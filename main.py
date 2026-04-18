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

    # M2 init would go here when available
    # m2_motor.init()

    m3_sensors.init_sensors()
    logger.info("M3 Sensor Integration initialized")

    # M4 init would go here when available
    # M5 init depends on M3
    # M6 init depends on M3, M4


def main():
    logger.info("SeeFire starting...")
    init()
    logger.info("SeeFire ready. Entering main loop.")


if __name__ == "__main__":
    main()
