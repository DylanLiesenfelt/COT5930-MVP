"""
Tests whether a START command to the write characteristic triggers EEG streaming.
python cmdtest.py
"""
import asyncio
import time

from winsdk.windows.devices.bluetooth import BluetoothLEDevice, BluetoothConnectionStatus
from winsdk.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCommunicationStatus,
    GattSession,
    GattWriteOption,
)
from winsdk.windows.storage.streams import DataReader, DataWriter, ByteOrder

MAC          = "CB:68:60:DA:76:05"
NOTIFY_UUID  = "8653000b-43e6-47b7-9cb0-5fc21d4ae340"
WRITE_UUID   = "8653000c-43e6-47b7-9cb0-5fc21d4ae340"

def mac_to_int(mac):
    return int(mac.replace(":", ""), 16)

def buf_to_bytes(buf):
    reader = DataReader.from_buffer(buf)
    reader.byte_order = ByteOrder.LITTLE_ENDIAN
    return bytes(reader.read_bytes(buf.length))

def bytes_to_buf(data: bytes):
    writer = DataWriter()
    writer.write_bytes(data)
    return writer.detach_buffer()

fired = []

async def main():
    loop = asyncio.get_running_loop()

    print(f"Connecting to {MAC}...")
    device = await BluetoothLEDevice.from_bluetooth_address_async(mac_to_int(MAC))
    print(f"  Name: {device.name}  paired={device.device_information.pairing.is_paired}")

    session = await GattSession.from_device_id_async(device.bluetooth_device_id)
    session.maintain_connection = True

    for _ in range(75):
        if device.connection_status == BluetoothConnectionStatus.CONNECTED:
            break
        await asyncio.sleep(0.2)
    print(f"  Connected: {device.connection_status == BluetoothConnectionStatus.CONNECTED}")
    await asyncio.sleep(1.6)

    # Find both characteristics
    r = await device.get_gatt_services_async()
    eeg = write_char = None
    for svc in r.services:
        cr = await svc.get_characteristics_async()
        for c in cr.characteristics:
            uuid = str(c.uuid).lower()
            if uuid == NOTIFY_UUID.lower():
                eeg = c
            if uuid == WRITE_UUID.lower():
                write_char = c

    print(f"  EEG char found:   {eeg is not None}")
    print(f"  Write char found: {write_char is not None}")

    # Subscribe to EEG notifications
    def on_notify(char, args):
        try:
            data = buf_to_bytes(args.characteristic_value)
            fired.append(data)
            print(f"  [DATA!] {len(data)}B: {data[:12].hex()}")
        except Exception as e:
            print(f"  [ERR] {e}")

    eeg.add_value_changed(on_notify)
    r = await eeg.write_client_characteristic_configuration_descriptor_async(
        GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
    )
    print(f"\nCCCD write: {r}  readback: {(await eeg.read_client_characteristic_configuration_descriptor_async()).client_characteristic_configuration_descriptor}")

    # Commands to try on the write characteristic
    commands = [
        ("DATA ch=01 type=01 (start ch1)",  bytes.fromhex("4441544100010001")),
        ("DATA ch=02 type=01 (start ch2)",  bytes.fromhex("4441544100020001")),
        ("DATA ch=00 type=01 (start all)",  bytes.fromhex("4441544100000001")),
        ("DATA ch=01 type=01 padded",       bytes.fromhex("44415441000100010000000000000000")),
        ("single byte 0x01",                bytes([0x01])),
        ("single byte 0x02",                bytes([0x02])),
        ("single byte 0x07",                bytes([0x07])),
        ("0x00 0x01",                       bytes([0x00, 0x01])),
    ]

    if not write_char:
        print("\n[ERR] No write characteristic found, cannot send commands")
        session.close(); device.close()
        return

    print(f"\nTrying {len(commands)} start commands on write characteristic...")
    print("Watching for data after each...\n")

    for label, cmd in commands:
        if fired:
            print(f"\n*** DATA FLOWING after previous command! ***")
            break

        print(f"  Sending: {label}  ({cmd.hex()})")
        try:
            # Try write with response first
            wr = await write_char.write_value_with_result_async(
                bytes_to_buf(cmd),
                GattWriteOption.WRITE_WITH_RESPONSE
            )
            print(f"    write_with_response: {wr.status}")
        except Exception as e:
            print(f"    write_with_response err: {e}")
            try:
                wr = await write_char.write_value_with_result_async(
                    bytes_to_buf(cmd),
                    GattWriteOption.WRITE_WITHOUT_RESPONSE
                )
                print(f"    write_without_response: {wr.status}")
            except Exception as e2:
                print(f"    write_without_response err: {e2}")

        await asyncio.sleep(2.0)
        print(f"    data received so far: {len(fired)}")

    print(f"\nTotal data packets received: {len(fired)}")
    if not fired:
        print("No data from any command.")
        print("The device may need a completely different protocol to start streaming.")

    session.close()
    device.close()

asyncio.run(main())
