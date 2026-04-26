"""
SereniBrain TH21A EEG reader — Windows (bleak / WinRT)

BEFORE FIRST RUN:
  Pair the headband in Windows Bluetooth settings once:
  Settings → Bluetooth & devices → Add device → pick TH21A_CB6860DA7605
  After it shows "Connected" there, run this script.

Usage:
  pip install bleak
  python client.py --csv eeg.csv
"""

import asyncio
import argparse
import csv
import inspect
import sys
import time
from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

# ── Device config ──────────────────────────────────────────────────────────────
ADDRESS     = "CB:68:60:DA:76:05"
NOTIFY_CHAR = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"
WRITE_CHAR  = "8653000c-43e6-47b7-9cb0-5fc21d4ae340"
BATTERY     = "00002a19-0000-1000-8000-00805f9b34fb"
SERVICE_CHANGED = "00002a05-0000-1000-8000-00805f9b34fb"

# ── Packet constants ───────────────────────────────────────────────────────────
MAGIC         = b'DATA'
HEADER_LEN    = 12
SAMPLE_STRIDE = 7      # [4B raw int32 LE] [2B idx uint16 LE] [1B pad]
FOOTER_LEN    = 10
CHANNEL_EEG   = 0x02
MSGTYPE_EEG   = 0x03
STREAM_KICK_CANDIDATES = (
    b"START",
    b"start",
    b"\x01",
    b"\x01\x00",
    b"DATA\x00\x01\x00\x01",
    b"DATA\x00\x02\x00\x01",
)


def parse_eeg_packet(data: bytes) -> list[tuple[int, int]]:
    if len(data) < HEADER_LEN + FOOTER_LEN:
        return []
    if data[:4] != MAGIC:
        return []
    if data[5] != CHANNEL_EEG or data[7] != MSGTYPE_EEG:
        return []
    samples = []
    end    = len(data) - FOOTER_LEN
    offset = HEADER_LEN
    while offset + SAMPLE_STRIDE <= end:
        raw = int.from_bytes(data[offset:offset + 4], 'little', signed=True)
        idx = int.from_bytes(data[offset + 4:offset + 6], 'little')
        samples.append((idx, raw))
        offset += SAMPLE_STRIDE
    return samples


class EEGReader:
    def __init__(self, csv_path: str | None = None):
        self.csv_path     = csv_path
        self.csv_file     = None
        self.csv_writer   = None
        self.sample_count = 0
        self.packet_count = 0
        self.last_idx     = None
        self.dropped      = 0
        self._start_time  = None

    def open_csv(self):
        if self.csv_path:
            self.csv_file   = open(self.csv_path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['timestamp_s', 'sample_index', 'raw_adc'])
            print(f"[CSV] Writing to {self.csv_path}")

    def close_csv(self):
        if self.csv_file:
            self.csv_file.close()

    def handle_eeg(self, sender: BleakGATTCharacteristic, data: bytes):
        if self._start_time is None:
            self._start_time = time.time()

        if len(data) < 8 or data[:4] != MAGIC:
            print(f"[?] Unknown packet ({len(data)}B): {data[:8].hex()}")
            return

        channel  = data[5]
        msg_type = data[7]

        if channel == 0x01 and msg_type == 0x03:
            try:
                name = data[12:17].decode('ascii', errors='replace').rstrip('\x00')
                hz   = data[19] if len(data) > 19 else '?'
                print(f"[INFO] Device: {name}  {hz} Hz")
            except Exception:
                pass
            return

        if channel == 0x01 and msg_type == 0x04:
            statuses = []
            for i in range(4):
                pos = 14 + i * 4
                if pos + 2 <= len(data):
                    statuses.append('OK' if data[pos:pos+2] == b'OK' else 'BAD')
            if statuses:
                print(f"[STATUS] Electrodes: {' | '.join(statuses)}")
            return

        if channel != CHANNEL_EEG or msg_type != MSGTYPE_EEG:
            print(f"[UNKNOWN] ch=0x{channel:02x} type=0x{msg_type:02x}")
            return

        samples = parse_eeg_packet(data)
        if not samples:
            return

        self.packet_count += 1
        elapsed = time.time() - self._start_time

        for idx, raw in samples:
            if self.last_idx is not None:
                gap = (idx - self.last_idx) & 0xFFFF
                if gap > 1:
                    self.dropped += gap - 1
            self.last_idx = idx
            self.sample_count += 1
            print(f"[EEG] #{idx:6d}  raw={raw:10d}")
            if self.csv_writer:
                self.csv_writer.writerow([f"{elapsed:.4f}", idx, raw])

        if self.csv_file:
            self.csv_file.flush()

    def handle_battery(self, sender: BleakGATTCharacteristic, data: bytes):
        print(f"[BATTERY] {data[0]}%")

    def print_stats(self):
        print(f"\n── Stats ──────────────────────────────")
        print(f"  Packets received : {self.packet_count}")
        print(f"  Samples received : {self.sample_count}")
        print(f"  Dropped samples  : {self.dropped}")
        if self.sample_count + self.dropped > 0:
            pct = 100 * self.dropped / (self.sample_count + self.dropped)
            print(f"  Drop rate        : {pct:.2f}%")
        print(f"───────────────────────────────────────")


async def resolve_device(target: str):
    """Resolve a BLE address/name into a concrete BLEDevice for reliable WinRT connects."""
    needle = target.lower()
    print("Scanning 6s to resolve device...")
    devices = await BleakScanner.discover(timeout=6.0)
    for dev in devices:
        name = (dev.name or "").lower()
        address = (dev.address or "").lower()
        if needle in (name, address):
            print(f"Resolved: {dev.name} ({dev.address})")
            return dev
    print("[WARN] Device not found during scan; falling back to direct address connect")
    return target


def dump_char_info(client: BleakClient, uuid: str, label: str):
    ch = client.services.get_characteristic(uuid)
    if ch is None:
        print(f"[WARN] {label} characteristic not found: {uuid}")
        return
    props = ", ".join(ch.properties)
    print(f"[{label}] handle={ch.handle} props=[{props}]")


def service_changed_handler(sender, data: bytes):
    # Present only for parity with nRF Connect subscription flow.
    return


def mac_to_int(mac: str) -> int:
    return int(mac.replace(":", ""), 16)


def winrt_buf_to_bytes(buf) -> bytes:
    from winsdk.windows.storage.streams import DataReader, ByteOrder

    reader = DataReader.from_buffer(buf)
    reader.byte_order = ByteOrder.LITTLE_ENDIAN
    return bytes(reader.read_bytes(buf.length))


async def get_winrt_services(device):
    """Get services preferring UNCACHED mode, with compatibility fallback."""
    from winsdk.windows.devices.bluetooth import BluetoothCacheMode

    try:
        return await device.get_gatt_services_async(BluetoothCacheMode.UNCACHED)
    except Exception:
        return await device.get_gatt_services_async()


async def get_winrt_characteristics(service):
    """Get characteristics preferring UNCACHED mode, with compatibility fallback."""
    from winsdk.windows.devices.bluetooth import BluetoothCacheMode

    try:
        return await service.get_characteristics_async(BluetoothCacheMode.UNCACHED)
    except Exception:
        return await service.get_characteristics_async()


async def find_winrt_characteristic(device, target_uuid: str):
    from winsdk.windows.devices.bluetooth.genericattributeprofile import GattCommunicationStatus

    target_uuid = target_uuid.lower()
    services_result = await get_winrt_services(device)
    if services_result.status != GattCommunicationStatus.SUCCESS:
        print(f"[WINRT] get_gatt_services failed: {services_result.status}")
        return None

    for service in services_result.services:
        chars_result = await get_winrt_characteristics(service)
        if chars_result.status != GattCommunicationStatus.SUCCESS:
            continue
        for char in chars_result.characteristics:
            if str(char.uuid).lower() == target_uuid:
                return char
    return None


async def write_winrt_cccd(char, cccd_value, protection_level=None):
    """Write CCCD across winsdk projections that expose 1-arg or 2-arg overloads."""
    fn = char.write_client_characteristic_configuration_descriptor_with_result_async

    if protection_level is not None:
        try:
            return await fn(cccd_value, protection_level)
        except Exception as e:
            msg = str(e).lower()
            if "invalid parameter count" not in msg and "parameter" not in msg:
                raise

    return await fn(cccd_value)


async def write_winrt_cccd_simple(char, cccd_value):
    """Use the non-result WinRT CCCD API used by rawtest.py when available."""
    fn = getattr(char, "write_client_characteristic_configuration_descriptor_async", None)
    if callable(fn):
        return await fn(cccd_value)
    return None


async def read_winrt_cccd(char):
    fn = getattr(char, "read_client_characteristic_configuration_descriptor_async", None)
    if not callable(fn):
        return None
    try:
        result = await fn()
        return getattr(result, "client_characteristic_configuration_descriptor", None)
    except Exception:
        return None


async def subscribe_winrt_char(char, cccd_value, label: str):
    """Try multiple WinRT CCCD subscription paths and return (ok, status_text, readback)."""
    attempts = []

    try:
        simple_status = await write_winrt_cccd_simple(char, cccd_value)
        attempts.append(f"simple={simple_status}")
    except Exception as e:
        attempts.append(f"simple_err={e}")

    # If simple path did not work, try result API with stronger protection then plain.
    if not attempts or any("err=" in a for a in attempts):
        for protection_name, protection in (("enc", 2), ("plain", 1)):
            try:
                res = await write_winrt_cccd(char, cccd_value, protection)
                status = getattr(res, "status", res)
                attempts.append(f"result_{protection_name}={status}")
                # success is usually status 0 (GattCommunicationStatus.SUCCESS)
                if str(status) == "0":
                    break
            except Exception as e:
                attempts.append(f"result_{protection_name}_err={e}")

    rb = await read_winrt_cccd(char)
    status_text = " | ".join(attempts)
    ok = (rb is not None and str(rb).endswith("NOTIFY")) or ("=0" in status_text)
    print(f"[FALLBACK] {label} CCCD: {status_text} readback={rb}")
    return ok, status_text, rb


async def write_winrt_value(char, payload: bytes, response: bool):
    """Write a payload to a WinRT characteristic across projection/method variants."""
    from winsdk.windows.devices.bluetooth.genericattributeprofile import (
        GattCommunicationStatus,
        GattWriteOption,
    )
    from winsdk.windows.storage.streams import DataWriter

    option = (
        GattWriteOption.WRITE_WITH_RESPONSE
        if response
        else GattWriteOption.WRITE_WITHOUT_RESPONSE
    )

    def make_buffer():
        writer = DataWriter()
        writer.write_bytes(payload)
        return writer.detach_buffer()

    attempts = []

    fn_with_result = getattr(char, "write_value_with_result_async", None)
    if callable(fn_with_result):
        try:
            result = await fn_with_result(make_buffer(), option)
            status = getattr(result, "status", result)
            attempts.append(f"with_result_opt={status}")
            if str(status) == str(GattCommunicationStatus.SUCCESS) or str(status) == "0":
                return True, " | ".join(attempts)
        except Exception as e:
            attempts.append(f"with_result_opt_err={e}")

        try:
            result = await fn_with_result(make_buffer())
            status = getattr(result, "status", result)
            attempts.append(f"with_result={status}")
            if str(status) == str(GattCommunicationStatus.SUCCESS) or str(status) == "0":
                return True, " | ".join(attempts)
        except Exception as e:
            attempts.append(f"with_result_err={e}")

    fn = getattr(char, "write_value_async", None)
    if callable(fn):
        try:
            status = await fn(make_buffer(), option)
            attempts.append(f"write_async_opt={status}")
            if str(status) == str(GattCommunicationStatus.SUCCESS) or str(status) == "0":
                return True, " | ".join(attempts)
        except Exception as e:
            attempts.append(f"write_async_opt_err={e}")

        try:
            status = await fn(make_buffer())
            attempts.append(f"write_async={status}")
            if str(status) == str(GattCommunicationStatus.SUCCESS) or str(status) == "0":
                return True, " | ".join(attempts)
        except Exception as e:
            attempts.append(f"write_async_err={e}")

    return False, " | ".join(attempts) if attempts else "no write API available"


async def try_kick_stream_winrt(write_char, reader: EEGReader) -> bool:
    print("[FALLBACK] No packets yet; trying stream kick commands on WinRT write characteristic...")
    for payload in STREAM_KICK_CANDIDATES:
        for response in (False, True):
            ok, status_text = await write_winrt_value(write_char, payload, response)
            print(
                f"[FALLBACK] kick {payload!r} (response={response}) -> "
                f"ok={ok} [{status_text}]"
            )
            await asyncio.sleep(1.0)
            if reader.packet_count > 0:
                print("[FALLBACK] kick succeeded: EEG packets started")
                return True
    return False


async def run_winsdk(address: str, csv_path: str | None):
    print("\n[FALLBACK] Trying native WinRT GATT path...")
    try:
        from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
        from winsdk.windows.devices.bluetooth.genericattributeprofile import (
            GattClientCharacteristicConfigurationDescriptorValue,
            GattProtectionLevel,
            GattCommunicationStatus,
            GattSession,
        )
        from winsdk.windows.devices.enumeration import DevicePairingKinds, DevicePairingResultStatus
    except Exception as e:
        print(f"[FALLBACK] winsdk unavailable: {e}")
        return

    # Do not truncate the existing CSV if the bleak path already created it.
    fallback_csv = None
    if csv_path:
        print("[FALLBACK] CSV write disabled for fallback to avoid overwriting existing file")
    reader = EEGReader(fallback_csv)
    reader.open_csv()
    device = None
    eeg_char = None
    write_char = None
    bat_char = None
    svc_changed_char = None
    gatt_session = None

    try:
        addr_int = mac_to_int(address)
        device = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)
        if device is None:
            print("[FALLBACK] Could not open BluetoothLEDevice from address")
            return

        print(f"[FALLBACK] Device: {device.name}")
        try:
            access = await device.request_access_async()
            print(f"[FALLBACK] Access status: {access}")
        except Exception as e:
            print(f"[FALLBACK] Access request failed: {e}")

        pairing = device.device_information.pairing
        print(f"[FALLBACK] Already paired: {pairing.is_paired}")
        if not pairing.is_paired:
            custom = pairing.custom

            def on_pairing_requested(sender, args):
                try:
                    args.accept()
                except Exception:
                    pass

            token = custom.add_pairing_requested(on_pairing_requested)
            result = await custom.pair_async(
                DevicePairingKinds.CONFIRM_ONLY | DevicePairingKinds.CONFIRM_PAIRING_FRIENDLY_NAME
            )
            custom.remove_pairing_requested(token)
            print(f"[FALLBACK] Pair result: {result.status}")
            if result.status not in (
                DevicePairingResultStatus.PAIRED,
                DevicePairingResultStatus.ALREADY_PAIRED,
            ):
                print("[FALLBACK] Pairing did not fully succeed")

        await asyncio.sleep(2.0)

        eeg_char = await find_winrt_characteristic(device, NOTIFY_CHAR)
        if eeg_char is None:
            print("[FALLBACK] EEG notify characteristic not found")
            return
        write_char = await find_winrt_characteristic(device, WRITE_CHAR)
        if write_char is None:
            print("[FALLBACK] EEG write characteristic not found")
        bat_char = await find_winrt_characteristic(device, BATTERY)
        svc_changed_char = await find_winrt_characteristic(device, SERVICE_CHANGED)

        # Keep GATT session alive if available in this projection.
        try:
            gatt_session = await GattSession.from_device_id_async(device.bluetooth_device_id)
            if gatt_session is not None:
                gatt_session.maintain_connection = True
                print("[FALLBACK] GATT session maintain_connection enabled")
        except Exception as e:
            print(f"[FALLBACK] GATT session setup skipped: {e}")

        def eeg_handler(sender, args):
            try:
                payload = winrt_buf_to_bytes(args.characteristic_value)
                reader.handle_eeg(None, payload)
            except Exception as ex:
                print(f"[FALLBACK] EEG callback error: {ex}")

        def bat_handler(sender, args):
            try:
                payload = winrt_buf_to_bytes(args.characteristic_value)
                reader.handle_battery(None, payload)
            except Exception:
                pass

        def svc_changed_handler(sender, args):
            return

        if svc_changed_char is not None:
            svc_changed_char.add_value_changed(svc_changed_handler)
            try:
                await subscribe_winrt_char(
                    svc_changed_char,
                    GattClientCharacteristicConfigurationDescriptorValue.INDICATE,
                    "Service Changed",
                )
            except Exception as e:
                print(f"[FALLBACK] Service Changed subscribe skipped: {e}")

        eeg_char.add_value_changed(eeg_handler)
        eeg_ok, eeg_status_text, _ = await subscribe_winrt_char(
            eeg_char,
            GattClientCharacteristicConfigurationDescriptorValue.NOTIFY,
            "EEG",
        )
        if not eeg_ok:
            print(f"[FALLBACK] EEG subscribe failed after retries: {eeg_status_text}")
            return

        if bat_char is not None:
            bat_char.add_value_changed(bat_handler)
            await subscribe_winrt_char(
                bat_char,
                GattClientCharacteristicConfigurationDescriptorValue.NOTIFY,
                "Battery",
            )

        print("[FALLBACK] Waiting for EEG packets (5s)...")
        await asyncio.sleep(5.0)

        if reader.packet_count == 0 and write_char is not None:
            kicked = await try_kick_stream_winrt(write_char, reader)
            if kicked:
                await asyncio.sleep(2.0)

        if reader.packet_count == 0:
            print("[FALLBACK] Waiting for EEG packets after kick attempts (5s)...")
            await asyncio.sleep(5.0)

        if reader.packet_count == 0:
            print("[FALLBACK] Still no packets on WinRT path")
        else:
            print("[FALLBACK] Streaming started")
            while True:
                await asyncio.sleep(1.0)
                if device.connection_status != BluetoothConnectionStatus.CONNECTED:
                    print("[FALLBACK] Device disconnected")
                    break

    except KeyboardInterrupt:
        print("\n[FALLBACK] Stopped by user")
    except Exception as e:
        print(f"[FALLBACK] Error: {e}")
    finally:
        try:
            if eeg_char is not None:
                await write_winrt_cccd(
                    eeg_char,
                    GattClientCharacteristicConfigurationDescriptorValue.NONE,
                    GattProtectionLevel.PLAIN,
                )
        except Exception:
            pass

        try:
            if device is not None:
                device.close()
        except Exception:
            pass

        try:
            if gatt_session is not None:
                gatt_session.close()
        except Exception:
            pass

        reader.close_csv()
        reader.print_stats()


async def try_kick_stream(client: BleakClient, reader: EEGReader) -> bool:
    print("[WARN] No data yet; trying stream kick commands on write characteristic...")
    for payload in STREAM_KICK_CANDIDATES:
        for response in (False, True):
            try:
                await client.write_gatt_char(WRITE_CHAR, payload, response=response)
                print(f"  kick sent: {payload!r} (response={response})")
                await asyncio.sleep(1.0)
                if reader.packet_count > 0:
                    print("  kick succeeded: EEG packets started")
                    return True
            except Exception as e:
                print(f"  kick failed for {payload!r} (response={response}): {e}")
    return False


async def run_raw_probe(client: BleakClient) -> int:
    """Subscribe with a raw callback briefly to see whether any notifications arrive at all."""
    raw_count = 0

    def raw_dump(sender, data: bytes):
        nonlocal raw_count
        raw_count += 1
        preview = data.hex()
        if len(preview) > 96:
            preview = preview[:96] + "..."
        print(f"  [RAW] {len(data)}B: {preview}")

    try:
        await client.stop_notify(NOTIFY_CHAR)
    except Exception:
        pass

    await client.start_notify(NOTIFY_CHAR, raw_dump)
    await asyncio.sleep(5.0)
    try:
        await client.stop_notify(NOTIFY_CHAR)
    except Exception:
        pass
    return raw_count


async def ensure_services_resolved(client: BleakClient):
    """Resolve GATT services across bleak versions without crashing."""
    try:
        # bleak versions differ: some expose get_services(), others only services.
        get_services = getattr(client, "get_services", None)
        if callable(get_services):
            await get_services()
            return
        # Accessing .services may trigger lazy resolution in some builds.
        _ = client.services
    except Exception:
        # Last-resort path used by some backend implementations.
        backend = getattr(client, "_backend", None)
        backend_get_services = getattr(backend, "get_services", None)
        if callable(backend_get_services):
            await backend_get_services()


async def pair_with_best_effort(client: BleakClient):
    """Try WinRT pair variants to maximize chance of encrypted notifications."""
    pair_fn = getattr(client, "pair", None)
    if not callable(pair_fn):
        print("  pair() not available in this bleak build")
        return

    try:
        sig = inspect.signature(pair_fn)
        if "protection_level" in sig.parameters:
            for level in (2, 1):
                try:
                    paired = await pair_fn(protection_level=level)
                    print(f"  pair(protection_level={level}) returned: {paired}")
                    return
                except Exception as e:
                    print(f"  pair(protection_level={level}) failed: {e}")
        paired = await pair_fn()
        print(f"  pair() returned: {paired}")
    except Exception as e:
        print(f"  pair() exception (may be OK): {e}")


async def run(address: str, csv_path: str | None, kick_stream: bool, winsdk_fallback: bool):
    reader = EEGReader(csv_path)
    reader.open_csv()
    should_try_winsdk = False

    print(f"Connecting to {address} ...")
    print("Make sure the headband is paired in Windows Bluetooth settings first.\n")

    try:
        target = await resolve_device(address)

        # WinRT can cache stale GATT layouts/CCCD state; prefer uncached services.
        client_kwargs = {"timeout": 30.0}
        try:
            client_kwargs["winrt"] = {"use_cached_services": False}
            client = BleakClient(target, **client_kwargs)
        except TypeError:
            # Older bleak builds may not support winrt kwargs.
            client_kwargs.pop("winrt", None)
            client = BleakClient(target, **client_kwargs)

        async with client:
            print(f"Connected! MTU={client.mtu_size}")

            # nRF Connect log shows bonding via CONSENT ("Just Works") happens
            # inline during connection — no pre-pairing needed.
            # We explicitly trigger this here so WinRT negotiates encryption
            # before we touch any characteristics.
            print("Pairing (triggering BLE bonding / encryption)...")
            await pair_with_best_effort(client)

            # nRF Connect waits 1600ms after bonding before doing anything.
            # We do 2s to be safe.
            print("Settling after bond (2s)...")
            await asyncio.sleep(2.0)

            await ensure_services_resolved(client)
            dump_char_info(client, SERVICE_CHANGED, "Service Changed")
            dump_char_info(client, NOTIFY_CHAR, "EEG notify")
            dump_char_info(client, WRITE_CHAR, "EEG write")
            dump_char_info(client, BATTERY, "Battery")

            # Force an encrypted attribute operation before notification subscribe.
            # If this read fails, notifications often fail silently too on WinRT.
            try:
                bat = await client.read_gatt_char(BATTERY)
                if bat:
                    print(f"[BATTERY-READ] {bat[0]}%")
            except Exception as e:
                print(f"[WARN] Battery pre-read failed: {e}")

            try:
                await client.stop_notify(NOTIFY_CHAR)
            except Exception:
                pass

            # Match nRF Connect order: Service Changed -> EEG -> Battery
            try:
                await client.start_notify(SERVICE_CHANGED, service_changed_handler)
            except Exception:
                pass

            await client.start_notify(NOTIFY_CHAR, reader.handle_eeg)
            await client.start_notify(BATTERY, reader.handle_battery)

            print("\nWaiting for data stream...\n")
            await asyncio.sleep(5.0)

            if reader.packet_count == 0:
                print("[WARN] No data after first subscribe pass. Re-subscribing without writes...")
                try:
                    await client.stop_notify(NOTIFY_CHAR)
                except Exception:
                    pass
                await asyncio.sleep(0.8)
                await client.start_notify(NOTIFY_CHAR, reader.handle_eeg)
                await asyncio.sleep(4.0)

            if reader.packet_count == 0 and kick_stream:
                kicked = await try_kick_stream(client, reader)
                if kicked:
                    await asyncio.sleep(2.0)

            if reader.packet_count == 0:
                print("[WARN] Still no data after 5s. Trying stop+restart notify...")
                try:
                    await client.stop_notify(NOTIFY_CHAR)
                    await asyncio.sleep(0.5)
                    await client.start_notify(NOTIFY_CHAR, reader.handle_eeg)
                except Exception as e:
                    print(f"  [WARN] Re-subscribe failed: {e}")
                await asyncio.sleep(5.0)

            if reader.packet_count == 0:
                print("[WARN] Running raw notification probe (5s)...")
                try:
                    raw_count = await run_raw_probe(client)
                    await client.start_notify(NOTIFY_CHAR, reader.handle_eeg)
                except Exception as e:
                    raw_count = 0
                    print(f"  [WARN] Raw probe failed: {e}")

                if raw_count == 0:
                    print("  [DIAG] No notifications at all reached this client.")
                    print("  [DIAG] Likely causes: BLE bond/encryption state, concurrent connection from another host, or headset not in active streaming mode.")
                else:
                    print(f"  [DIAG] Received {raw_count} raw notifications but none parsed as EEG.")
                    print("  [DIAG] Protocol mismatch is likely; capture these RAW packets and we can update parser/start command.")

            if reader.packet_count == 0:
                print("\n[ERROR] No data received. Things to check:")
                print("  1. Is the headband powered on?")
                print("  2. Is it on your head with electrodes touching skin?")
                print("     (The device may only stream when worn)")
                print("  3. Try power-cycling the headband and re-running.")
                if winsdk_fallback:
                    should_try_winsdk = True
            else:
                print(f"[OK] Streaming! Press Ctrl+C to stop.\n")
                while client.is_connected:
                    await asyncio.sleep(0.5)

    except BleakError as e:
        print(f"\n[BLE ERROR] {e}")
        if "not found" in str(e).lower():
            print("  → Device not found. Is it powered on and in range?")
        elif "timeout" in str(e).lower() or "0x8" in str(e):
            print("  → Connection timed out. The device disconnects after ~2.5 min.")
            print("    Re-run the script to reconnect.")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        reader.close_csv()
        reader.print_stats()

    if should_try_winsdk:
        await run_winsdk(address, csv_path)


def main():
    parser = argparse.ArgumentParser(description="SereniBrain TH21A EEG reader")
    parser.add_argument('--address', default=ADDRESS,
                        help=f"BLE MAC address (default: {ADDRESS})")
    parser.add_argument('--csv', metavar='FILE',
                        help="Save samples to CSV file")
    parser.add_argument('--no-kick-stream', action='store_true',
                        help="Disable fallback write commands used when notifications stay silent")
    parser.add_argument('--no-winsdk-fallback', action='store_true',
                        help="Disable native WinRT fallback attempt when bleak receives no EEG packets")
    args = parser.parse_args()
    asyncio.run(
        run(
            args.address,
            args.csv,
            kick_stream=not args.no_kick_stream,
            winsdk_fallback=not args.no_winsdk_fallback,
        )
    )


if __name__ == '__main__':
    main()
