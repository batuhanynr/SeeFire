import logging

import config
import m7_logging
import m3_sensors
import m4_vision

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("seefire")


def init() -> None:
    config.validate_gpio_pins()
    config.validate_fusion_weights()
    logger.info("Config validation passed")

    m7_logging.init()
    logger.info("M7 Data Logging initialized")

    from m2_motor import motor
    motor.init_hardware()
    logger.info("M2 Motor & Power initialized")

    m3_sensors.init_sensors()
    logger.info("M3 Sensor Integration initialized")

    m4_vision.init()
    logger.info("M4 Vision initialized")
    logger.info("M5 Navigation and M6 Decision are not wired into main yet")


def main():
    logger.info("SeeFire starting...")
    init()
    logger.info("SeeFire initialization complete.")


if __name__ == "__main__":
    main()
