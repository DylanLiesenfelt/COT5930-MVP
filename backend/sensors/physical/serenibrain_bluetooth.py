"""
SereniBrain Bluetooth EEG sensor.

Wraps the TH21A BLE notify stream as a PhysicalSensor so it can be auto-started
by sensors/start_all_sensors.py and automatically discovered by SessionManager
through LSL.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from bleak import BleakClient

from sensors.sensor import PhysicalSensor
from sensors.physical.bluetooth_sensors.client import (
    ADDRESS,
    NOTIFY_CHAR,
    WRITE_CHAR,
    STREAM_KICK_CANDIDATES,
    ensure_services_resolved,
    pair_with_best_effort,
    parse_eeg_packet,
    resolve_device,
)


@dataclass
class SereniBrainBluetoothEEG(PhysicalSensor):
    """Stream TH21A EEG raw ADC samples into an LSL outlet."""

    address: str = ADDRESS
    notify_uuid: str = NOTIFY_CHAR
    write_uuid: str = WRITE_CHAR
    kick_on_connect: bool = True
    connect_timeout_s: float = 25.0

    _loop: asyncio.AbstractEventLoop | None = field(init=False, default=None)
    _thread: threading.Thread | None = field(init=False, default=None)
    _connected: threading.Event = field(init=False, default_factory=threading.Event)
    _stop: threading.Event = field(init=False, default_factory=threading.Event)
    _samples: deque[float] = field(init=False, default_factory=lambda: deque(maxlen=10000))
    _samples_lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _ble_error: Exception | None = field(init=False, default=None)
    _packet_count: int = field(init=False, default=0)
    _last_packet_ts: float = field(init=False, default=0.0)

    @classmethod
    def default(cls):
        return cls(
            uid="th21a_eeg_001",
            name="TH21A_EEG",
            type="EEG",
            channels=1,
            sample_rate=120,
            channel_labels=["EEG_RAW_ADC"],
        )

    def connect(self):
        self._connected.clear()
        self._stop.clear()
        self._ble_error = None
        self._packet_count = 0
        self._last_packet_ts = 0.0

        self._thread = threading.Thread(target=self._ble_thread_main, daemon=True)
        self._thread.start()

        if not self._connected.wait(timeout=self.connect_timeout_s):
            self._stop.set()
            raise RuntimeError(
                "TH21A BLE sensor did not connect/subscribe in time. "
                "Check power, pairing, and Bluetooth range."
            )

    def read_sample(self) -> list[float] | None:
        if self._ble_error is not None:
            raise RuntimeError(f"BLE reader failed: {self._ble_error}") from self._ble_error

        with self._samples_lock:
            if not self._samples:
                return None
            value = self._samples.popleft()
        return [value]

    def disconnect(self):
        self._stop.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _ble_thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ble_worker())
        except Exception as e:
            self._ble_error = e
            self._connected.set()
        finally:
            self._loop.close()

    async def _ble_worker(self):
        target = await resolve_device(self.address)

        kwargs = {"timeout": 30.0}
        try:
            kwargs["winrt"] = {"use_cached_services": False}
            client = BleakClient(target, **kwargs)
        except TypeError:
            kwargs.pop("winrt", None)
            client = BleakClient(target, **kwargs)

        async with client:
            await pair_with_best_effort(client)
            await asyncio.sleep(2.0)
            await ensure_services_resolved(client)

            await client.start_notify(self.notify_uuid, self._on_notify)
            self._connected.set()

            started = time.monotonic()
            self._last_packet_ts = started
            next_diag = started + 5.0

            if self.kick_on_connect:
                await self._kick_stream(client)

            while not self._stop.is_set():
                now = time.monotonic()

                if now >= next_diag:
                    silence = now - self._last_packet_ts
                    if self._packet_count == 0:
                        print(f"[{self.name}] Awaiting data... no packets yet ({silence:.1f}s)")
                    else:
                        print(f"[{self.name}] packets={self._packet_count} silence={silence:.1f}s")
                    next_diag = now + 5.0

                # If stream goes silent, retry notify + kick sequence without restarting the process.
                if now - self._last_packet_ts >= 8.0:
                    await self._recover_stream(client)
                    self._last_packet_ts = time.monotonic()

                await asyncio.sleep(0.1)

            try:
                await client.stop_notify(self.notify_uuid)
            except Exception:
                pass

    def _on_notify(self, _sender, data: bytes):
        samples = parse_eeg_packet(data)
        if not samples:
            return

        self._packet_count += 1
        self._last_packet_ts = time.monotonic()
        with self._samples_lock:
            for _idx, raw in samples:
                self._samples.append(float(raw))

    async def _kick_stream(self, client: BleakClient):
        for payload in STREAM_KICK_CANDIDATES:
            for response in (False, True):
                if self._stop.is_set():
                    return
                try:
                    await client.write_gatt_char(self.write_uuid, payload, response=response)
                except Exception:
                    continue

    async def _recover_stream(self, client: BleakClient):
        try:
            await client.stop_notify(self.notify_uuid)
        except Exception:
            pass

        await asyncio.sleep(0.4)

        try:
            await client.start_notify(self.notify_uuid, self._on_notify)
        except Exception:
            return

        await self._kick_stream(client)


if __name__ == "__main__":
    SereniBrainBluetoothEEG.default().run()