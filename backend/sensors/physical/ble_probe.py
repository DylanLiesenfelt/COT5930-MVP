"""
BLE Probe Utility

Use this to discover BLE devices and inspect characteristics before wiring a
new physical BLE sensor.

Examples:
  python sensors/physical/ble_probe.py --scan
  python sensors/physical/ble_probe.py --name SereniBrain --services
  python sensors/physical/ble_probe.py --address AA:BB:CC:DD:EE:FF --services
"""

from __future__ import annotations

import argparse
import asyncio

try:
    from bleak import BleakClient, BleakScanner
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "bleak is required for BLE probing. Run: pip install -r backend/requirements.txt"
    ) from exc


async def scan(timeout: float):
    devices = await BleakScanner.discover(timeout=timeout)
    if not devices:
        print("No BLE devices discovered.")
        return

    print(f"Discovered {len(devices)} BLE device(s):")
    for dev in devices:
        print(f"  - {dev.name or '<unknown>'} [{dev.address}]")


def _match_device(devices, name_hint: str, address: str):
    if address:
        for dev in devices:
            if dev.address.lower() == address.lower():
                return dev
        return None

    hint = name_hint.lower()
    for dev in devices:
        if dev.name and hint in dev.name.lower():
            return dev
    return None


async def show_services(name_hint: str, address: str, timeout: float):
    devices = await BleakScanner.discover(timeout=timeout)
    target = _match_device(devices, name_hint=name_hint, address=address)

    if not target:
        print("Target BLE device not found.")
        print("Tip: run with --scan first and provide --address for reliability.")
        return

    print(f"Connecting to {target.name or '<unknown>'} [{target.address}]...")
    async with BleakClient(target.address) as client:
        svcs = None
        # Bleak API differs by version:
        # - older: await client.get_services()
        # - newer: client.services (populated after connect)
        if hasattr(client, "get_services"):
            svcs = await client.get_services()
        else:
            svcs = client.services

        if svcs is None:
            print("No GATT services available from device.")
            return

        print("Services and characteristics:")
        for svc in svcs:
            print(f"  Service: {svc.uuid}")
            for ch in svc.characteristics:
                props = ", ".join(ch.properties)
                print(f"    Char: {ch.uuid} | props: {props}")


def parse_args():
    p = argparse.ArgumentParser(description="Probe BLE devices/services")
    p.add_argument("--scan", action="store_true", help="Scan nearby BLE devices")
    p.add_argument("--services", action="store_true", help="Inspect services/characteristics")
    p.add_argument("--name", default="SereniBrain", help="Name hint for selecting device")
    p.add_argument("--address", default="", help="Exact BLE address (preferred)")
    p.add_argument("--timeout", type=float, default=8.0, help="Scan timeout seconds")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.scan and not args.services:
        args.scan = True

    if args.scan:
        asyncio.run(scan(args.timeout))

    if args.services:
        asyncio.run(show_services(args.name, args.address, args.timeout))


if __name__ == "__main__":
    main()
