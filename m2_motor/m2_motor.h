#ifndef M2_MOTOR_H
#define M2_MOTOR_H

/**
 * @file m2_motor.h
 * @brief Motor Control & Power Management - public interface
 * @author Emre Can Tuncer (200104004115)  Bekir Emre Sarpinar (220104004039)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: motor_drive, motor_stop, set_alarm
 */
 
#include <stdint.h>
#include <stdbool.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M2_PWM_FREQ_HZ        1000    /**< Recommended PWM frequency for L298N */
#define M2_SPEED_MIN          0       /**< Minimum duty cycle (%) */
#define M2_SPEED_MAX          100     /**< Maximum duty cycle (%) */
#define M2_BATTERY_LOW_V      9.6f    /**< Low battery warning threshold (V) */
#define M2_BATTERY_CRIT_V     8.4f    /**< Critical battery threshold (V) */

/* GPIO Pin assignments (mirrored from config.py) */
#define M2_PIN_IN1            17
#define M2_PIN_IN2            18
#define M2_PIN_IN3            27
#define M2_PIN_IN4            22
#define M2_PIN_ENA            12
#define M2_PIN_ENB            13
#define M2_PIN_LED            26
#define M2_PIN_BUZZER         19

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M2 functions */
typedef enum {
    M2_OK            =  0,  /**< Operation successful */
    M2_ERR_INIT      = -1,  /**< GPIO initialisation failed */
    M2_ERR_INVALID   = -2,  /**< Invalid parameter */
    M2_ERR_HARDWARE  = -3   /**< Hardware fault detected */
} m2_status_t;

/** @brief Motor movement directions */
typedef enum {
    M2_DIR_FORWARD     = 0, /**< Both motors forward */
    M2_DIR_BACKWARD    = 1, /**< Both motors backward */
    M2_DIR_TURN_LEFT   = 2, /**< Left motor back, right motor forward */
    M2_DIR_TURN_RIGHT  = 3, /**< Right motor back, left motor forward */
    M2_DIR_STOP        = 4  /**< All motors stopped */
} m2_direction_t;

/** @brief LED blink pattern identifiers */
typedef enum {
    M2_BLINK_FAST   = 0,    /**< 10 Hz blink — alarm active */
    M2_BLINK_SLOW   = 1,    /**< 1 Hz blink — low battery */
    M2_BLINK_SOLID  = 2     /**< Constant on — system active */
} m2_blink_pattern_t;

/** @brief Motor & alarm state snapshot */
typedef struct {
    m2_direction_t  direction;      /**< Current movement direction */
    uint8_t         speed;          /**< Current duty cycle (0-100) */
    float           battery_v;      /**< Last measured battery voltage (V) */
    bool            led_on;         /**< LED currently active */
    bool            buzzer_on;      /**< Buzzer currently active */
} m2_state_t;

/* ── Public Functions ───────────────────────────────────────────────────── */

/**
 * @brief Initialise GPIO pins and PWM channels for motor control.
 * @return M2_OK on success, M2_ERR_INIT on failure.
 */
m2_status_t m2_init_motors(void);

/**
 * @brief Drive motors in the specified direction at the given speed.
 * @param direction  One of the m2_direction_t values.
 * @param speed      Duty cycle percentage (0–100). Clamped to valid range.
 * @return M2_OK on success, M2_ERR_INVALID if parameters are out of range.
 */
m2_status_t m2_motor_drive(m2_direction_t direction, uint8_t speed);

/**
 * @brief Immediately stop all motors (zero duty cycle, direction STOP).
 * @return M2_OK always.
 */
m2_status_t m2_motor_stop(void);

/**
 * @brief Rotate the robot by a target angle using timed differential drive.
 * @param angle_deg  Target rotation in degrees (positive = clockwise).
 * @param speed      Duty cycle percentage (0–100).
 * @return M2_OK on success, M2_ERR_INVALID if speed is out of range.
 */
m2_status_t m2_motor_turn(float angle_deg, uint8_t speed);

/**
 * @brief Read the current LiPo battery voltage via ADC voltage divider.
 * @param voltage_out  Pointer to float where measured voltage (V) is stored.
 * @return M2_OK on success, M2_ERR_HARDWARE on ADC read failure.
 */
m2_status_t m2_get_battery_voltage(float *voltage_out);

/**
 * @brief Activate or deactivate the alarm LED and buzzer.
 * @param led_on     true to turn LED on, false to turn off.
 * @param buzzer_on  true to activate buzzer, false to silence.
 * @return M2_OK always.
 */
m2_status_t m2_set_alarm(bool led_on, bool buzzer_on);

/**
 * @brief Start a non-blocking LED blink pattern on a background thread.
 * @param pattern  Blink pattern (M2_BLINK_FAST, M2_BLINK_SLOW, M2_BLINK_SOLID).
 * @return M2_OK on success, M2_ERR_INIT if thread cannot be created.
 */
m2_status_t m2_blink_led(m2_blink_pattern_t pattern);

/**
 * @brief Retrieve a snapshot of the current motor and alarm state.
 * @param state_out  Pointer to caller-owned m2_state_t struct.
 * @return M2_OK on success, M2_ERR_INVALID if state_out is NULL.
 */
m2_status_t m2_get_state(m2_state_t *state_out);

/**
 * @brief Release GPIO resources and stop PWM channels.
 * @return M2_OK always.
 */
m2_status_t m2_cleanup(void);

#endif /* M2_MOTOR_H */
