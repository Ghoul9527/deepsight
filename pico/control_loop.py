"""Deterministic realtime control loop - 50 Hz."""

import time

import config
from lib.servo import create_servo_driver
from lib.imu import create_imu_driver
from lib.pressure import create_pressure_driver
from lib.bme280 import create_bme280_driver
from lib.leak_sensor import create_leak_sensor
from lib.lighting import create_lighting_driver
from serial_link import SerialLink
from command_parser import CommandParser
from safety import SafetyMonitor
import telemetry


class ControlLoop:
    def __init__(self, serial: SerialLink):
        self._serial = serial
        self._parser = CommandParser()
        self._safety = SafetyMonitor()

        # Drivers
        self.servo = create_servo_driver()
        self.imu = create_imu_driver()
        self.pressure = create_pressure_driver()
        self.bme280 = create_bme280_driver()
        self.leak = create_leak_sensor()
        self.lighting = create_lighting_driver()

        # State
        self._running = False
        self._telemetry_counter = 0
        self._heartbeat_counter = 0

        # Register command handlers
        self._parser.register("cmd.servo.set", self._handle_servo)
        self._parser.register("cmd.lighting.set", self._handle_lighting)

    def _handle_servo(self, payload: dict):
        servo_id = payload.get("servo_id", 0)
        angle = payload.get("angle", 90.0)
        self.servo.set_angle(servo_id, angle)
        self._safety.command_received()

    def _handle_lighting(self, payload: dict):
        channel = payload.get("channel", 0)
        brightness = payload.get("brightness", 0.0)
        self.lighting.set_brightness(channel, brightness)

    def init(self):
        self.servo.init()
        self.imu.init()
        self.pressure.init()
        self.bme280.init()
        self.leak.init()
        self.lighting.init()
        self._serial.init()
        self._serial.flush_input()  # discard startup noise
        print("[PICO] All drivers initialized")

    def run(self):
        self._running = True
        last_time = time.time()
        startup_ticks = 0  # grace period before reading UART

        print(f"[PICO] Control loop started @ {config.CONTROL_LOOP_HZ} Hz")

        while self._running:
            now = time.time()
            dt = now - last_time
            if dt < config.CONTROL_LOOP_DT:
                time.sleep(config.CONTROL_LOOP_DT - dt)
                now = time.time()
                dt = config.CONTROL_LOOP_DT
            last_time = now

            try:
                self._step(dt, startup_ticks)
            except Exception as e:
                print(f"[PICO] Step error: {e}")
            if startup_ticks < 250:  # ~5s grace period
                startup_ticks += 1

    def _step(self, dt: float, startup_ticks: int = 999):
        # Drain UART every tick to prevent RX buffer overflow.
        # Only process the LAST complete line; stale commands are discarded.
        last_line = None
        if config.ENABLE_UART_READ and startup_ticks >= 250:
            while True:
                line = self._serial.read_line()
                if line is None:
                    break
                last_line = line  # keep only the most recent command
        if last_line:
            parsed = self._parser.parse(last_line)
            if parsed:
                cmd_type, payload = parsed
                self._parser.dispatch(cmd_type, payload)

        # Safety check
        if self._safety.check():
            defaults = self._safety.get_default_angles()
            for i, angle in enumerate(defaults):
                self.servo.set_angle(i, angle)

        # Telemetry at 1 Hz (was 25 Hz - exceeded 115200 baud)
        self._telemetry_counter += 1
        self._heartbeat_counter += 1

        if self._telemetry_counter >= 50:  # 1 Hz (50 ticks x 20ms = 1s)
            self._telemetry_counter = 0
            self._send_telemetry()

        if self._heartbeat_counter >= 50:  # ~1 Hz heartbeat
            self._heartbeat_counter = 0
            self._serial.write(telemetry.tel_heartbeat())

    def _send_telemetry(self):
        # Combine all sensor data into a single message to minimize UART writes
        yaw, pitch, roll, ax, ay, az = self.imu.read()
        depth_m, pressure_mbar, temp_c = self.pressure.read()
        env_temp, humidity, pressure_hpa = self.bme280.read()
        leak_states = [self.leak.is_wet(ch) for ch in range(4)]

        msg = telemetry.make_telemetry("tel.sensors", {
            "yaw": yaw, "pitch": pitch, "roll": roll,
            "accel_x": ax, "accel_y": ay, "accel_z": az,
            "depth_m": depth_m, "pressure_mbar": pressure_mbar,
            "water_temp_c": temp_c,
            "env_temp_c": env_temp, "humidity_pct": humidity,
            "env_pressure_hpa": pressure_hpa,
            "leak": leak_states,
        })
        self._serial.write(msg)

    def stop(self):
        self._running = False
