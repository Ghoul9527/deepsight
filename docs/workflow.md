# Development Workflow

## Daily Development Loop

```bash
source .venv/bin/activate
deepsight-cli start --mock
# Develop, test, iterate...
deepsight-cli test
```

## Adding a New Sensor Driver (Pico)

1. Create `lib/new_sensor.py` with ABC pattern
2. Implement `MockNewSensor` with simulated data
3. Implement `RealNewSensor` (later, with hardware)
4. Factory function selects based on `config.MOCK_ENABLED`
5. Add to `ControlLoop.__init__()`
6. Add telemetry output in `telemetry.py`

## Adding a New Message Type

1. Add type string to `KNOWN_TYPES` in `shared/src/deepsight_shared/protocol.py`
2. Add factory function in protocol.py
3. Add JSON schema in schemas.py
4. Add handler in command_parser / message_router

## Adding a New Tracking Mode

1. Create `host/src/deepsight_host/tracking/new_mode.py`
2. Subclass `TrackingEngine`, implement `process_frame()`
3. Register: `register_tracker("new_mode", NewModeTracker)`
4. Add to UI dropdown in `tracking_view.py`

## Code Quality

```bash
make lint  # ruff + mypy
make test  # pytest
```

## Git Workflow

- Feature branches off `main`
- PR with description of changes
- Test before merge
- Squash merge to keep history clean
