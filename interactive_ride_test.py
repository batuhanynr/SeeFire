#!/usr/bin/env python3
"""
SeeFire interactive ride test.

Controls (hold-to-move / tank drive):
    W       forward (hold)
    S       backward (hold)
    A       steer/rotate left (hold)
    D       steer/rotate right (hold)
    W+A/D   forward differential steer
    S+A/D   reverse differential steer
    SPACE   stop
    Q       quit

    Throttle + steer combine differentially:
      throttle held + steer -> both sides same direction, inner side slower
      steer alone           -> in-place rotation (sides spin opposite)

Hardware note:
    The chassis has 4 physical motors, but the L298N wiring drives them as
    two channels: left pair (FL+RL) and right pair (FR+RR). This dashboard
    shows all four wheels, while applying the same PWM to each side pair.
"""
from __future__ import annotations

import csv
import curses
import math
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import config


PWM_HZ = 1000
LOOP_DT = 0.05
KEY_HOLD_SEC = 0.6
STEER_INNER_SCALE = 0.35
TURN_SCALE = 1.0
LOG_INTERVAL = 1.0   # seconds between wheel-log rows

MIN_SPEED_LEVEL = 1
MAX_SPEED_LEVEL = 10


@dataclass
class WheelPower:
    fl: float = 0.0
    fr: float = 0.0
    rl: float = 0.0
    rr: float = 0.0


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

    def init(self) -> None:
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError(f"RPi.GPIO yok. Bu test Raspberry Pi uzerinde calismali: {exc}") from exc

        self.gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        pins = [
            config.MOTOR_IN1,
            config.MOTOR_IN2,
            config.MOTOR_IN3,
            config.MOTOR_IN4,
            config.MOTOR_ENA,
            config.MOTOR_ENB,
        ]
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        self.pwm_a = GPIO.PWM(config.MOTOR_ENA, PWM_HZ)
        self.pwm_b = GPIO.PWM(config.MOTOR_ENB, PWM_HZ)
        self.pwm_a.start(0)
        self.pwm_b.start(0)

        # Encoder interrupts
        GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(config.ENCODER_LEFT_PIN, GPIO.RISING, callback=self._on_left_tick, bouncetime=2)
        GPIO.add_event_detect(config.ENCODER_RIGHT_PIN, GPIO.RISING, callback=self._on_right_tick, bouncetime=2)

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
            try:
                self.gpio.remove_event_detect(config.ENCODER_LEFT_PIN)
                self.gpio.remove_event_detect(config.ENCODER_RIGHT_PIN)
            except Exception:
                pass
            self.gpio.cleanup(
                (
                    config.MOTOR_IN1,
                    config.MOTOR_IN2,
                    config.MOTOR_IN3,
                    config.MOTOR_IN4,
                    config.MOTOR_ENA,
                    config.MOTOR_ENB,
                    config.ENCODER_LEFT_PIN,
                    config.ENCODER_RIGHT_PIN,
                )
            )

    def _set_left(self, speed: float) -> None:
        # Polarity inverted vs wiring: speed>0 (forward) drives IN1 LOW / IN2 HIGH.
        gpio = self.gpio
        duty = abs(speed)
        if speed > 0:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.HIGH)
        elif speed < 0:
            gpio.output(config.MOTOR_IN1, gpio.HIGH)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        else:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        self.pwm_a.ChangeDutyCycle(duty)

    def _set_right(self, speed: float) -> None:
        # Polarity inverted vs wiring: speed>0 (forward) drives IN3 LOW / IN4 HIGH.
        gpio = self.gpio
        duty = abs(speed)
        if speed > 0:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.HIGH)
        elif speed < 0:
            gpio.output(config.MOTOR_IN3, gpio.HIGH)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        else:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        self.pwm_b.ChangeDutyCycle(duty)


class RideController:
    def __init__(self, max_level: int) -> None:
        self.max_level = max_level
        self.max_pwm = float(max_level * 10)
        self.accel = max(40.0, self.max_pwm * 1.25)
        self.decel = max(100.0, self.max_pwm * 3.0)
        self.left = 0.0
        self.right = 0.0
        self.last_seen: dict[str, float] = {}
        self.message = "Hazir"
        self.running = True
        self.hw = DriveHardware()
        self.last_speed_time = time.monotonic()
        self.last_left_ticks = 0
        self.last_right_ticks = 0
        self.speed_left = 0.0      # cm/s
        self.speed_right = 0.0     # cm/s
        self.rpm_left = 0.0
        self.rpm_right = 0.0
        # One wheel revolution advances pi * diameter.
        self.wheel_circ_cm = math.pi * (config.WHEEL_DIAMETER_MM / 10.0)

        # Per-second wheel log (compare left vs right speed/balance).
        self.log_file = None
        self.log_writer = None
        self.log_path: Path | None = None
        self.last_log_time = time.monotonic()
        self.last_log_left = 0
        self.last_log_right = 0
        self.t0 = time.monotonic()

    def init(self) -> None:
        self.hw.init()
        log_dir = Path(__file__).resolve().parent / "runtime_data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / f"wheel_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.log_file = self.log_path.open("w", newline="", encoding="utf-8")
        self.log_writer = csv.writer(self.log_file)
        self.log_writer.writerow([
            "t_s", "cmd_left_pwm", "cmd_right_pwm",
            "left_rpm", "right_rpm", "left_cm_s", "right_cm_s",
            "left_ticks", "right_ticks", "rpm_ratio_L_over_R",
        ])
        self.log_file.flush()

    def close(self) -> None:
        self.hw.cleanup()
        if self.log_file is not None:
            try:
                self.log_file.close()
            except Exception:
                pass

    def _log_row(self) -> None:
        now = time.monotonic()
        dt = now - self.last_log_time
        if dt < LOG_INTERVAL or self.log_writer is None:
            return
        dl = self.hw.left_ticks - self.last_log_left
        dr = self.hw.right_ticks - self.last_log_right
        rev_l = (dl / config.ENCODER_TICKS_PER_REV) / dt
        rev_r = (dr / config.ENCODER_TICKS_PER_REV) / dt
        l_rpm, r_rpm = rev_l * 60.0, rev_r * 60.0
        l_cms, r_cms = rev_l * self.wheel_circ_cm, rev_r * self.wheel_circ_cm
        ratio = (l_rpm / r_rpm) if r_rpm else 0.0
        self.log_writer.writerow([
            f"{now - self.t0:.1f}", f"{self.left:.1f}", f"{self.right:.1f}",
            f"{l_rpm:.1f}", f"{r_rpm:.1f}", f"{l_cms:.1f}", f"{r_cms:.1f}",
            self.hw.left_ticks, self.hw.right_ticks, f"{ratio:.3f}",
        ])
        self.log_file.flush()
        self.last_log_time = now
        self.last_log_left = self.hw.left_ticks
        self.last_log_right = self.hw.right_ticks

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
        elif key == "q":
            self.running = False

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

        max_pwm = self.max_pwm

        if fwd or back:
            # Moving: both sides same direction, inner side slowed for the curve.
            sign = 1.0 if fwd else -1.0
            base = sign * max_pwm
            inner = base * STEER_INNER_SCALE
            dir_label = "Ileri" if fwd else "Geri"
            if right_key:           # right turn -> right (inner) slower
                return base, inner, f"{dir_label} sag"
            if left_key:            # left turn -> left (inner) slower
                return inner, base, f"{dir_label} sol"
            return base, base, dir_label

        # Stationary: pivot turn. One side driven full, other coasts (free).
        # Stronger on low-power chassis than counter-rotation (only one side
        # must break traction; no scrub fighting on the other side).
        turn = max_pwm * TURN_SCALE
        if right_key:
            return turn, 0.0, "Pivot sag"
        if left_key:
            return 0.0, turn, "Pivot sol"
        return 0.0, 0.0, "Bos"

    def tick(self) -> None:
        target_left, target_right, mode = self.compute_target(self.active_keys())
        
        # Determine acceleration vs deceleration steps
        if target_left == 0.0:
            step_left = self.decel * LOOP_DT
        else:
            step_left = self.accel * LOOP_DT

        if target_right == 0.0:
            step_right = self.decel * LOOP_DT
        else:
            step_right = self.accel * LOOP_DT

        self.left = approach(self.left, target_left, step_left)
        self.right = approach(self.right, target_right, step_right)
        self.hw.set_drive(self.left, self.right)
        self.message = mode

        # Real-time RPM + speed from encoders (wheel geometry, not TICKS_PER_CM).
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

        self._log_row()

    def wheels(self) -> WheelPower:
        return WheelPower(fl=self.left, rl=self.left, fr=self.right, rr=self.right)


def approach(current: float, target: float, step: float) -> float:
    if math.isclose(current, target, abs_tol=step):
        return target
    return current + step if target > current else current - step


def ask_speed_level() -> int:
    print("Maks hiz derecesi sec (1-10)")
    print("1=%10 PWM, 3=%30 PWM, 6=%60 PWM, 10=%100 PWM")
    while True:
        raw = input("Hiz derecesi: ").strip()
        try:
            level = int(raw)
        except ValueError:
            print("1 ile 10 arasi sayi gir.")
            continue
        if MIN_SPEED_LEVEL <= level <= MAX_SPEED_LEVEL:
            return level
        print("1 ile 10 arasi sayi gir.")


def signed_bar(value: float, max_pwm: float, width: int = 18) -> str:
    value = max(-max_pwm, min(max_pwm, value))
    half = width // 2
    ratio = abs(value) / max_pwm if max_pwm else 0.0
    fill = int(round(ratio * half))
    if value > 0:
        return " " * half + "|" + "#" * fill + "." * (half - fill)
    if value < 0:
        return "." * (half - fill) + "#" * fill + "|" + " " * half
    return "." * half + "|" + "." * half


def fmt_power(value: float) -> str:
    direction = "FWD" if value > 0 else "REV" if value < 0 else "STOP"
    return f"{direction} {abs(value):05.1f}%"


def draw(stdscr, controller: RideController) -> None:
    stdscr.erase()
    wheels = controller.wheels()
    width = 100
    stdscr.addstr(0, 0, "SeeFire INTERACTIVE RIDE TEST".center(width))
    stdscr.addstr(1, 0, f"Hiz level {controller.max_level} | max PWM {controller.max_pwm:.0f}% | {controller.message}".center(width))
    stdscr.addstr(2, 0, "=" * width)
    stdscr.addstr(4, 2, "Kontrol (basili tut): W ileri | S geri | A sol | D sag | SPACE dur | Q cikis")
    stdscr.addstr(6, 2, "+----------------------------- ROBOT -----------------------------+")
    stdscr.addstr(7, 2, f"|  FL {fmt_power(wheels.fl):<12} {signed_bar(wheels.fl, controller.max_pwm)}   FR {fmt_power(wheels.fr):<12} {signed_bar(wheels.fr, controller.max_pwm)} |")
    stdscr.addstr(8, 2, "|                                                                   |")
    stdscr.addstr(9, 2, "|                              ^ ON                                 |")
    stdscr.addstr(10, 2, "|                                                                   |")
    stdscr.addstr(11, 2, f"|  RL {fmt_power(wheels.rl):<12} {signed_bar(wheels.rl, controller.max_pwm)}   RR {fmt_power(wheels.rr):<12} {signed_bar(wheels.rr, controller.max_pwm)} |")
    stdscr.addstr(12, 2, "+-------------------------------------------------------------------+")
    stdscr.addstr(14, 2, f"Sol kanal  PWM: {controller.left:6.1f}%   Sag kanal PWM: {controller.right:6.1f}%")
    stdscr.addstr(15, 2, f"Sol Enkoder: {controller.rpm_left:6.1f} rpm  {controller.speed_left:6.1f} cm/s ({controller.speed_left * 0.036:5.2f} km/h) (Tick: {controller.hw.left_ticks:<6})")
    stdscr.addstr(16, 2, f"Sag Enkoder: {controller.rpm_right:6.1f} rpm  {controller.speed_right:6.1f} cm/s ({controller.speed_right * 0.036:5.2f} km/h) (Tick: {controller.hw.right_ticks:<6})")
    stdscr.addstr(18, 2, f"Teker capi {config.WHEEL_DIAMETER_MM:.0f}mm, {config.ENCODER_TICKS_PER_REV:.0f} tick/tur | FL+RL ve FR+RR ayni L298N kanali.")
    if controller.log_path is not None:
        stdscr.addstr(19, 2, f"Log (1s): {controller.log_path.name}")
    stdscr.refresh()


def curses_main(stdscr, level: int) -> int:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    stdscr.timeout(0)

    controller = RideController(level)
    controller.init()

    def stop_handler(_sig, _frame):
        controller.running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    try:
        last = time.monotonic()
        while controller.running:
            ch = stdscr.getch()
            while ch != -1:
                if ch in (ord("w"), ord("W")):
                    controller.note_key("w")
                elif ch in (ord("a"), ord("A")):
                    controller.note_key("a")
                elif ch in (ord("s"), ord("S")):
                    controller.note_key("s")
                elif ch in (ord("d"), ord("D")):
                    controller.note_key("d")
                elif ch == ord(" "):
                    controller.note_key(" ")
                elif ch in (ord("q"), ord("Q")):
                    controller.note_key("q")
                ch = stdscr.getch()

            now = time.monotonic()
            if now - last >= LOOP_DT:
                controller.tick()
                draw(stdscr, controller)
                last = now
            time.sleep(0.005)
        return 0
    finally:
        controller.close()


def main() -> int:
    level = ask_speed_level()
    print("\nBasliyor. Robot tekerleri yerden kesik olsun veya genis alan olsun.")
    print("Cikis: Q veya Ctrl+C")
    time.sleep(2)
    return curses.wrapper(curses_main, level)


if __name__ == "__main__":
    sys.exit(main())
