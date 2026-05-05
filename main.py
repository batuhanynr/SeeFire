import logging

import config
import m7_logging
import m3_sensors

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

    # M4, M5, M6 starting soon...
    # from m4_vision import vision
    # from m5_navigation import navigation
    # from m6_decision import decision


def main():
    logger.info("SeeFire starting...")
    init()
    logger.info("SeeFire ready. Entering main loop.")


if __name__ == "__main__":
    main()
