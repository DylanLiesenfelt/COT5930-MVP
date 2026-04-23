"""
Bluetooth Sensor Template

Copy into backend/sensors/physical/ and rename the class/file.
Implement connect/read_sample/disconnect for your BLE/Bluetooth device.
"""

from dataclasses import dataclass, field

from sensors.sensor import BluetoothPhysicalSensor


@dataclass
class MyBluetoothSensor(BluetoothPhysicalSensor):  # rename
    address: str = ""
    notify_char_uuid: str = ""

    _latest: list[float] | None = field(init=False, default=None)

    @classmethod
    def default(cls):
        return cls(
            uid="my_ble_sensor_001",
            name="MyBluetoothSensor",
            type="EEG",
            channels=1,
            sample_rate=128,
            address="",
            notify_char_uuid="",
        )

    def connect(self):
        # Typical flow:
        # 1) Connect via bleak/device SDK
        # 2) Subscribe to notifications
        # 3) Save incoming parsed sample to self._latest
        raise NotImplementedError("Implement connect() for your Bluetooth device")

    def read_sample(self) -> list[float] | None:
        sample = self._latest
        self._latest = None
        return sample

    def disconnect(self):
        # Disconnect Bluetooth client/session.
        pass


if __name__ == "__main__":
    sensor = MyBluetoothSensor.default()
    sensor.run()
