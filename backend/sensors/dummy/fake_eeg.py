"""
Dummy EEG Sensor

Generates synthetic 8-channel EEG data with realistic frequency components
(delta, theta, alpha, beta) for testing the pipeline and derived sensors.
"""

import numpy as np
import random
from dataclasses import dataclass, field
from sensors.sensor import DummySensor

# Standard 10-20 montage subset
EEG_CHANNELS = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "O1", "O2"]


@dataclass
class FakeEEG(DummySensor):
    """
    Generates synthetic multi-channel EEG with mixed frequency bands.

    The signal is a sum of sinusoids at delta (1-4 Hz), theta (4-8 Hz),
    alpha (8-12 Hz), and beta (12-30 Hz) with per-channel amplitude
    variation and additive Gaussian noise.  Occipital channels (O1, O2)
    get stronger alpha to mimic eyes-closed resting state.
    """

    noise_level: float = 0.5
    _t: float = field(init=False, default=0.0)

    @classmethod
    def default(cls):
        return cls(
            uid="fake_eeg_001",
            name="FakeEEG",
            type="EEG",
            channels=len(EEG_CHANNELS),
            sample_rate=256,
            channel_labels=EEG_CHANNELS,
        )

    # Per-band base amplitudes (µV-ish scale)
    _band_amps: dict = field(init=False, default_factory=lambda: {
        "delta": 20.0,   # 1-4 Hz
        "theta": 10.0,   # 4-8 Hz
        "alpha": 15.0,   # 8-12 Hz
        "beta":  5.0,    # 12-30 Hz
    })

    def generate_sample(self) -> list[float]:
        self._t += 1.0 / self.sample_rate
        sample = []

        for i in range(self.channels):
            # Alpha boost for occipital channels (indices 6, 7 = O1, O2)
            alpha_scale = 2.5 if i >= 6 else 1.0

            value = (
                self._band_amps["delta"] * np.sin(2 * np.pi * 2.0  * self._t + i)
              + self._band_amps["theta"] * np.sin(2 * np.pi * 6.0  * self._t + i * 0.7)
              + self._band_amps["alpha"] * np.sin(2 * np.pi * 10.0 * self._t + i * 1.3) * alpha_scale
              + self._band_amps["beta"]  * np.sin(2 * np.pi * 20.0 * self._t + i * 0.4)
              + random.gauss(0, self.noise_level)
            )
            sample.append(float(value))

        return sample


if __name__ == "__main__":
    eeg = FakeEEG.default()
    eeg.run()
