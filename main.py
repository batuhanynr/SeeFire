import logging
import signal
import sys

import config
import m7_logging
import m3_sensors
import m4_vision
from m2_motor import motor
from m6_decision.decision import DecisionEngine

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

    motor.init_hardware()
    logger.info("M2 Motor & Power initialized")

    m3_sensors.init_sensors()
    logger.info("M3 Sensor Integration initialized")

    m4_vision.init()
    logger.info("M4 Vision initialized")


def signal_handler(sig, frame):
    logger.info("Interrupt received, shutting down...")
    motor.stop()
    motor.cleanup()
    m3_sensors.cleanup()
    m4_vision.close()
    sys.exit(0)


def main():
    logger.info("SeeFire starting...")
    signal.signal(signal.SIGINT, signal_handler)

    try:
        init()
        logger.info("SeeFire initialization complete.")

        engine = DecisionEngine()
        logger.info("Starting Decision Engine...")
        engine.start()

    except Exception as e:
        logger.error("Fatal error during execution: %s", e, exc_info=True)
        motor.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
