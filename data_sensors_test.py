#!/usr/bin/env python3
"""
SeeFire active data-sensor dashboard.

Flow:
1. Probe each data sensor and print [PASS]/[FAIL].
2. Wait 20 seconds.
3. Refresh terminal with a live table using only passing sensors.

Run on Raspberry Pi from the SeeFire repo:
    python3 data_sensors_test.py
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

import config


INTERVAL_SECONDS = 3.0
START_DELAY_SECONDS = 20
ADC_REF_V = 3.3


@dataclass
class SensorStatus:
    key: str
    label: str
    ok: bool
    detail: str


class Dashboard:
    def __init__(self) -> None:
        self.gpio = None
        self.spi = None
        self.smbus_cls = None
        self.active: dict[str, SensorStatus] = {}
        self._stop = False

    def setup_signals(self) -> None:
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, _sig, _frame) -> None:
        self._stop = True

    def cleanup(self) -> None:
        if self.spi is not None:
            try:
                self.spi.close()
            except Exception:
                pass
        if self.gpio is not None:
            try:
                self.gpio.cleanup()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hardware setup helpers
    # ------------------------------------------------------------------
    def _ensure_gpio(self):
        if self.gpio is not None:
            return self.gpio
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError(f"RPi.GPIO yok: {exc}") from exc
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.gpio = GPIO
        return GPIO

    def _ensure_spi(self):
        if self.spi is not None:
            return self.spi
        try:
            import spidev
        except ImportError as exc:
            raise RuntimeError(f"spidev yok: {exc}") from exc
        gpio = self._ensure_gpio()
        gpio.setup(config.MQ2_CS_PIN, gpio.OUT)
        gpio.output(config.MQ2_CS_PIN, gpio.HIGH)
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1_000_000
        spi.no_cs = True
        self.spi = spi
        return spi

    def _ensure_smbus(self):
        if self.smbus_cls is not None:
            return self.smbus_cls
        try:
            from smbus2 import SMBus
        except ImportError as exc:
            raise RuntimeError(f"smbus2 yok: {exc}") from exc
        self.smbus_cls = SMBus
        return SMBus

    # ------------------------------------------------------------------
    # Probe functions
    # ------------------------------------------------------------------
    def probe_all(self) -> list[SensorStatus]:
        checks: list[tuple[str, str, Callable[[], str]]] = [
            ("front_us", "On ultrasonik", lambda: self._probe_ultrasonic(config.TRIG_FRONT, config.ECHO_FRONT)),
            ("left_us", "Sol ultrasonik", lambda: self._probe_ultrasonic(config.TRIG_LEFT, config.ECHO_LEFT)),
            ("right_us", "Sag ultrasonik", lambda: self._probe_ultrasonic(config.TRIG_RIGHT, config.ECHO_RIGHT)),
            ("mq2", "Duman/CO2 MQ-2", self._probe_mq2),
            ("ir", "Sicaklik MLX90614", self._probe_ir),
            ("battery", "Batarya ADC", self._probe_battery),
        ]

        statuses = []
        for key, label, fn in checks:
            try:
                detail = fn()
                status = SensorStatus(key, label, True, detail)
                self.active[key] = status
            except Exception as exc:
                status = SensorStatus(key, label, False, f"{type(exc).__name__}: {exc}")
            statuses.append(status)
        return statuses

    def _probe_ultrasonic(self, trig_pin: int, echo_pin: int) -> str:
        distance = self._read_ultrasonic(trig_pin, echo_pin)
        return f"{distance:.1f} cm"

    def _probe_mq2(self) -> str:
        raw = self._read_adc_12bit(config.MQ2_ADC_CH)
        return f"CH{config.MQ2_ADC_CH} raw={raw}/4095"

    def _probe_battery(self) -> str:
        raw = self._read_adc_12bit(config.BATTERY_ADC_CH)
        voltage = self._battery_voltage_from_raw(raw)
        if not (5.5 <= voltage <= 9.0):
            raise RuntimeError(f"beklenen 2S araligi disi: {voltage:.2f} V")
        return f"CH{config.BATTERY_ADC_CH} {voltage:.2f} V"

    def _probe_ir(self) -> str:
        ambient, obj = self._read_ir()
        return f"ambient={ambient:.1f} C, object={obj:.1f} C"

    # ------------------------------------------------------------------
    # Read functions
    # ------------------------------------------------------------------
    def _read_ultrasonic(self, trig_pin: int, echo_pin: int) -> float:
        gpio = self._ensure_gpio()
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
            raise RuntimeError(f"gecersiz mesafe: {distance:.1f} cm")
        return distance

    def _read_adc_12bit(self, channel: int) -> int:
        gpio = self._ensure_gpio()
        spi = self._ensure_spi()
        gpio.output(config.MQ2_CS_PIN, gpio.LOW)
        time.sleep(0.00001)
        try:
            data = spi.xfer2([6 | (channel >> 2), (channel & 3) << 6, 0])
        finally:
            gpio.output(config.MQ2_CS_PIN, gpio.HIGH)
        return ((data[1] & 15) << 8) + data[2]

    def _battery_voltage_from_raw(self, raw: int) -> float:
        pin_v = (raw / 4095.0) * ADC_REF_V
        return pin_v * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)

    def _read_ir(self) -> tuple[float, float]:
        SMBus = self._ensure_smbus()
        with SMBus(config.I2C_BUS) as bus:
            ambient = (bus.read_word_data(config.MLX90614_ADDR, 0x06) * 0.02) - 273.15
            obj = (bus.read_word_data(config.MLX90614_ADDR, 0x07) * 0.02) - 273.15
        return ambient, obj

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def print_probe_results(self, statuses: list[SensorStatus]) -> None:
        print("\nSeeFire data sensor aktiflik kontrolu\n")
        for status in statuses:
            tag = "[PASS]" if status.ok else "[FAIL]"
            print(f"{tag:<7} {status.label:<20} {status.detail}")
        print(f"\nCanli veri baslamadan once {START_DELAY_SECONDS} saniye bekleniyor...")

    def wait_before_live(self) -> None:
        for remaining in range(START_DELAY_SECONDS, 0, -1):
            if self._stop:
                return
            print(f"\rBaslamaya kalan: {remaining:02d}s", end="", flush=True)
            time.sleep(1)
        print()

    def clear(self) -> None:
        command = "cls" if os.name == "nt" else "clear"
        if shutil.which(command):
            subprocess.run([command], check=False)
        else:
            print("\033[2J\033[H", end="")

    def live_loop(self) -> None:
        while not self._stop:
            values = self.read_active_values()
            self.clear()
            self.print_dashboard(values)
            time.sleep(INTERVAL_SECONDS)

    def read_active_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        readers: dict[str, Callable[[], str]] = {
            "front_us": lambda: f"{self._read_ultrasonic(config.TRIG_FRONT, config.ECHO_FRONT):.1f} cm",
            "left_us": lambda: f"{self._read_ultrasonic(config.TRIG_LEFT, config.ECHO_LEFT):.1f} cm",
            "right_us": lambda: f"{self._read_ultrasonic(config.TRIG_RIGHT, config.ECHO_RIGHT):.1f} cm",
            "mq2": lambda: f"{self._read_adc_12bit(config.MQ2_ADC_CH)} / 4095",
            "battery": lambda: f"{self._battery_voltage_from_raw(self._read_adc_12bit(config.BATTERY_ADC_CH)):.2f} V",
            "ir": lambda: self._format_ir(),
        }
        for key in self.active:
            try:
                values[key] = readers[key]()
            except Exception as exc:
                values[key] = f"READ FAIL: {type(exc).__name__}: {exc}"
        return values

    def _format_ir(self) -> str:
        ambient, obj = self._read_ir()
        return f"object {obj:.1f} C / ortam {ambient:.1f} C"

    def _fit(self, text: str, width: int) -> str:
        text = str(text)
        if len(text) > width:
            return text[: max(0, width - 3)] + "..."
        return text.ljust(width)

    def print_dashboard(self, values: dict[str, str]) -> None:
        front = self._fit(values.get("front_us", "--"), 10)
        left = self._fit(values.get("left_us", "--"), 10)
        right = self._fit(values.get("right_us", "--"), 10)
        ir = self._fit(values.get("ir", "PASIF"), 30)
        mq2 = self._fit(values.get("mq2", "PASIF"), 30)
        battery = self._fit(values.get("battery", "PASIF"), 30)
        active = ", ".join(status.label for status in self.active.values()) or "Yok"
        width = 112
        left_w = 58
        right_w = 52
        gap = "  "

        robot_lines = [
            f"          ON: {front}",
            "      +--------------------+",
            "      |                    |",
            f"SOL: {left} |      SeeFire       | SAG: {right}",
            "      |       ROBOT        |",
            "      |                    |",
            "      +--------------------+",
        ]
        data_lines = [
            "DIGER VERILER",
            "------------",
            f"Sicaklik   : {ir}",
            f"Duman(CO2) : {mq2}",
            f"Batarya    : {battery}",
            "",
            "",
        ]

        print("SeeFire DATA SENSOR LIVE".center(width))
        print(("Guncelleme: " + time.strftime("%H:%M:%S") + f" | interval {INTERVAL_SECONDS:.0f}s").center(width))
        print("=" * width)
        for robot_line, data_line in zip(robot_lines, data_lines):
            print(self._fit(robot_line, left_w) + gap + self._fit(data_line, right_w))
        print("=" * width)
        print()
        print("Aktif sensorler: " + self._fit(active, width - 17).rstrip())
        print("Cikis: Ctrl+C")


def main() -> int:
    dashboard = Dashboard()
    dashboard.setup_signals()
    try:
        statuses = dashboard.probe_all()
        dashboard.print_probe_results(statuses)
        dashboard.wait_before_live()
        if not dashboard.active:
            print("\nAktif sensor yok. Cikis.")
            return 1
        dashboard.live_loop()
        return 0
    finally:
        dashboard.cleanup()
        print("\nTemizlendi.")


if __name__ == "__main__":
    sys.exit(main())
