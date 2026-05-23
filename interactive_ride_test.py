#!/usr/bin/env python3
"""
SeeFire interactive ride test.

Controls:
    W       forward
    S       backward
    A       rotate left in place
    D       rotate right in place
    W+A/D   forward steering
    S+A/D   reverse steering
    SPACE   brake/stop
    Q       quit

Hardware note:
    The chassis has 4 physical motors, but the L298N wiring drives them as
    two channels: left pair (FL+RL) and right pair (FR+RR). This dashboard
    shows all four wheels, while applying the same PWM to each side pair.
"""
from __future__ import annotations

import curses
import math
import signal
import sys
import time
from dataclasses import dataclass

import config


PWM_HZ = 1000
LOOP_DT = 0.05
KEY_HOLD_SEC = 0.22
STEER_INNER_SCALE = 0.35

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
            self.gpio.cleanup(
                (
                    config.MOTOR_IN1,
                    config.MOTOR_IN2,
                    config.MOTOR_IN3,
                    config.MOTOR_IN4,
                    config.MOTOR_ENA,
                    config.MOTOR_ENB,
                )
            )

    def _set_left(self, speed: float) -> None:
        gpio = self.gpio
        duty = abs(speed)
        if speed > 0:
            gpio.output(config.MOTOR_IN1, gpio.HIGH)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        elif speed < 0:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.HIGH)
        else:
            gpio.output(config.MOTOR_IN1, gpio.LOW)
            gpio.output(config.MOTOR_IN2, gpio.LOW)
        self.pwm_a.ChangeDutyCycle(duty)

    def _set_right(self, speed: float) -> None:
        gpio = self.gpio
        duty = abs(speed)
        if speed > 0:
            gpio.output(config.MOTOR_IN3, gpio.HIGH)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        elif speed < 0:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.HIGH)
        else:
            gpio.output(config.MOTOR_IN3, gpio.LOW)
            gpio.output(config.MOTOR_IN4, gpio.LOW)
        self.pwm_b.ChangeDutyCycle(duty)


class RideController:
    def __init__(self, max_level: int) -> None:
        self.max_level = max_level
        self.max_pwm = float(max_level * 10)
        self.accel = max(40.0, self.max_pwm * 1.25)
        self.left = 0.0
        self.right = 0.0
        self.last_seen: dict[str, float] = {}
        self.message = "Hazir"
        self.running = True
        self.hw = DriveHardware()

    def init(self) -> None:
        self.hw.init()

    def close(self) -> None:
        self.hw.cleanup()

    def note_key(self, key: str) -> None:
        now = time.monotonic()
        if key in ("w", "a", "s", "d"):
            self.last_seen[key] = now
        elif key == " ":
            self.left = 0.0
            self.right = 0.0
            self.hw.stop()
            self.last_seen.clear()
            self.message = "Fren"
        elif key == "q":
            self.running = False

    def active_keys(self) -> set[str]:
        now = time.monotonic()
        return {key for key, ts in self.last_seen.items() if now - ts <= KEY_HOLD_SEC}

    def target_from_keys(self, keys: set[str]) -> tuple[float, float, str]:
        fwd = "w" in keys
        back = "s" in keys
        left_key = "a" in keys
        right_key = "d" in keys

        if fwd and back:
            return 0.0, 0.0, "Cakisik W+S"
        if left_key and right_key and not (fwd or back):
            return 0.0, 0.0, "Cakisik A+D"

        max_pwm = self.max_pwm
        inner = max_pwm * STEER_INNER_SCALE

        if fwd:
            if left_key:
                return inner, max_pwm, "Ileri sol"
            if right_key:
                return max_pwm, inner, "Ileri sag"
            return max_pwm, max_pwm, "Ileri"

        if back:
            if left_key:
                return -inner, -max_pwm, "Geri sol"
            if right_key:
                return -max_pwm, -inner, "Geri sag"
            return -max_pwm, -max_pwm, "Geri"

        turn_pwm = max_pwm * 0.85
        if left_key:
            return -turn_pwm, turn_pwm, "Yerinde sol"
        if right_key:
            return turn_pwm, -turn_pwm, "Yerinde sag"

        return 0.0, 0.0, "Bos"

    def tick(self) -> None:
        target_left, target_right, mode = self.target_from_keys(self.active_keys())
        step = self.accel * LOOP_DT
        self.left = approach(self.left, target_left, step)
        self.right = approach(self.right, target_right, step)
        self.hw.set_drive(self.left, self.right)
        self.message = mode

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
    stdscr.addstr(4, 2, "Kontrol: W ileri | S geri | A yerinde sol | D yerinde sag | SPACE fren | Q cikis")
    stdscr.addstr(6, 2, "+----------------------------- ROBOT -----------------------------+")
    stdscr.addstr(7, 2, f"|  FL {fmt_power(wheels.fl):<12} {signed_bar(wheels.fl, controller.max_pwm)}   FR {fmt_power(wheels.fr):<12} {signed_bar(wheels.fr, controller.max_pwm)} |")
    stdscr.addstr(8, 2, "|                                                                   |")
    stdscr.addstr(9, 2, "|                              ^ ON                                 |")
    stdscr.addstr(10, 2, "|                                                                   |")
    stdscr.addstr(11, 2, f"|  RL {fmt_power(wheels.rl):<12} {signed_bar(wheels.rl, controller.max_pwm)}   RR {fmt_power(wheels.rr):<12} {signed_bar(wheels.rr, controller.max_pwm)} |")
    stdscr.addstr(12, 2, "+-------------------------------------------------------------------+")
    stdscr.addstr(14, 2, f"Sol kanal  PWM: {controller.left:6.1f}%   Sag kanal PWM: {controller.right:6.1f}%")
    stdscr.addstr(15, 2, "Not: FL+RL ayni L298N kanalinda, FR+RR ayni L298N kanalinda.")
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
