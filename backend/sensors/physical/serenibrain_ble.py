"""
SereniBrain BLE Sensor (physical)

Wraps a BLE notification characteristic from a SereniBrain-style EEG headstrap
and republishes samples as an LSL outlet via the PhysicalSensor base class.

Configuration is driven by environment variables so you can tune it without
editing code:

  SERENI_BLE_ADDRESS      Optional BLE MAC/address (preferred if known)
  SERENI_BLE_NAME         Device name hint for scan fallback (default: SereniBrain)
  SERENI_BLE_CHAR_UUID    Notify characteristic UUID (auto-pick if omitted)
    SERENI_BLE_WRITE_UUID   Optional write characteristic UUID for start command
    SERENI_BLE_START_HEX    Optional hex payload to write after connect (e.g. A10001)
  SERENI_BLE_CHANNELS     Number of EEG channels expected (default: 4)
  SERENI_BLE_RATE         Sample rate in Hz (default: 128)
  SERENI_BLE_FORMAT       Payload format: f32le | i16le | u16le (default: f32le)
    SERENI_BLE_SCALE        Scalar multiplier for decoded values (default: 1.0)
    SERENI_BLE_RECONNECT_SECONDS  Reconnect if no data for N seconds (default: 6)
"""

from __future__ import annotations

import asyncio
import os
import queue
import struct
import threading
import time
from typing import Any
from dataclasses import dataclass, field

from sensors.sensor import BluetoothPhysicalSensor

try:
    from bleak import BleakClient, BleakScanner
except Exception as exc:  # pragma: no cover
    BleakClient = None
    BleakScanner = None
    _BLEAK_IMPORT_ERROR = exc
else:
    _BLEAK_IMPORT_ERROR = None


@dataclass
class SereniBrainBLE(BluetoothPhysicalSensor):
    address: str = ""
    device_name: str = "SereniBrain"
    notify_char_uuid: str = ""
    write_char_uuid: str = ""
    start_hex: str = ""
    payload_format: str = "f32le"  # f32le | i16le | u16le
    scale: float = 1.0
    reconnect_after_s: float = 6.0

    _loop: asyncio.AbstractEventLoop | None = field(init=False, default=None)
    _loop_ready: threading.Event = field(init=False, default_factory=threading.Event)
    _loop_thread: threading.Thread | None = field(init=False, default=None)
    _client: Any = field(init=False, default=None)
    _resolved_address: str = field(init=False, default="")
    _resolved_char_uuid: str = field(init=False, default="")
    _samples: queue.Queue[list[float]] = field(init=False, default_factory=queue.Queue)
    _last_rx: float = field(init=False, default=0.0)
    _last_reconnect_attempt: float = field(init=False, default=0.0)
    _reconnecting: bool = field(init=False, default=False)

    @classmethod
    def default(cls):
        channels = int(os.getenv("SERENI_BLE_CHANNELS", "4"))
        rate = float(os.getenv("SERENI_BLE_RATE", "128"))
        return cls(
            uid="serenibrain_ble_001",
            name="SereniBrainEEG",
            type="EEG",
            channels=channels,
            sample_rate=rate,
            channel_labels=[f"EEG {i + 1}" for i in range(channels)],
            address=os.getenv("SERENI_BLE_ADDRESS", "").strip(),
            device_name=os.getenv("SERENI_BLE_NAME", "SereniBrain").strip() or "SereniBrain",
            notify_char_uuid=os.getenv("SERENI_BLE_CHAR_UUID", "").strip().lower(),
            write_char_uuid=os.getenv("SERENI_BLE_WRITE_UUID", "").strip().lower(),
            start_hex=os.getenv("SERENI_BLE_START_HEX", "").strip(),
            payload_format=os.getenv("SERENI_BLE_FORMAT", "f32le").strip().lower(),
            scale=float(os.getenv("SERENI_BLE_SCALE", "1.0")),
            reconnect_after_s=float(os.getenv("SERENI_BLE_RECONNECT_SECONDS", "6")),
        )

    def _run_event_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()

    def _run_coro(self, coro):
        if not self._loop:
            raise RuntimeError("BLE event loop not initialized")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=25)

    async def _resolve_address(self) -> str:
        if BleakScanner is None:
            raise RuntimeError(f"bleak import failed: {_BLEAK_IMPORT_ERROR}")

        devices = await BleakScanner.discover(timeout=8.0)
        if self.address:
            for dev in devices:
                if dev.address.lower() == self.address.lower():
                    return dev.address

        target = self.device_name.lower()
        for dev in devices:
            if dev.name and target in dev.name.lower():
                return dev.address

        available = [f"{d.name or '<unknown>'} [{d.address}]" for d in devices]
        if self.address:
            raise RuntimeError(
                f"Configured address '{self.address}' not found and no device matching "
                f"name '{self.device_name}' was discovered. Nearby devices: {available}"
            )
        raise RuntimeError(
            f"No BLE device matching '{self.device_name}' found. Nearby devices: {available}"
        )

    async def _resolve_notify_uuid(self, client: Any) -> str:
        if self.notify_char_uuid:
            return self.notify_char_uuid

        if hasattr(client, "get_services"):
            services = await client.get_services()
        else:
            services = client.services

        if services is None:
            raise RuntimeError("No GATT services available from BLE device")

        for svc in services:
            for ch in svc.characteristics:
                props = {p.lower() for p in ch.properties}
                if "notify" in props:
                    return str(ch.uuid).lower()

        raise RuntimeError("No notify characteristic found on BLE device")

    def _decode_payload(self, data: bytearray) -> list[float] | None:
        raw = bytes(data)
        if not raw:
            return None

        fmt = self.payload_format
        if fmt == "f32le":
            if len(raw) % 4 != 0:
                return None
            vals = list(struct.unpack("<" + "f" * (len(raw) // 4), raw))
        elif fmt == "i16le":
            if len(raw) % 2 != 0:
                return None
            vals = [float(v) for v in struct.unpack("<" + "h" * (len(raw) // 2), raw)]
        elif fmt == "u16le":
            if len(raw) % 2 != 0:
                return None
            vals = [float(v) for v in struct.unpack("<" + "H" * (len(raw) // 2), raw)]
        else:
            raise RuntimeError(
                f"Unsupported SERENI_BLE_FORMAT='{fmt}'. Use f32le, i16le, or u16le."
            )

        vals = [v * self.scale for v in vals]

        if len(vals) >= self.channels:
            return vals[: self.channels]

        # Pad short payloads so push_sample always matches configured channel count.
        return vals + [0.0] * (self.channels - len(vals))

    async def _connect_async(self):
        if BleakClient is None:
            raise RuntimeError(f"bleak import failed: {_BLEAK_IMPORT_ERROR}")

        self._resolved_address = await self._resolve_address()
        self._client = BleakClient(self._resolved_address)
        await self._client.connect(timeout=15.0)

        self._resolved_char_uuid = await self._resolve_notify_uuid(self._client)

        def _on_notification(_sender: str, data: bytearray):
            sample = self._decode_payload(data)
            if sample is not None:
                self._last_rx = time.monotonic()
                self._samples.put_nowait(sample)

        await self._client.start_notify(self._resolved_char_uuid, _on_notification)

        # Some devices require a control write before streaming begins.
        if self.start_hex:
            if not self.write_char_uuid:
                raise RuntimeError(
                    "SERENI_BLE_START_HEX is set but SERENI_BLE_WRITE_UUID is empty."
                )
            payload = bytes.fromhex(self.start_hex)
            await self._client.write_gatt_char(self.write_char_uuid, payload, response=False)

    def _is_connected(self) -> bool:
        if self._client is None:
            return False
        return bool(getattr(self._client, "is_connected", False))

    def _reconnect_if_needed(self):
        if self.reconnect_after_s <= 0:
            return

        now = time.monotonic()
        no_data_too_long = self._last_rx > 0 and (now - self._last_rx) >= self.reconnect_after_s
        disconnected = not self._is_connected()

        if not (no_data_too_long or disconnected):
            return
        if self._reconnecting:
            return
        if (now - self._last_reconnect_attempt) < 2.0:
            return

        self._last_reconnect_attempt = now
        self._reconnecting = True
        try:
            print(f"[{self.name}] BLE link dropped/stalled; reconnecting...")
            self._run_coro(self._disconnect_async())
            self._run_coro(self._connect_async())
            print(f"[{self.name}] BLE reconnect successful")
        except Exception as e:
            print(f"[{self.name}] BLE reconnect failed: {e}")
        finally:
            self._reconnecting = False

    async def _disconnect_async(self):
        if self._client is None:
            return

        try:
            if self._resolved_char_uuid:
                await self._client.stop_notify(self._resolved_char_uuid)
        except Exception:
            pass

        try:
            await self._client.disconnect()
        finally:
            self._client = None

    def connect(self):
        # Start the async event loop only once; safe to call again on retry.
        if self._loop is None or not self._loop.is_running():
            self._loop_ready.clear()
            self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._loop_thread.start()
            if not self._loop_ready.wait(timeout=3):
                raise RuntimeError("Failed to start BLE event loop")

        self._run_coro(self._connect_async())
        self._last_rx = time.monotonic()
        print(
            f"[{self.name}] Connected BLE {self._resolved_address} | "
            f"char={self._resolved_char_uuid} | format={self.payload_format}"
        )

    def read_sample(self) -> list[float] | None:
        self._reconnect_if_needed()
        try:
            return self._samples.get_nowait()
        except queue.Empty:
            return None

    def disconnect(self):
        if self._loop:
            try:
                self._run_coro(self._disconnect_async())
            except Exception:
                pass

            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread:
            self._loop_thread.join(timeout=2)

        self._loop = None
        self._loop_thread = None
        print(f"[{self.name}] Disconnected BLE")


if __name__ == "__main__":
    sensor = SereniBrainBLE.default()
    sensor.run()
