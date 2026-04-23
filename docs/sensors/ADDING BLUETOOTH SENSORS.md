# Bluetooth Sensor Quickstart

This quickstart standardizes Bluetooth/BLE integrations in ECHO.

## 1. Create the sensor file

Copy the Bluetooth template into the physical sensor package and rename it:

- Source template: `backend/sensors/templates/bluetooth_sensor_template.py`
- Destination example: `backend/sensors/physical/my_ble_eeg.py`

## 2. Use the Bluetooth base class

Your class must inherit from `BluetoothPhysicalSensor`:

```python
from sensors.sensor import BluetoothPhysicalSensor
```

Implement these hooks:

- `connect()`
- `read_sample()`
- `disconnect()`

## 3. BLE workflow

Typical BLE flow:

1. Scan for device (name or address)
2. Connect to device
3. Subscribe to notify characteristic
4. Decode payload into float sample values
5. Return one sample at a time from `read_sample()`

## 4. Add a default launcher

Add a `default()` classmethod so `start_all_sensors.py` can launch the sensor.

```python
@classmethod
def default(cls):
    return cls(
        uid="my_ble_001",
        name="MyBLEEEG",
        type="EEG",
        channels=4,
        sample_rate=128,
    )
```

## 5. Launch and verify

From `backend/`:

```bash
python sensors/start_all_sensors.py
```

Verify your sensor appears as `[PHYSICAL]` and starts `Streaming`.

## 6. Common Bluetooth notes

- Many devices allow only one active connection at a time.
- Disconnect phone apps while testing on desktop.
- BLE addresses may rotate; name-based fallback is often needed.
- If notifications require a start command, write to a control characteristic in `connect()`.
