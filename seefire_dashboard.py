#!/usr/bin/env python3
"""
SeeFire unified cockpit: drive control + live sensor dashboard in one screen.

Flow:
    1. Ask max forward speed level (1-25) and turning speed level (1-25).
    2. 5 s device check screen: probe every attached device, show PASS/FAIL.
    3. Main screen:
         - top:    ASCII robot with wheel-pair power/RPM/speed and the three
                   ultrasonic distances (front/left/right).
         - bottom: data-sensor readings (IR temp, MQ-2 smoke, battery, encoders,
                   camera).

Controls:
    W/S        forward / backward (hold)
    A/D        steer-or-rotate left / right (hold)
    W+A/D      forward differential steer
    SPACE      stop
    P          capture camera snapshot
    Q          quit

Hardware note:
    4 physical motors driven by two L298N boards (front #1 + rear #2) with
    parallel GPIO signals. Motor 1=FL, 2=FR (L298N #1), Motor 3=RL, 4=RR
    (L298N #2). Same PWM per side.

Heavy sensor reads (ultrasonic/ADC/I2C) run on a background thread (~0.5 s);
the drive loop stays fast (20 Hz). Encoders are interrupt-driven.

Run on Raspberry Pi from the SeeFire repo:
    python3 seefire_dashboard.py
"""

from __future__ import annotations

import curses
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import config

PWM_HZ = 1000
LOOP_DT = 0.05
KEY_HOLD_SEC = 0.6
STEER_INNER_SCALE = 0.35
TURN_SCALE = 1.0

MIN_SPEED_LEVEL = 1
MAX_SPEED_LEVEL = 25

CHECK_SECONDS = 5
SENSOR_INTERVAL = 0.5
ADC_REF_V = 3.3


# ---------------------------------------------------------------------------
# Drive hardware (L298N ×2 motors + interrupt encoders)
# ---------------------------------------------------------------------------
class DriveHardware:
    def __init__(self) -> None:
        self.gpio = None
        self.pwm_a = None
        self.pwm_b = None
        self.left_ticks = 0
        self.right_ticks = 0

    def _on_left_tick(self, _channel) -> None:
        self.left_ticks += 1

    def _on_right_tick(self, _channel) -> None:
        self.right_ticks += 1

    def init(self, gpio) -> None:
        self.gpio = gpio
        pins = [
            config.MOTOR_IN1,
            config.MOTOR_IN2,
            config.MOTOR_IN3,
            config.MOTOR_IN4,
            config.MOTOR_ENA,
            config.MOTOR_ENB,
        ]
        for pin in pins:
            gpio.setup(pin, gpio.OUT)
            gpio.output(pin, gpio.LOW)

        self.pwm_a = gpio.PWM(config.MOTOR_ENA, PWM_HZ)
        self.pwm_b = gpio.PWM(config.MOTOR_ENB, PWM_HZ)
        self.pwm_a.start(0)
        self.pwm_b.start(0)

        gpio.setup(config.ENCODER_LEFT_PIN, gpio.IN, pull_up_down=gpio.PUD_DOWN)
        gpio.setup(config.ENCODER_RIGHT_PIN, gpio.IN, pull_up_down=gpio.PUD_DOWN)
        gpio.add_event_detect(
            config.ENCODER_LEFT_PIN,
            gpio.RISING,
            callback=self._on_left_tick,
            bouncetime=2,
        )
        gpio.add_event_detect(
            config.ENCODER_RIGHT_PIN,
            gpio.RISING,
            callback=self._on_right_tick,
            bouncetime=2,
        )

    def set_drive(self, left: float, right: float) -> None:
        left = max(-100.0, min(100.0, left))
        right = max(-100.0, min(100.0, right))
        self._set_left(left)
        self._set_right(right)

    def stop(self) -> None:
        self.set_drive(0.0, 0.0)

    def cleanup(self) -> None:
        try:
            self.stop()
        except Exception:
            pass
        if self.pwm_a is not None:
            self.pwm_a.stop()
        if self.pwm_b is not None:
            self.pwm_b.stop()
        if self.gpio is not None:
            for pin in (config.ENCODER_LEFT_PIN, config.ENCODER_RIGHT_PIN):
                try:
                    self.gpio.remove_event_detect(pin)
                except Exception:
                    pass

    def _set_left(self, speed: float) -> None:
        # Polarity inverted vs wiring: speed>0 (forward) drives IN1 LOW / IN2 HIGH.
        gpio = self.gpio
        if speed > 0:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.HIGH)
        elif speed < 0:
            gpio.output(config.MOTOR_IN1, gpio.HIGH)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        else:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        self.pwm_a.ChangeDutyCycle(abs(speed))

    def _set_right(self, speed: float) -> None:
        # Tested polarity: speed>0 (forward) drives IN3 HIGH / IN4 LOW.
        gpio = self.gpio
        if speed > 0:
            gpio.output(config.MOTOR_IN3, gpio.HIGH)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        elif speed < 0:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.HIGH)
        else:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        self.pwm_b.ChangeDutyCycle(abs(speed))


# ---------------------------------------------------------------------------
# Drive controller (state + encoder RPM/speed)
# ---------------------------------------------------------------------------
def approach(current: float, target: float, step: float) -> float:
    if math.isclose(current, target, abs_tol=step):
        return target
    return current + step if target > current else current - step


class RideController:
    def __init__(self, hw: DriveHardware, fwd_level: int, turn_level: int) -> None:
        self.hw = hw
        self.fwd_level = fwd_level
        self.turn_level = turn_level
        self.max_pwm_fwd = float(fwd_level * 4)
        self.max_pwm_turn = float(turn_level * 4)
        self.accel = max(40.0, max(self.max_pwm_fwd, self.max_pwm_turn) * 1.25)
        self.decel = max(100.0, max(self.max_pwm_fwd, self.max_pwm_turn) * 3.0)
        self.left = 0.0
        self.right = 0.0
        self.last_seen: dict[str, float] = {}
        self.message = "Hazir"

        self.last_speed_time = time.monotonic()
        self.last_left_ticks = 0
        self.last_right_ticks = 0
        self.speed_left = 0.0
        self.speed_right = 0.0
        self.rpm_left = 0.0
        self.rpm_right = 0.0
        self.wheel_circ_cm = math.pi * (config.WHEEL_DIAMETER_MM / 10.0)

    def note_key(self, key: str) -> None:
        now = time.monotonic()
        if key in ("w", "a", "s", "d"):
            self.last_seen[key] = now
        elif key == " ":
            self.left = 0.0
            self.right = 0.0
            self.hw.stop()
            self.last_seen.clear()
            self.message = "Dur"

    def active_keys(self) -> set[str]:
        now = time.monotonic()
        return {key for key, ts in self.last_seen.items() if now - ts <= KEY_HOLD_SEC}

    def compute_target(self, keys: set[str]) -> tuple[float, float, str]:
        fwd = "w" in keys
        back = "s" in keys
        left_key = "a" in keys
        right_key = "d" in keys

        if fwd and back:
            return 0.0, 0.0, "Cakisik W+S"
        if left_key and right_key and not (fwd or back):
            return 0.0, 0.0, "Cakisik A+D"

        if fwd or back:
            sign = 1.0 if fwd else -1.0
            base = sign * self.max_pwm_fwd
            inner = base * STEER_INNER_SCALE
            dir_label = "Ileri" if fwd else "Geri"
            if right_key:
                return base, inner, f"{dir_label} sag"
            if left_key:
                return inner, base, f"{dir_label} sol"
            return base, base, dir_label

        # Stationary: tank turn (sides spin opposite directions).
        turn = self.max_pwm_turn * TURN_SCALE
        if right_key:
            return turn, -turn, "Tank sag"
        if left_key:
            return -turn, turn, "Tank sol"
        return 0.0, 0.0, "Bos"

    def tick(self) -> None:
        target_left, target_right, mode = self.compute_target(self.active_keys())
        step_left = (self.decel if target_left == 0.0 else self.accel) * LOOP_DT
        step_right = (self.decel if target_right == 0.0 else self.accel) * LOOP_DT
        self.left = approach(self.left, target_left, step_left)
        self.right = approach(self.right, target_right, step_right)
        self.hw.set_drive(self.left, self.right)
        self.message = mode

        now = time.monotonic()
        dt = now - self.last_speed_time
        if dt >= 0.2:
            dl = self.hw.left_ticks - self.last_left_ticks
            dr = self.hw.right_ticks - self.last_right_ticks
            rev_l = (dl / config.ENCODER_TICKS_PER_REV) / dt
            rev_r = (dr / config.ENCODER_TICKS_PER_REV) / dt
            self.rpm_left = rev_l * 60.0
            self.rpm_right = rev_r * 60.0
            self.speed_left = rev_l * self.wheel_circ_cm
            self.speed_right = rev_r * self.wheel_circ_cm
            self.last_left_ticks = self.hw.left_ticks
            self.last_right_ticks = self.hw.right_ticks
            self.last_speed_time = now


# ---------------------------------------------------------------------------
# Sensor hub (ultrasonic / MQ-2 / IR / battery / camera) on a background thread
# ---------------------------------------------------------------------------
@dataclass
class SensorStatus:
    key: str
    label: str
    ok: bool
    detail: str


class SensorHub:
    def __init__(self, gpio) -> None:
        self.gpio = gpio
        self.spi = None
        self.smbus_cls = None
        self.cv2 = None
        self.camera_device = 0
        self.snapshot_dir = (
            Path(__file__).resolve().parent / "runtime_data" / "snapshots"
        )
        self.photo_count = 0
        self.photo_status = "P ile foto cek"

        self.active: dict[str, str] = {}  # key -> label
        self.values: dict[str, str] = {}  # key -> latest formatted value
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- setup helpers ----------------------------------------------------
    def _ensure_spi(self):
        if self.spi is not None:
            return self.spi
        import spidev

        self.gpio.setup(config.MQ2_CS_PIN, self.gpio.OUT)
        self.gpio.output(config.MQ2_CS_PIN, self.gpio.HIGH)
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1_000_000
        spi.no_cs = True
        self.spi = spi
        return spi

    def _ensure_smbus(self):
        if self.smbus_cls is not None:
            return self.smbus_cls
        from smbus2 import SMBus

        self.smbus_cls = SMBus
        return SMBus

    # --- raw reads --------------------------------------------------------
    def _read_ultrasonic(self, trig_pin: int, echo_pin: int) -> float:
        gpio = self.gpio
        gpio.setup(trig_pin, gpio.OUT)
        gpio.output(trig_pin, gpio.LOW)
        gpio.setup(echo_pin, gpio.IN)
        time.sleep(0.03)
        gpio.output(trig_pin, gpio.HIGH)
        time.sleep(0.00001)
        gpio.output(trig_pin, gpio.LOW)

        deadline = time.time() + 0.05
        start_t = None
        while gpio.input(echo_pin) == 0 and time.time() < deadline:
            start_t = time.time()
        if start_t is None:
            raise RuntimeError("echo baslamadi")
        stop_t = start_t
        while gpio.input(echo_pin) == 1 and time.time() < deadline:
            stop_t = time.time()
        distance = ((stop_t - start_t) * 34300.0) / 2.0
        if not (2.0 <= distance <= 400.0):
            raise RuntimeError(f"gecersiz: {distance:.1f}cm")
        return distance

    def _read_adc_12bit(self, channel: int) -> int:
        gpio = self.gpio
        spi = self._ensure_spi()
        gpio.output(config.MQ2_CS_PIN, gpio.LOW)
        time.sleep(0.00001)
        try:
            data = spi.xfer2([6 | (channel >> 2), (channel & 3) << 6, 0])
        finally:
            gpio.output(config.MQ2_CS_PIN, gpio.HIGH)
        return ((data[1] & 15) << 8) + data[2]

    def _battery_voltage(self, raw: int) -> float:
        pin_v = (raw / 4095.0) * ADC_REF_V
        return pin_v * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)

    def _read_ir(self) -> tuple[float, float]:
        SMBus = self._ensure_smbus()
        with SMBus(config.I2C_BUS) as bus:
            ambient = (bus.read_word_data(config.MLX90614_ADDR, 0x06) * 0.02) - 273.15
            obj = (bus.read_word_data(config.MLX90614_ADDR, 0x07) * 0.02) - 273.15
        return ambient, obj

    # --- formatted readers ------------------------------------------------
    def _fmt_front(self) -> str:
        return f"{self._read_ultrasonic(config.TRIG_FRONT, config.ECHO_FRONT):.1f} cm"

    def _fmt_left(self) -> str:
        return f"{self._read_ultrasonic(config.TRIG_LEFT, config.ECHO_LEFT):.1f} cm"

    def _fmt_right(self) -> str:
        return f"{self._read_ultrasonic(config.TRIG_RIGHT, config.ECHO_RIGHT):.1f} cm"

    def _fmt_mq2(self) -> str:
        return f"{self._read_adc_12bit(config.MQ2_ADC_CH)} / 4095"

    def _fmt_battery(self) -> str:
        return f"{self._battery_voltage(self._read_adc_12bit(config.BATTERY_ADC_CH)):.2f} V"

    def _fmt_ir(self) -> str:
        ambient, obj = self._read_ir()
        return f"obj {obj:.1f}C / ortam {ambient:.1f}C"

    def _readers(self) -> dict[str, Callable[[], str]]:
        return {
            "front_us": self._fmt_front,
            "left_us": self._fmt_left,
            "right_us": self._fmt_right,
            "mq2": self._fmt_mq2,
            "ir": self._fmt_ir,
            "battery": self._fmt_battery,
        }

    # --- probe ------------------------------------------------------------
    def probe(self) -> list[SensorStatus]:
        labels = {
            "front_us": "On ultrasonik",
            "left_us": "Sol ultrasonik",
            "right_us": "Sag ultrasonik",
            "mq2": "Duman/CO2 MQ-2",
            "ir": "Sicaklik MLX90614",
            "battery": "Batarya ADC",
        }
        statuses: list[SensorStatus] = []
        readers = self._readers()
        for key, label in labels.items():
            try:
                detail = readers[key]()
                self.active[key] = label
                self.values[key] = detail
                statuses.append(SensorStatus(key, label, True, detail))
            except Exception as exc:
                statuses.append(
                    SensorStatus(key, label, False, f"{type(exc).__name__}: {exc}")
                )

        # Camera probe (capture happens on demand).
        cam = SensorStatus("camera", "Kamera (P foto)", False, "")
        try:
            dev = Path(f"/dev/video{self.camera_device}")
            if not dev.exists():
                raise RuntimeError(f"{dev} yok")
            import cv2

            self.cv2 = cv2
            cam = SensorStatus(
                "camera",
                "Kamera (P foto)",
                True,
                f"/dev/video{self.camera_device} hazir",
            )
        except Exception as exc:
            cam = SensorStatus(
                "camera", "Kamera (P foto)", False, f"{type(exc).__name__}: {exc}"
            )
        statuses.append(cam)
        return statuses

    # --- background loop --------------------------------------------------
    def start(self) -> None:
        if not self.active:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        readers = self._readers()
        while not self._stop.is_set():
            for key in list(self.active):
                if key not in readers:
                    continue
                try:
                    val = readers[key]()
                except Exception:
                    val = "ERR"
                with self._lock:
                    self.values[key] = val
            self._stop.wait(SENSOR_INTERVAL)

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self.values)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # --- camera -----------------------------------------------------------
    def capture_photo(self) -> None:
        if self.cv2 is None:
            self.photo_status = "Kamera pasif"
            return
        cv2 = self.cv2
        cap = cv2.VideoCapture(self.camera_device)
        if not cap.isOpened():
            self.photo_status = "Kamera acilmadi"
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        frame = None
        for _ in range(10):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                break
            time.sleep(0.05)
        cap.release()
        if frame is None or not frame.size:
            self.photo_status = "Bos kare"
            return
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        fname = self.snapshot_dir / f"snap_{time.strftime('%H%M%S')}.jpg"
        if cv2.imwrite(str(fname), frame):
            self.photo_count += 1
            self.photo_status = f"kayit #{self.photo_count}: {fname.name}"
        else:
            self.photo_status = "yazma hatasi"


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def _ask_level(prompt: str, hint: str) -> int:
    print(prompt)
    print(hint)
    while True:
        raw = input("Derece: ").strip()
        try:
            level = int(raw)
        except ValueError:
            print(f"{MIN_SPEED_LEVEL} ile {MAX_SPEED_LEVEL} arasi sayi gir.")
            continue
        if MIN_SPEED_LEVEL <= level <= MAX_SPEED_LEVEL:
            return level
        print(f"{MIN_SPEED_LEVEL} ile {MAX_SPEED_LEVEL} arasi sayi gir.")


def ask_speed_levels() -> tuple[int, int]:
    print("=== Guc Ayarlari ===")
    fwd = _ask_level(
        "Ileri/geri guc derecesi sec (1-25)",
        "1=%4 PWM, 5=%20 PWM, 13=%52 PWM, 25=%100 PWM",
    )
    turn = _ask_level(
        "Donus guc derecesi sec (1-25)",
        "1=%4 PWM, 5=%20 PWM, 13=%52 PWM, 25=%100 PWM",
    )
    return fwd, turn


def fmt_power(value: float) -> str:
    direction = "FWD" if value > 0 else "REV" if value < 0 else "OFF"
    return f"{direction:<3} {abs(value):05.1f}%"  # fixed 10 chars


def fmt_dist(value: str, width: int = 8) -> str:
    """Right-justified fixed-width distance; errors collapse to '---'."""
    if not value or "HATA" in value or "ERR" in value or value == "--":
        value = "---"
    return value.rjust(width)


def _addstr(stdscr, y: int, x: int, text: str) -> None:
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def draw_check(stdscr, statuses: list[SensorStatus], remaining: int) -> None:
    stdscr.erase()
    _addstr(stdscr, 0, 0, "SeeFire CIHAZ KONTROLU".center(80))
    _addstr(stdscr, 1, 0, "=" * 80)
    row = 3
    for s in statuses:
        tag = "[PASS]" if s.ok else "[FAIL]"
        _addstr(stdscr, row, 2, f"{tag:<7} {s.label:<22} {s.detail}")
        row += 1
    _addstr(stdscr, row + 1, 2, f"Ana ekrana {remaining}s...")
    stdscr.refresh()


def draw_main(stdscr, ride: RideController, hub: SensorHub) -> None:
    vals = hub.snapshot()
    front = fmt_dist(vals.get("front_us", "--"))
    left = fmt_dist(vals.get("left_us", "--"))
    right = fmt_dist(vals.get("right_us", "--"))
    pl = fmt_power(ride.left)
    pr = fmt_power(ride.right)

    stdscr.erase()
    width = 100
    _addstr(stdscr, 0, 0, "SeeFire KOKPIT (surus + sensor)".center(width))
    _addstr(stdscr, 1, 0, f"Ileri guc {ride.fwd_level} (PWM {ride.max_pwm_fwd:.0f}%) | Donus guc {ride.turn_level} (PWM {ride.max_pwm_turn:.0f}%) | {ride.message}".center(width))
    _addstr(stdscr, 2, 0, "=" * width)
    _addstr(
        stdscr, 3, 2, "W ileri | S geri | A sol | D sag | SPACE dur | P foto | Q cikis"
    )

    # --- robot + ultrasonics (top), fixed-width grid so columns stay aligned ---
    LM = 4  # left screen margin
    GUT = 15  # left gutter width (wheel/sensor labels), bar aligns here
    INNER = 24  # box interior width
    box_x = LM + GUT + 1
    border = " " * GUT + "+" + "-" * INNER + "+"

    def row(left_lbl: str, interior: str, right_lbl: str) -> str:
        return f"{left_lbl:>{GUT}}|{interior.center(INNER)}|{right_lbl}"

    _addstr(stdscr, 5, box_x, f"ON {front}".center(INNER))
    _addstr(stdscr, 6, LM, border)
    _addstr(stdscr, 7, LM, row(f"FL {pl} ", "", f" FR {pr}"))
    _addstr(stdscr, 8, LM, row(f"SOL {left} ", "S E E F I R E", f" SAG {right}"))
    _addstr(stdscr, 9, LM, row("", "^ ileri", ""))
    _addstr(stdscr, 10, LM, row(f"RL {pl} ", "", f" RR {pr}"))
    _addstr(stdscr, 11, LM, border)

    _addstr(
        stdscr,
        13,
        LM,
        f"Sol kanal: {ride.rpm_left:6.1f} rpm  {ride.speed_left:6.1f} cm/s  ({ride.speed_left * 0.036:4.2f} km/h)  tick {ride.hw.left_ticks}",
    )
    _addstr(
        stdscr,
        14,
        LM,
        f"Sag kanal: {ride.rpm_right:6.1f} rpm  {ride.speed_right:6.1f} cm/s  ({ride.speed_right * 0.036:4.2f} km/h)  tick {ride.hw.right_ticks}",
    )

    # --- data sensors (bottom) ---
    _addstr(stdscr, 16, 0, "-" * width)
    _addstr(stdscr, 17, 2, "VERILER")
    _addstr(stdscr, 18, 2, f"Sicaklik   : {vals.get('ir', 'PASIF')}")
    _addstr(stdscr, 19, 2, f"Duman(CO2) : {vals.get('mq2', 'PASIF')}")
    _addstr(stdscr, 20, 2, f"Batarya    : {vals.get('battery', 'PASIF')}")
    _addstr(stdscr, 21, 2, f"Kamera     : {hub.photo_status}")
    stdscr.refresh()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def curses_main(stdscr, fwd_level: int, turn_level: int) -> int:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        _addstr(stdscr, 0, 0, f"RPi.GPIO yok, Pi uzerinde calismali: {exc}")
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
        return 1

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    hw = DriveHardware()
    ride = RideController(hw, fwd_level, turn_level)
    hub = SensorHub(GPIO)

    running = True
    try:
        hw.init(GPIO)
        statuses = hub.probe()
        # Drive/encoders status from successful init.
        statuses.insert(
            0,
            SensorStatus(
                "drive",
                "Motor + Enkoder",
                True,
                f"L298N ×2 + enc GPIO{config.ENCODER_LEFT_PIN}/{config.ENCODER_RIGHT_PIN}",
            ),
        )

        # 5 s check screen.
        end = time.monotonic() + CHECK_SECONDS
        while time.monotonic() < end:
            draw_check(stdscr, statuses, int(end - time.monotonic()) + 1)
            time.sleep(0.2)

        hub.start()

        last = time.monotonic()
        while running:
            ch = stdscr.getch()
            while ch != -1:
                if ch in (ord("w"), ord("W")):
                    ride.note_key("w")
                elif ch in (ord("a"), ord("A")):
                    ride.note_key("a")
                elif ch in (ord("s"), ord("S")):
                    ride.note_key("s")
                elif ch in (ord("d"), ord("D")):
                    ride.note_key("d")
                elif ch == ord(" "):
                    ride.note_key(" ")
                elif ch in (ord("p"), ord("P")):
                    hub.capture_photo()
                elif ch in (ord("q"), ord("Q")):
                    running = False
                ch = stdscr.getch()

            now = time.monotonic()
            if now - last >= LOOP_DT:
                ride.tick()
                draw_main(stdscr, ride, hub)
                last = now
            time.sleep(0.005)
        return 0
    finally:
        hub.stop()
        hw.cleanup()
        try:
            GPIO.cleanup()
        except Exception:
            pass


def main() -> int:
    fwd_level, turn_level = ask_speed_levels()
    print(f"\nIleri guc: {fwd_level} (PWM {fwd_level*4}%) | Donus guc: {turn_level} (PWM {turn_level*4}%)")
    print("Basliyor. Robot tekerleri yerden kesik olsun veya genis alan olsun.")
    print("Cikis: Q veya Ctrl+C")
    time.sleep(1.5)
    return curses.wrapper(curses_main, fwd_level, turn_level)


if __name__ == "__main__":
    import sys

    sys.exit(main())
