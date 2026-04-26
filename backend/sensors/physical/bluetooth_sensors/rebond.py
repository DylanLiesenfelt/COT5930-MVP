"""
Clears stale Windows bond and re-pairs fresh with the headband.
Run this ONCE, then run client.py normally.

python rebond.py
"""
import asyncio
import time

from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
from winsdk.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCommunicationStatus,
    GattSession,
)
from winsdk.windows.devices.enumeration import (
    DevicePairingKinds,
    DevicePairingResultStatus,
    DeviceUnpairingResultStatus,
)
from winsdk.windows.storage.streams import DataReader, ByteOrder

MAC = "CB:68:60:DA:76:05"

def mac_to_int(mac):
    return int(mac.replace(":", ""), 16)

def buf_to_bytes(buf):
    reader = DataReader.from_buffer(buf)
    reader.byte_order = ByteOrder.LITTLE_ENDIAN
    return bytes(reader.read_bytes(buf.length))

fired = []

async def main():
    loop = asyncio.get_running_loop()

    print(f"Getting device {MAC}...")
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(MAC))
    if not device:
        print("[ERR] Device not found - is it powered on?")
        return

    print(f"  Name:      {device.name}")
    pairing = device.device_information.pairing
    print(f"  is_paired: {pairing.is_paired}")
    print(f"  can_pair:  {pairing.can_pair}")
    print(f"  protection:{pairing.protection_level}")

    # ── Step 1: Unpair to clear stale bond keys ────────────────────────────────
    if pairing.is_paired:
        print("\nUnpairing (clearing stale bond keys)...")
        unpair_result = await pairing.unpair_async()
        print(f"  Unpair status: {unpair_result.status}")
        if unpair_result.status != DeviceUnpairingResultStatus.UNPAIRED:
            print(f"  [WARN] Unpair may not have fully succeeded: {unpair_result.status}")
        else:
            print("  Unpaired OK.")
        await asyncio.sleep(2.0)
    else:
        print("\nNot paired — skipping unpair.")

    # Re-fetch device after unpair
    device.close()
    await asyncio.sleep(1.0)
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(MAC))
    if not device:
        print("[ERR] Device gone after unpair - power cycle it and retry")
        return
    pairing = device.device_information.pairing
    print(f"\nAfter unpair: is_paired={pairing.is_paired}  can_pair={pairing.can_pair}")

    # ── Step 2: Fresh pair with CONFIRM_ONLY (Just Works / CONSENT) ────────────
    print("\nPairing fresh (Just Works - no PIN)...")
    custom = pairing.custom

    def on_pairing_requested(sender, args):
        print(f"  Pairing requested: kind={args.pairing_kind}  -> accepting")
        args.accept()

    token = custom.add_pairing_requested(on_pairing_requested)
    pair_result = await custom.pair_async(DevicePairingKinds.CONFIRM_ONLY)
    custom.remove_pairing_requested(token)
    print(f"  Pair status: {pair_result.status}")

    if pair_result.status not in (
        DevicePairingResultStatus.PAIRED,
        DevicePairingResultStatus.ALREADY_PAIRED,
    ):
        print(f"[ERR] Pairing failed: {pair_result.status}")
        print("  Try power-cycling the headband and running this script again.")
        device.close()
        return

    print("  Paired successfully!")
    await asyncio.sleep(2.0)

    # ── Step 3: Connect and verify notifications now work ──────────────────────
    print("\nOpening GattSession...")
    session = await GattSession.from_device_id_async(device.bluetooth_device_id)
    session.maintain_connection = True

    print("Waiting for connection...")
    for _ in range(75):
        if device.connection_status == BluetoothConnectionStatus.CONNECTED:
            break
        await asyncio.sleep(0.2)
    print(f"  Status: {device.connection_status}  (1=connected)")

    await asyncio.sleep(1.6)

    # Find EEG characteristic
    NOTIFY_UUID = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"
    r = await device.get_gatt_services_async()
    eeg = None
    for svc in r.services:
        cr = await svc.get_characteristics_async()
        for c in cr.characteristics:
            if str(c.uuid).lower() == NOTIFY_UUID.lower():
                eeg = c

    if not eeg:
        print("[ERR] EEG char not found")
        session.close(); device.close()
        return

    def on_notify(char, args):
        try:
            data = buf_to_bytes(args.characteristic_value)
            fired.append(data)
            print(f"  [DATA] {len(data)}B: {data[:8].hex()}")
        except Exception as e:
            print(f"  [ERR] {e}")

    eeg.add_value_changed(on_notify)

    result = await eeg.write_client_characteristic_configuration_descriptor_async(
        GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
    )
    print(f"\nCCCD write: {result}  (0=success)")

    rb = await eeg.read_client_characteristic_configuration_descriptor_async()
    print(f"CCCD readback: {rb.client_characteristic_configuration_descriptor}  (1=notify on)")

    print("\nWaiting 10s for data...")
    await asyncio.sleep(10.0)

    print(f"\nCallbacks fired: {len(fired)}")
    if fired:
        print("SUCCESS - notifications working! Now run client.py normally.")
    else:
        print("Still no data.")
        print("The device may have its own bond stored that conflicts.")
        print("Try: power off the headband, wait 10s, power back on, run this script again.")

    session.close()
    device.close()

asyncio.run(main())
