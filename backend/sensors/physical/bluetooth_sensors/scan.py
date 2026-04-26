import asyncio 
from bleak import BleakScanner, BleakClient

async def scan():
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)

    for address, (device, adv_data) in devices.items():
        print("------------------------------------------------\n")
        print(device.name, address)
        print("RSSI:", adv_data.rssi)
        print("TX Power:", adv_data.tx_power)
        print("Service UUIDs:", adv_data.service_uuids)
        print("Manufacturer Data:", adv_data.manufacturer_data)
        print("Platform Data:", adv_data.platform_data)
        print("Fields:", adv_data._fields)
        print("default fields:", adv_data._field_defaults)
        print("Service Data:", adv_data.service_data)
        print("Local Name:", adv_data.local_name)       

asyncio.run(scan())