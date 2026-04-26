"""
Minimal test - just checks if value_changed fires at all.
python rawtest.py
"""
import asyncio
import threading
import time

from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
from winsdk.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCommunicationStatus,
    GattSession,
)
from winsdk.windows.storage.streams import DataReader, ByteOrder

MAC         = "CB:68:60:DA:76:05"
NOTIFY_UUID = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"

def mac_to_int(mac):
    return int(mac.replace(":", ""), 16)

def buf_to_bytes(buf):
    reader = DataReader.from_buffer(buf)
    reader.byte_order = ByteOrder.LITTLE_ENDIAN
    return bytes(reader.read_bytes(buf.length))

# Shared state - no asyncio involved, just raw threading
fired = []
fire_lock = threading.Lock()

def on_value_changed(char, args):
    try:
        data = buf_to_bytes(args.characteristic_value)
        with fire_lock:
            fired.append(data)
        print(f"[CALLBACK FIRED] thread={threading.current_thread().name} len={len(data)} hex={data[:8].hex()}")
    except Exception as e:
        print(f"[CALLBACK ERR] {e}")

async def main():
    print(f"Connecting to {MAC}...")
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(MAC))
    print(f"  Name: {device.name}  status={device.connection_status}")

    session = await GattSession.from_device_id_async(device.bluetooth_device_id)
    session.maintain_connection = True

    # Wait for connection
    for _ in range(75):
        if device.connection_status == BluetoothConnectionStatus.CONNECTED:
            break
        await asyncio.sleep(0.2)
    print(f"  After wait: status={device.connection_status}")

    await asyncio.sleep(1.6)

    # Get characteristic
    r = await device.get_gatt_services_async()
    eeg = None
    for svc in r.services:
        cr = await svc.get_characteristics_async()
        for c in cr.characteristics:
            if str(c.uuid).lower() == NOTIFY_UUID.lower():
                eeg = c
                break

    if not eeg:
        print("[ERR] characteristic not found")
        return

    print(f"Found EEG char: {eeg.uuid}")
    print(f"Properties: {eeg.characteristic_properties}")

    # Register callback BEFORE writing CCCD
    token = eeg.add_value_changed(on_value_changed)
    print(f"Registered callback, token={token}")

    # Write CCCD
    result = await eeg.write_client_characteristic_configuration_descriptor_async(
        GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
    )
    print(f"CCCD write: {result}")

    readback = await eeg.read_client_characteristic_configuration_descriptor_async()
    print(f"CCCD readback: {readback.client_characteristic_configuration_descriptor}")

    # Now just block the thread for 15 seconds and see if callback fires
    print(f"\nWaiting 15s on main thread. Callback fires on WinRT thread directly.")
    print(f"Watch for [CALLBACK FIRED] lines...\n")
    
    start = time.time()
    while time.time() - start < 15:
        await asyncio.sleep(0.5)
        with fire_lock:
            n = len(fired)
        if n > 0:
            print(f"  fired count so far: {n}")

    with fire_lock:
        total = len(fired)
    print(f"\nDone. Total callbacks fired: {total}")

    if total == 0:
        print("\nCallback NEVER fired despite CCCD=1.")
        print("This means WinRT is not delivering notifications to this process.")
        print()
        print("Possible reasons:")
        print("  1. Device only streams when worn (electrodes need skin contact)")
        print("  2. WinRT notification delivery requires a different session setup")
        print("  3. The characteristic requires a specific write command first")
        print()
        # Try a manual read to see if data is there
        print("Attempting manual read of the characteristic value...")
        try:
            read_result = await eeg.read_value_async(
                # 0 = BluetoothCacheMode.Uncached
                0
            )
            if read_result.status == GattCommunicationStatus.SUCCESS:
                data = buf_to_bytes(read_result.value)
                print(f"  Manual read: {len(data)}B: {data.hex()}")
            else:
                print(f"  Manual read failed: {read_result.status}")
                print("  (Notify-only characteristics can't be read - this is normal)")
        except Exception as e:
            print(f"  Manual read exception: {e}")

    session.close()
    device.close()

asyncio.run(main())
