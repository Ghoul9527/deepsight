# Hardware Integration Guide

## Mock → Real Migration Strategy

Every hardware interface uses the ABC (Abstract Base Class) pattern:

```python
class SensorDriver(ABC):
    @abstractmethod
    def read(self) -> DataType: ...

class MockSensor(SensorDriver):
    def read(self) -> DataType:
        return simulated_data()

class RealSensor(SensorDriver):
    def read(self) -> DataType:
        return read_from_i2c_device()

def create_sensor() -> SensorDriver:
    if config.MOCK_ENABLED:
        return MockSensor()
    return RealSensor()
```

## Migration Order

### Phase 3a: Servo Control
- Swap PCA9685 driver for mock servo
- Verify PWM output with oscilloscope
- Test servo range calibration

### Phase 3b: Sensors
- MPU6050 IMU → verify orientation data
- MS5837 pressure → verify depth calculation
- BME280 → verify environment readings

### Phase 3c: GoPro Control
- Enable USB control in config
- Test record start/stop
- Test mode switching

### Phase 3d: HDMI Capture
- Connect HDMI capture dongle
- Verify frame capture
- Tune encoding pipeline

### Phase 3e: Winch Motor
- Connect motor controller
- Verify limit switches
- Test emergency stop
- Tune PID gains

## Config Changes

For each device, change one line in the config:

```yaml
# From:
servo:
  mock: true

# To:
servo:
  mock: false
  i2c_address: 0x40
```

No code changes needed. The factory functions handle the switchover.
