"""
USB Sensor Template

Copy into backend/sensors/physical/ and rename the class/file.
Implement connect/read_sample/disconnect for your USB or serial device.
"""

from dataclasses import dataclass
from sensors.sensor import USBPhysicalSensor


@dataclass
class MyUSBSensor(USBPhysicalSensor):  # rename
    port: str = "COM3"
    baud: int = 115200

    @classmethod
    def default(cls):
        return cls(
            uid="my_usb_sensor_001",
            name="MyUSBSensor",
            type="EEG",
            channels=1,
            sample_rate=250,
            port="COM3",
            baud=115200,
        )

    def connect(self):
        # Example:
        # import serial
        # self._dev = serial.Serial(self.port, self.baud, timeout=1)
        raise NotImplementedError("Implement connect() for your USB/serial device")

    def read_sample(self) -> list[float] | None:
        # Return a single sample with exactly `channels` floats, or None.
        raise NotImplementedError("Implement read_sample() for your USB/serial device")

    def disconnect(self):
        # Close USB/serial handle if needed.
        pass


if __name__ == "__main__":
    sensor = MyUSBSensor.default()
    sensor.run()
