"""
Run this first to show exactly what winsdk APIs are available.
python diag.py
"""
import asyncio

def mac_to_int(mac: str) -> int:
    return int(mac.replace(":", ""), 16)

MAC = "CB:68:60:DA:76:05"

async def main():
    # ── Check winsdk ──────────────────────────────────────────────────────────
    try:
        from winsdk.windows.devices.bluetooth import BluetoothLEDevice
        print("[OK] winsdk imported")
    except ImportError:
        print("[ERR] winsdk not installed. Run: pip install winsdk")
        return

    from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
    from winsdk.windows.devices.bluetooth.genericattributeprofile import (
        GattCommunicationStatus,
        GattClientCharacteristicConfigurationDescriptorValue,
    )
    from winsdk.windows.storage.streams import DataReader, ByteOrder

    # ── Connect ───────────────────────────────────────────────────────────────
    print(f"\nConnecting to {MAC}...")
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(MAC))
    if not device:
        print("[ERR] Could not connect")
        return
    print(f"  Name: {device.name}")
    print(f"  Connection: {device.connection_status}")

    # ── Pairing info ──────────────────────────────────────────────────────────
    pairing = device.device_information.pairing
    print(f"\nPairing info:")
    print(f"  is_paired:    {pairing.is_paired}")
    print(f"  can_pair:     {pairing.can_pair}")
    print(f"  protection:   {pairing.protection_level}")

    # ── Dump pairing custom methods ───────────────────────────────────────────
    custom = pairing.custom
    print(f"\npairing.custom methods:")
    for m in sorted(dir(custom)):
        if not m.startswith('_'):
            print(f"  {m}")

    # ── List DevicePairingKinds values ────────────────────────────────────────
    try:
        from winsdk.windows.devices.enumeration import DevicePairingKinds
        print(f"\nDevicePairingKinds values:")
        for m in sorted(dir(DevicePairingKinds)):
            if not m.startswith('_'):
                print(f"  {m} = {getattr(DevicePairingKinds, m)}")
    except Exception as e:
        print(f"  DevicePairingKinds error: {e}")

    # ── Find EEG char and dump its methods ────────────────────────────────────
    NOTIFY_UUID = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"
    print(f"\nGetting services...")
    svc_result = await device.get_gatt_services_async()
    print(f"  status: {svc_result.status}")
    
    eeg_char = None
    for svc in svc_result.services:
        chars = await svc.get_characteristics_async()
        for c in chars.characteristics:
            uuid = str(c.uuid).lower()
            print(f"  char: {uuid}")
            if uuid == NOTIFY_UUID.lower():
                eeg_char = c

    if eeg_char:
        print(f"\nEEG char methods:")
        for m in sorted(dir(eeg_char)):
            if not m.startswith('_') and ('descriptor' in m.lower() or 'notify' in m.lower() or 'write' in m.lower() or 'value' in m.lower()):
                print(f"  {m}")

    device.close()

asyncio.run(main())
