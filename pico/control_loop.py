"""Deterministic realtime control loop - 50 Hz."""

import gc
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
        self._rx_line_count = 0
        self._rx_servo_count = 0
        self._last_servo_seq: dict[int, int] = {}  # servo_id -> last seq seen
        self._loop_count = 0
        self._last_loop_report = 0.0
        self._loop_hz = 0.0
        self._step_ms = 0
        self._sensor_ms = 0

        self._gc_counter = 0  # only gc.collect() every N iterations

        # Staggered sensor reads: read one sensor per tick to avoid I2C blocking
        self._sensor_phase = 0
        self._sensor_cache = {
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
            "ax": 0.0, "ay": 0.0, "az": 0.0,
            "depth_m": 0.0, "pressure_mbar": 0.0, "water_temp_c": 0.0,
            "env_temp_c": 0.0, "humidity_pct": 0.0, "env_pressure_hpa": 0.0,
            "leak": [False, False, False, False],
        }

        # Register command handlers
        self._parser.register("cmd.servo.set", self._handle_servo)
        self._parser.register("cmd.lighting.set", self._handle_lighting)
        self._parser.register("sys.heartbeat", self._handle_heartbeat)
        self._parser.register("tel.poll", self._handle_poll)

    def _handle_servo(self, payload: dict):
        servo_id = payload.get("servo_id", 0)
        angle = payload.get("angle", 90.0)
        self.servo.set_angle(servo_id, angle)
        self._safety.command_received()

    def _handle_heartbeat(self, _payload: dict):
        self._safety.command_received()

    def _handle_lighting(self, payload: dict):
        channel = payload.get("channel", 0)
        brightness = payload.get("brightness", 0.0)
        self.lighting.set_brightness(channel, brightness)

    def _handle_poll(self, _payload: dict):
        """Respond to Pi's telemetry poll with compact sensor snapshot."""
        s = self._sensor_cache
        msg = telemetry.make_telemetry("t", {
            "st": self._step_ms,
            "hz": round(self._loop_hz, 1),
            "rx": self._rx_line_count,
            "rs": self._rx_servo_count,
            "s0": self._last_servo_seq.get(0, 0),
            "s1": self._last_servo_seq.get(1, 0),
            "y": round(s["yaw"], 1),
            "p": round(s["pitch"], 1),
            "r": round(s["roll"], 1),
            "ax": round(s["ax"], 2),
            "ay": round(s["ay"], 2),
            "az": round(s["az"], 2),
            "d": round(s["depth_m"], 1),
            "pr": round(s["pressure_mbar"], 1),
            "wt": round(s["water_temp_c"], 1),
            "et": round(s["env_temp_c"], 1),
            "eh": round(s["humidity_pct"], 1),
            "ep": round(s["env_pressure_hpa"], 1),
            "le": s["leak"],
        })
        self._serial.write(msg)

    def init(self):
        print("[PICO] init servo...")
        self.servo.init()
        print("[PICO] init imu...")
        self.imu.init()
        print("[PICO] init pressure...")
        self.pressure.init()
        print("[PICO] init bme280...")
        self.bme280.init()
        print("[PICO] init leak...")
        self.leak.init()
        print("[PICO] init lighting...")
        self.lighting.init()
        print("[PICO] init serial...")
        self._serial.init()
        self._serial.flush_input()  # discard startup noise
        print("[PICO] All drivers initialized")

    def run(self):
        self._running = True
        last_time = time.time()
        last_ticks = time.ticks_us()  # µs counter for precise loop pacing
        startup_ticks = 0  # grace period before reading UART
        self._last_loop_report = time.time()
        self._loop_count = 0

        print(f"[PICO] Control loop started @ {config.CONTROL_LOOP_HZ} Hz")

        while self._running:
            now = time.time()
            self._loop_count += 1

            # Track actual loop rate (report every 5s)
            if now - self._last_loop_report >= 5.0:
                self._loop_hz = self._loop_count / (now - self._last_loop_report)
                self._loop_count = 0
                self._last_loop_report = now

            # Precise pacing via µs counter (time.time() resolution is ~10ms)
            dt = time.ticks_diff(time.ticks_us(), last_ticks) / 1000000.0
            if dt < config.CONTROL_LOOP_DT:
                time.sleep_us(int((config.CONTROL_LOOP_DT - dt) * 1000000))
                dt = config.CONTROL_LOOP_DT
            last_ticks = time.ticks_us()

            try:
                self._step(dt, now, startup_ticks)
            except Exception as e:
                print(f"[PICO] Step error: {e}")
            if startup_ticks < 250:  # ~5s grace period
                startup_ticks += 1

    def _step(self, dt: float, now: float, startup_ticks: int = 999):
        t0 = time.time()
        self._gc_counter += 1
        if self._gc_counter >= 50:
            gc.collect()
            self._gc_counter = 0

        # Drain commands FIRST — always process gamepad input before anything
        # that might block (telemetry write). Idempotent: only last of each
        # command type is dispatched.
        if config.ENABLE_UART_READ and startup_ticks >= 250:
            last_servo = None
            last_lighting = None
            last_heartbeat = False
            for _ in range(10):
                try:
                    line = self._serial.read_line()
                except Exception as e:
                    print(f"[PICO] read_line error: {e}")
                    break
                if line is None:
                    break
                self._rx_line_count += 1
                try:
                    parsed = self._parser.parse(line)
                    if parsed:
                        cmd_type, payload = parsed
                        if cmd_type == "cmd.servo.set":
                            self._rx_servo_count += 1
                            sid = payload.get("servo_id", 0)
                            self._last_servo_seq[sid] = payload.get("seq", 0)
                            last_servo = payload
                        elif cmd_type == "cmd.lighting.set":
                            last_lighting = payload
                        elif cmd_type == "sys.heartbeat":
                            last_heartbeat = True
                        else:
                            self._parser.dispatch(cmd_type, payload)
                except Exception as e:
                    print(f"[PICO] Parse error: {e}")
            if last_heartbeat:
                self._safety.command_received()
            if last_servo is not None:
                self._safety.command_received()
                self._parser.dispatch("cmd.servo.set", last_servo)
            if last_lighting is not None:
                self._parser.dispatch("cmd.lighting.set", last_lighting)

        # Safety check
        try:
            if self._safety.check():
                defaults = self._safety.get_default_angles()
                for i, angle in enumerate(defaults):
                    self.servo.set_angle(i, angle)
        except Exception as e:
            print(f"[PICO] safety error: {e}")

        # Stagger sensor reads to avoid I2C blocking the control loop
        try:
            self._read_sensors_staggered()
        except Exception as e:
            print(f"[PICO] sensor error: {e}")

        self._step_ms = int((time.time() - t0) * 1000)

    def _read_sensors_staggered(self):
        """Read one sensor per tick in round-robin to keep loop fast."""
        try:
            t0 = time.time()
            if self._sensor_phase == 0:
                yaw, pitch, roll, ax, ay, az = self.imu.read()
                self._sensor_cache["yaw"] = yaw
                self._sensor_cache["pitch"] = pitch
                self._sensor_cache["roll"] = roll
                self._sensor_cache["ax"] = ax
                self._sensor_cache["ay"] = ay
                self._sensor_cache["az"] = az
            elif self._sensor_phase == 1:
                depth_m, pressure_mbar, temp_c = self.pressure.read()
                self._sensor_cache["depth_m"] = depth_m
                self._sensor_cache["pressure_mbar"] = pressure_mbar
                self._sensor_cache["water_temp_c"] = temp_c
            elif self._sensor_phase == 2:
                env_temp, humidity, pressure_hpa = self.bme280.read()
                self._sensor_cache["env_temp_c"] = env_temp
                self._sensor_cache["humidity_pct"] = humidity
                self._sensor_cache["env_pressure_hpa"] = pressure_hpa
            elif self._sensor_phase == 3:
                for ch in range(4):
                    self._sensor_cache["leak"][ch] = self.leak.is_wet(ch)
            self._sensor_ms = int((time.time() - t0) * 1000)
        except Exception:
            self._sensor_ms = -1
        self._sensor_phase = (self._sensor_phase + 1) % 4

    def stop(self):
        self._running = False
