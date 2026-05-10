"""Deterministic realtime control loop — 50 Hz."""

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
        print("[PICO] All drivers initialized")

    def run(self):
        self._running = True
        last_time = time.time()

        print(f"[PICO] Control loop started @ {config.CONTROL_LOOP_HZ} Hz")

        while self._running:
            now = time.time()
            dt = now - last_time
            if dt < config.CONTROL_LOOP_DT:
                time.sleep(config.CONTROL_LOOP_DT - dt)
                now = time.time()
                dt = config.CONTROL_LOOP_DT
            last_time = now

            self._step(dt)

    def _step(self, dt: float):
        # Read incoming commands
        line = self._serial.read_line()
        if line:
            parsed = self._parser.parse(line)
            if parsed:
                cmd_type, payload = parsed
                self._parser.dispatch(cmd_type, payload)

        # Safety check
        if self._safety.check():
            defaults = self._safety.get_default_angles()
            for i, angle in enumerate(defaults):
                self.servo.set_angle(i, angle)

        # Read sensors (every other tick = 25 Hz per sensor group)
        self._telemetry_counter += 1
        self._heartbeat_counter += 1

        if self._telemetry_counter >= 2:
            self._telemetry_counter = 0
            self._send_telemetry()

        if self._heartbeat_counter >= 25:  # ~1 Hz heartbeat
            self._heartbeat_counter = 0
            self._serial.write(telemetry.tel_heartbeat())

    def _send_telemetry(self):
        # IMU
        yaw, pitch, roll, ax, ay, az = self.imu.read()
        self._serial.write(telemetry.tel_imu(yaw, pitch, roll, ax, ay, az))

        # Depth
        depth_m, pressure_mbar, temp_c = self.pressure.read()
        self._serial.write(telemetry.tel_depth(depth_m, pressure_mbar, temp_c))

        # Environment
        env_temp, humidity, pressure_hpa = self.bme280.read()
        self._serial.write(telemetry.tel_env(env_temp, humidity, pressure_hpa))

        # Leak
        for ch in range(4):
            wet = self.leak.is_wet(ch)
            self._serial.write(telemetry.tel_leak(ch, wet))

    def stop(self):
        self._running = False
