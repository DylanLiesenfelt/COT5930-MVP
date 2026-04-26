"""
SereniBrain TH21A EEG reader — Windows (winsdk)
Install: pip install winsdk
Run:     python client.py --csv eeg.csv
"""

import asyncio
import argparse
import csv
import time
import threading

from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
from winsdk.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCommunicationStatus,
    GattSession,
)
from winsdk.windows.storage.streams import DataReader, ByteOrder

MAC          = "CB:68:60:DA:76:05"
NOTIFY_UUID  = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

MAGIC         = b'DATA'
HEADER_LEN    = 12
SAMPLE_STRIDE = 7
FOOTER_LEN    = 10
CHANNEL_EEG   = 0x02
MSGTYPE_EEG   = 0x03


def mac_to_int(mac):
    return int(mac.replace(":", ""), 16)


def buf_to_bytes(buf):
    reader = DataReader.from_buffer(buf)
    reader.byte_order = ByteOrder.LITTLE_ENDIAN
    return bytes(reader.read_bytes(buf.length))


def parse_eeg(data):
    if len(data) < HEADER_LEN + FOOTER_LEN or data[:4] != MAGIC:
        return []
    if data[5] != CHANNEL_EEG or data[7] != MSGTYPE_EEG:
        return []
    samples, end, offset = [], len(data) - FOOTER_LEN, HEADER_LEN
    while offset + SAMPLE_STRIDE <= end:
        raw = int.from_bytes(data[offset:offset+4], 'little', signed=True)
        idx = int.from_bytes(data[offset+4:offset+6], 'little')
        samples.append((idx, raw))
        offset += SAMPLE_STRIDE
    return samples


class EEGReader:
    def __init__(self, csv_path=None):
        self.csv_path     = csv_path
        self.csv_file     = None
        self.csv_writer   = None
        self.sample_count = 0
        self.packet_count = 0
        self.last_idx     = None
        self.dropped      = 0
        self._t0          = None
        # asyncio queue — WinRT thread puts data here, asyncio loop reads it
        self.queue        = asyncio.Queue()

    def open_csv(self):
        if self.csv_path:
            self.csv_file   = open(self.csv_path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['timestamp_s', 'sample_index', 'raw_adc'])
            print(f"[CSV] Writing to {self.csv_path}")

    def close_csv(self):
        if self.csv_file:
            self.csv_file.close()

    def make_eeg_handler(self, loop):
        """
        Returns a callback for add_value_changed.
        WinRT fires this on its own thread — we use call_soon_threadsafe
        to safely hand the bytes over to the asyncio event loop.
        """
        def handler(char, args):
            try:
                data = buf_to_bytes(args.characteristic_value)
                loop.call_soon_threadsafe(self.queue.put_nowait, ('eeg', data))
            except Exception as e:
                loop.call_soon_threadsafe(self.queue.put_nowait, ('err', str(e)))
        return handler

    def make_battery_handler(self, loop):
        def handler(char, args):
            try:
                data = buf_to_bytes(args.characteristic_value)
                loop.call_soon_threadsafe(self.queue.put_nowait, ('bat', data))
            except Exception as e:
                pass
        return handler

    def process(self, kind, data):
        """Process a packet on the asyncio thread."""
        if kind == 'err':
            print(f"[ERR] {data}")
            return
        if kind == 'bat':
            print(f"[BATTERY] {data[0]}%")
            return

        # EEG packet
        if self._t0 is None:
            self._t0 = time.time()
        elapsed = time.time() - self._t0

        if len(data) < 8 or data[:4] != MAGIC:
            print(f"[RAW?] {len(data)}B: {data.hex()}")
            return

        ch, mt = data[5], data[7]

        if ch == 0x01 and mt == 0x03:
            try:
                name = data[12:17].decode('ascii', errors='replace').rstrip('\x00')
                print(f"[INFO] {name}  {data[19]}Hz")
            except Exception:
                pass
            return

        if ch == 0x01 and mt == 0x04:
            st = ['OK' if data[14+i*4:16+i*4]==b'OK' else 'BAD' for i in range(4)]
            print(f"[STATUS] {' | '.join(st)}")
            return

        if ch != CHANNEL_EEG or mt != MSGTYPE_EEG:
            print(f"[UNKNOWN] ch={ch:#04x} mt={mt:#04x}")
            return

        samples = parse_eeg(data)
        self.packet_count += 1
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

    def stats(self):
        print(f"\n── Stats ──────────────────────────")
        print(f"  Packets  : {self.packet_count}")
        print(f"  Samples  : {self.sample_count}")
        print(f"  Dropped  : {self.dropped}")
        print(f"───────────────────────────────────")


async def wait_connected(device, timeout=15.0):
    t = time.time()
    while time.time() - t < timeout:
        if device.connection_status == BluetoothConnectionStatus.CONNECTED:
            return True
        await asyncio.sleep(0.2)
    return False


async def get_char(device, uuid):
    uuid = uuid.lower()
    r = await device.get_gatt_services_async()
    if r.status != GattCommunicationStatus.SUCCESS:
        return None
    for svc in r.services:
        cr = await svc.get_characteristics_async()
        if cr.status != GattCommunicationStatus.SUCCESS:
            continue
        for c in cr.characteristics:
            if str(c.uuid).lower() == uuid:
                return c
    return None


async def run(mac, csv_path):
    loop   = asyncio.get_running_loop()
    reader = EEGReader(csv_path)
    reader.open_csv()

    print(f"Getting device {mac}...")
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(mac))
    if not device:
        print("[ERR] Device not found.")
        reader.close_csv()
        return
    print(f"  Name: {device.name}")

    print("Opening GattSession (maintain_connection=True)...")
    session = await GattSession.from_device_id_async(device.bluetooth_device_id)
    session.maintain_connection = True

    print("Waiting for connection...")
    if not await wait_connected(device):
        print("[ERR] Timed out.")
        session.close(); device.close(); reader.close_csv()
        return
    print(f"  Connected!")

    await asyncio.sleep(1.6)

    print("Getting characteristics...")
    eeg = await get_char(device, NOTIFY_UUID)
    bat = await get_char(device, BATTERY_UUID)
    if not eeg:
        print("[ERR] EEG characteristic not found.")
        session.close(); device.close(); reader.close_csv()
        return

    # Register handlers — WinRT calls these on its own thread.
    # The handlers use call_soon_threadsafe to push data into our asyncio queue.
    eeg_token = eeg.add_value_changed(reader.make_eeg_handler(loop))
    if bat:
        bat_token = bat.add_value_changed(reader.make_battery_handler(loop))

    print("Writing CCCD (enabling notifications)...")
    result = await eeg.write_client_characteristic_configuration_descriptor_async(
        GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
    )
    print(f"  EEG CCCD:  {result}  (0=success)")

    readback = await eeg.read_client_characteristic_configuration_descriptor_async()
    print(f"  CCCD readback: status={readback.status}  value={readback.client_characteristic_configuration_descriptor}  (1=notify on)")

    if bat:
        await bat.write_client_characteristic_configuration_descriptor_async(
            GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
        )

    if result != GattCommunicationStatus.SUCCESS:
        print(f"[ERR] CCCD write failed: {result}")
        session.close(); device.close(); reader.close_csv()
        return

    print("\nStreaming — press Ctrl+C to stop.\n")
    try:
        while True:
            if device.connection_status != BluetoothConnectionStatus.CONNECTED:
                print("[DISCONNECTED]")
                break
            try:
                kind, data = await asyncio.wait_for(reader.queue.get(), timeout=1.0)
                reader.process(kind, data)
            except asyncio.TimeoutError:
                pass  # just check connection status again
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        try:
            await eeg.write_client_characteristic_configuration_descriptor_async(
                GattClientCharacteristicConfigurationDescriptorValue.NONE
            )
        except Exception:
            pass
        session.close()
        device.close()
        reader.close_csv()
        reader.stats()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--address', default=MAC)
    p.add_argument('--csv', metavar='FILE')
    args = p.parse_args()
    asyncio.run(run(args.address, args.csv))


if __name__ == '__main__':
    main()