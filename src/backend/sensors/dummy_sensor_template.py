"""
Dummy Sensor Template

Copy this file into the dummy/ folder and rename it.
Rename the class, then fill in generate_sample() with your fake data.
"""

from dataclasses import dataclass
from sensors.sensor import DummySensor


@dataclass
class MyDummySensor(DummySensor):  # ← rename this
    """Describe what this sensor fakes."""

    # Add any settings you need (optional)
    # noise_level: float = 0.1

    def generate_sample(self) -> list[float]:
        """
        Return one fake sample as a list of numbers.
        Must have exactly as many values as your 'channels' setting.
        """
        pass  # ← replace with your fake data


# ── To start the sensor ─────────────────────────────────────
#
#   sensor = MyDummySensor(
#       uid="",
#       name="",
#       type="",
#       channels=0,
#       sample_rate=0,
#   )
#   sensor.start()
