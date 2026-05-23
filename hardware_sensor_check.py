#!/usr/bin/env python3
"""
SeeFire Raspberry Pi hardware checks for today's missing sensors:
wheel encoders, USB camera, and MLX90614 IR thermometer.

Run on Raspberry Pi from the SeeFire repo:
    python3 hardware_sensor_check.py --all
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import config


RESULTS_PATH = Path("docs/bugunku_sensor_test_plani.md")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def append_result(result: CheckResult) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if result.ok else "FAIL"
    with RESULTS_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n| {time.strftime('%Y-%m-%d %H:%M:%S')} | {result.name} | {status} | {result.detail} |\n")


def run_check(name: str, fn: Callable[[], CheckResult]) -> CheckResult:
    print(f"\n=== {name} ===")
    try:
        result = fn()
    except Exception as exc:  # Keep field testing moving; record exact failure.
        result = CheckResult(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")
    print(("PASS" if result.ok else "FAIL") + f": {result.detail}")
    append_result(result)
    return result


def check_encoders(duration: float) -> CheckResult:
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        return CheckResult("encoders", False, f"RPi.GPIO import failed: {exc}")

    left_ticks = 0
    right_ticks = 0

    def on_left(_channel):
        nonlocal left_ticks
        left_ticks += 1

    def on_right(_channel):
        nonlocal right_ticks
        right_ticks += 1

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.ENCODER_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(config.ENCODER_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(config.ENCODER_LEFT_PIN, GPIO.RISING, callback=on_left, bouncetime=2)
    GPIO.add_event_detect(config.ENCODER_RIGHT_PIN, GPIO.RISING, callback=on_right, bouncetime=2)

    print(
        f"Spin wheels by hand now. Left GPIO{config.ENCODER_LEFT_PIN}, "
        f"right GPIO{config.ENCODER_RIGHT_PIN}. Waiting {duration:.0f}s..."
    )
    time.sleep(duration)

    try:
        GPIO.remove_event_detect(config.ENCODER_LEFT_PIN)
        GPIO.remove_event_detect(config.ENCODER_RIGHT_PIN)
    finally:
        GPIO.cleanup((config.ENCODER_LEFT_PIN, config.ENCODER_RIGHT_PIN))

    ok = left_ticks > 0 and right_ticks > 0
    detail = f"left_ticks={left_ticks}, right_ticks={right_ticks}"
    if not ok:
        detail += "; expected both > 0 while wheels spin"
    return CheckResult("encoders", ok, detail)


def check_camera(device: int, snapshot_path: str) -> CheckResult:
    device_path = Path(f"/dev/video{device}")
    if not device_path.exists():
        return CheckResult("camera", False, f"{device_path} does not exist")

    try:
        import cv2
    except ImportError as exc:
        return CheckResult("camera", False, f"cv2 import failed: {exc}")

    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return CheckResult("camera", False, f"/dev/video{device} did not open")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frame = None
    for _ in range(10):
        ok, frame = cap.read()
        if ok and frame is not None and frame.size:
            break
        time.sleep(0.1)
    cap.release()

    if frame is None or not frame.size:
        return CheckResult("camera", False, "camera opened but returned empty frame")

    out = Path(snapshot_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = cv2.imwrite(str(out), frame)
    h, w = frame.shape[:2]
    detail = f"/dev/video{device}, frame={w}x{h}, snapshot={out}"
    return CheckResult("camera", bool(written), detail if written else detail + "; snapshot write failed")


def check_ir() -> CheckResult:
    detect_detail = ""
    try:
        proc = subprocess.run(
            ["i2cdetect", "-y", str(config.I2C_BUS)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        detect_detail = "i2cdetect has 5a" if "5a" in proc.stdout.lower() else "i2cdetect missing 5a"
    except Exception as exc:
        detect_detail = f"i2cdetect failed: {type(exc).__name__}: {exc}"

    try:
        from smbus2 import SMBus
    except ImportError as exc:
        return CheckResult("ir_mlx90614", False, f"{detect_detail}; smbus2 import failed: {exc}")

    with SMBus(config.I2C_BUS) as bus:
        ambient = (bus.read_word_data(config.MLX90614_ADDR, 0x06) * 0.02) - 273.15
        obj = (bus.read_word_data(config.MLX90614_ADDR, 0x07) * 0.02) - 273.15

    ok = -20.0 <= ambient <= 80.0 and -20.0 <= obj <= 250.0 and "has 5a" in detect_detail
    detail = f"{detect_detail}; ambient={ambient:.2f}C, object={obj:.2f}C"
    return CheckResult("ir_mlx90614", ok, detail)


def _open_spi_no_cs():
    import spidev

    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1_000_000
    spi.no_cs = True
    return spi


def _read_adc_candidates(channel: int) -> tuple[int, int]:
    """Read one ADC channel as both MCP3208 and MCP3008 candidates.

    Repo code currently uses MCP3208; latest wiring plan names MCP3008.
    Returning both keeps the bench test useful while that hardware doc/code
    mismatch is resolved.
    """
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        raise RuntimeError(f"RPi.GPIO import failed: {exc}") from exc

    spi = _open_spi_no_cs()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.MQ2_CS_PIN, GPIO.OUT)

    def xfer(payload):
        GPIO.output(config.MQ2_CS_PIN, GPIO.LOW)
        time.sleep(0.00001)
        try:
            return spi.xfer2(payload)
        finally:
            GPIO.output(config.MQ2_CS_PIN, GPIO.HIGH)

    try:
        mcp3208_raw = xfer([6 | (channel >> 2), (channel & 3) << 6, 0])
        mcp3208 = ((mcp3208_raw[1] & 15) << 8) + mcp3208_raw[2]

        mcp3008_raw = xfer([1, (8 + channel) << 4, 0])
        mcp3008 = ((mcp3008_raw[1] & 3) << 8) + mcp3008_raw[2]
        return mcp3208, mcp3008
    finally:
        spi.close()
        GPIO.cleanup(config.MQ2_CS_PIN)


def check_mq2_adc() -> CheckResult:
    mcp3208, mcp3008 = _read_adc_candidates(config.MQ2_ADC_CH)
    ok = 0 <= mcp3208 <= 4095 and 0 <= mcp3008 <= 1023
    detail = (
        f"CH{config.MQ2_ADC_CH}; MCP3208_candidate={mcp3208}/4095, "
        f"MCP3008_candidate={mcp3008}/1023"
    )
    return CheckResult("mq2_adc", ok, detail)


def check_battery_adc() -> CheckResult:
    mcp3208, mcp3008 = _read_adc_candidates(config.BATTERY_ADC_CH)
    pin_v_3208 = (mcp3208 / 4095.0) * 3.3
    bat_v_3208 = pin_v_3208 * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)
    pin_v_3008 = (mcp3008 / 1023.0) * 3.3
    bat_v_3008 = pin_v_3008 * ((config.VDIV_R1 + config.VDIV_R2) / config.VDIV_R2)
    ok = 5.5 <= bat_v_3208 <= 9.0 or 5.5 <= bat_v_3008 <= 9.0
    detail = (
        f"CH{config.BATTERY_ADC_CH}; MCP3208_candidate={bat_v_3208:.2f}V, "
        f"MCP3008_candidate={bat_v_3008:.2f}V"
    )
    return CheckResult("battery_adc", ok, detail)


def check_ultrasonics() -> CheckResult:
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        return CheckResult("ultrasonics", False, f"RPi.GPIO import failed: {exc}")

    def read_one(name: str, trig_pin: int, echo_pin: int) -> tuple[str, bool, str]:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(trig_pin, GPIO.OUT)
            GPIO.output(trig_pin, GPIO.LOW)
            GPIO.setup(echo_pin, GPIO.IN)
            time.sleep(0.05)

            GPIO.output(trig_pin, GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(trig_pin, GPIO.LOW)

            timeout = time.time() + 0.05
            start_t = None
            while GPIO.input(echo_pin) == 0 and time.time() < timeout:
                start_t = time.time()
            if start_t is None:
                return name, False, "no echo start"

            stop_t = start_t
            while GPIO.input(echo_pin) == 1 and time.time() < timeout:
                stop_t = time.time()

            distance = ((stop_t - start_t) * 34300.0) / 2.0
            ok = 2.0 <= distance <= 400.0
            return name, ok, f"{distance:.1f}cm"
        except Exception as exc:
            return name, False, f"{type(exc).__name__}: {exc}"
        finally:
            try:
                GPIO.cleanup((trig_pin, echo_pin))
            except Exception:
                pass

    readings = [
        read_one("left", config.TRIG_LEFT, config.ECHO_LEFT),
        read_one("front", config.TRIG_FRONT, config.ECHO_FRONT),
        read_one("right", config.TRIG_RIGHT, config.ECHO_RIGHT),
    ]

    ok = all(item[1] for item in readings)
    detail = "; ".join(f"{name}={'PASS' if good else 'FAIL'} {msg}" for name, good, msg in readings)
    return CheckResult("ultrasonics", ok, detail)


def check_fusion_read() -> CheckResult:
    from m3_sensors.sensors import SensorsM3

    sensors = SensorsM3()
    ok = sensors.init_sensors()
    if not ok:
        return CheckResult("fusion_read", False, "init_sensors returned False")
    try:
        fusion = sensors.get_fusion_sensors()
    finally:
        sensors.cleanup()

    ok = 0 <= fusion.smoke_level <= 4095 and -20.0 <= fusion.ir_temp <= 250.0
    detail = f"smoke={fusion.smoke_level}/4095, smoke_alert={fusion.smoke_alert}, ir={fusion.ir_temp:.2f}C"
    return CheckResult("fusion_read", ok, detail)


def check_motor_driver_safe() -> CheckResult:
    """Exercise L298N GPIO/PWM setup with PWM duty 0 so wheels should not move."""
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        return CheckResult("motor_driver_safe", False, f"RPi.GPIO import failed: {exc}")

    pins = [config.MOTOR_IN1, config.MOTOR_IN2, config.MOTOR_IN3, config.MOTOR_IN4]
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in pins + [config.MOTOR_ENA, config.MOTOR_ENB]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    pwm_a = GPIO.PWM(config.MOTOR_ENA, 1000)
    pwm_b = GPIO.PWM(config.MOTOR_ENB, 1000)
    try:
        pwm_a.start(0)
        pwm_b.start(0)
        GPIO.output(config.MOTOR_IN1, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN2, GPIO.LOW)
        GPIO.output(config.MOTOR_IN3, GPIO.HIGH)
        GPIO.output(config.MOTOR_IN4, GPIO.LOW)
        time.sleep(0.2)
        for pin in pins:
            GPIO.output(pin, GPIO.LOW)
    finally:
        pwm_a.stop()
        pwm_b.stop()
        GPIO.cleanup(tuple(pins + [config.MOTOR_ENA, config.MOTOR_ENB]))

    return CheckResult(
        "motor_driver_safe",
        True,
        "L298N IN1-IN4 and ENA/ENB GPIO/PWM configured; PWM duty stayed 0",
    )


def check_alarm_outputs() -> CheckResult:
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        return CheckResult("alarm_outputs", False, f"RPi.GPIO import failed: {exc}")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.LED_PIN, GPIO.OUT)
    GPIO.setup(config.BUZZER_PIN, GPIO.OUT)
    try:
        GPIO.output(config.LED_PIN, GPIO.HIGH)
        GPIO.output(config.BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.25)
        GPIO.output(config.LED_PIN, GPIO.LOW)
        GPIO.output(config.BUZZER_PIN, GPIO.LOW)
    finally:
        GPIO.cleanup((config.LED_PIN, config.BUZZER_PIN))
    return CheckResult(
        "alarm_outputs",
        True,
        f"toggled LED GPIO{config.LED_PIN} and buzzer GPIO{config.BUZZER_PIN} for 0.25s",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Run encoder, camera, and IR checks")
    parser.add_argument("--encoders", action="store_true", help="Run wheel encoder pulse check")
    parser.add_argument("--camera", action="store_true", help="Run USB camera frame check")
    parser.add_argument("--ir", action="store_true", help="Run MLX90614 I2C check")
    parser.add_argument("--installed", action="store_true", help="Run currently installed sensor/actuator checks")
    parser.add_argument("--mq2", action="store_true", help="Run MQ-2 ADC check")
    parser.add_argument("--battery", action="store_true", help="Run battery ADC check")
    parser.add_argument("--ultrasonic", action="store_true", help="Run HC-SR04 distance checks")
    parser.add_argument("--alarm", action="store_true", help="Run LED/buzzer output check")
    parser.add_argument("--fusion", action="store_true", help="Run M3 fusion read through module")
    parser.add_argument("--motor-safe", action="store_true", help="Run safe L298N GPIO/PWM test without wheel motion")
    parser.add_argument("--encoder-seconds", type=float, default=10.0)
    parser.add_argument("--camera-device", type=int, default=0)
    parser.add_argument("--snapshot", default="runtime_data/snapshots/hardware_camera_check.jpg")
    args = parser.parse_args()

    if not any((
        args.all, args.encoders, args.camera, args.ir, args.installed,
        args.mq2, args.battery, args.ultrasonic, args.alarm, args.fusion,
        args.motor_safe,
    )):
        args.all = True

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RESULTS_PATH.exists():
        RESULTS_PATH.write_text("# SeeFire Bugunku Sensor Test Plani\n\n", encoding="utf-8")

    results: list[CheckResult] = []
    if args.all or args.encoders:
        results.append(run_check("encoders", lambda: check_encoders(args.encoder_seconds)))
    if args.all or args.camera:
        results.append(run_check("camera", lambda: check_camera(args.camera_device, args.snapshot)))
    if args.all or args.ir:
        results.append(run_check("ir_mlx90614", check_ir))
    if args.installed or args.mq2:
        results.append(run_check("mq2_adc", check_mq2_adc))
    if args.installed or args.battery:
        results.append(run_check("battery_adc", check_battery_adc))
    if args.installed or args.ultrasonic:
        results.append(run_check("ultrasonics", check_ultrasonics))
    if args.installed or args.alarm:
        results.append(run_check("alarm_outputs", check_alarm_outputs))
    if args.installed or args.fusion:
        results.append(run_check("fusion_read", check_fusion_read))
    if args.installed or args.motor_safe:
        results.append(run_check("motor_driver_safe", check_motor_driver_safe))

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    sys.exit(main())
