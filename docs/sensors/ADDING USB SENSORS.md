# USB Sensor Quickstart

This quickstart standardizes USB/serial device integrations in ECHO.

## 1. Create the sensor file

Copy the USB template into the physical sensor package and rename it:

- Source template: `backend/sensors/templates/usb_sensor_template.py`
- Destination example: `backend/sensors/physical/my_usb_eeg.py`

## 2. Use the USB base class

Your class must inherit from `USBPhysicalSensor`:

```python
from sensors.sensor import USBPhysicalSensor
```

Implement these hooks:

- `connect()`
- `read_sample()`
- `disconnect()` (optional but recommended)

## 3. Define stream metadata

Set these correctly in your constructor/default:

- `uid` unique instance id
- `name` human-readable stream name
- `type` signal family (EEG, ECG, etc.)
- `channels` values per sample
- `sample_rate` Hz
- `channel_labels` optional explicit labels

## 4. Add a default launcher

Add a `default()` classmethod so `start_all_sensors.py` auto-discovers the sensor.

```python
@classmethod
def default(cls):
    return cls(
        uid="my_usb_001",
        name="MyUSBSensor",
        type="EEG",
        channels=4,
        sample_rate=250,
    )
```

## 5. Launch and verify

From `backend/`:

```bash
python sensors/start_all_sensors.py
```

Verify your sensor appears as `[PHYSICAL]` and transitions to `Streaming`.

## 6. Common USB notes

- Serial devices may need port auto-detection or explicit COM port config.
- Skip malformed lines in `read_sample()` instead of crashing.
- Return `None` when no sample is available yet.
- Always ensure sample length matches `channels`.
