#ifndef M1_CHASSIS_H
#define M1_CHASSIS_H

/**
 * @file m1_chassis.h
 * @brief Chassis & Mechanical Assembly - hardware specifications
 * @author Halil Buğra Şen (230104004088), Alperen Şahin (220104004943)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: chassis specs, motor mounts, sensor mounting points
 */

#include <stdint.h>
#include <stdbool.h>

/* ── Physical Dimensions ────────────────────────────────────────────────── */
#define M1_CHASSIS_LENGTH_MM    200     /**< Chassis length (mm) */
#define M1_CHASSIS_WIDTH_MM     150     /**< Chassis width (mm) */
#define M1_CHASSIS_HEIGHT_MM    100     /**< Chassis height (mm) */
#define M1_WHEEL_DIAMETER_MM    65      /**< Wheel diameter (mm) */
#define M1_WHEEL_BASE_MM        140     /**< Distance between front and rear axles (mm) */
#define M1_TRACK_WIDTH_MM       120     /**< Distance between left and right wheels (mm) */

/* ── Motor Specifications ───────────────────────────────────────────────── */
#define M1_MOTOR_TYPE           "DC 6V Motor with Gearbox"  /**< Motor type */
#define M1_MOTOR_VOLTAGE_V      6.0f    /**< Rated voltage (V) */
#define M1_MOTOR_RPM_NO_LOAD    100     /**< No-load RPM */
#define M1_MOTOR_TORQUE_NM      0.8f    /**< Stall torque (N⋅m) */
#define M1_NUM_MOTORS           4       /**< Total motors (4WD) */

/* ── Power System ───────────────────────────────────────────────────────── */
#define M1_BATTERY_TYPE         "LiPo 2S1P (7.4V nominal)"  /**< Battery type */
#define M1_BATTERY_CAPACITY_MAH 2200    /**< Battery capacity (mAh) */
#define M1_BATTERY_VOLTAGE_V    7.4f    /**< Nominal voltage (V) */

/* ── Sensor Mounting Points ─────────────────────────────────────────────── */
#define M1_SENSOR_FRONT_MM      25      /**< Front sensor offset from front edge (mm) */
#define M1_SENSOR_SIDE_MM       15      /**< Side sensor offset from wheel edge (mm) */
#define M1_SENSOR_HEIGHT_MM     50      /**< Sensor mounting height (mm) */

/* ── Motor Mount Interface ──────────────────────────────────────────────── */
typedef struct {
    uint8_t motor_id;                   /**< Motor index (0-3) */
    uint16_t pwm_pin;                   /**< PWM control pin (RPi GPIO) */
    uint16_t dir_pin_a;                 /**< Direction pin A (RPi GPIO) */
    uint16_t dir_pin_b;                 /**< Direction pin B (RPi GPIO) */
} M1_MotorMount;

/**
 * @brief Get motor mount configuration by ID
 * @param motor_id Motor index (0-3: FL, FR, RL, RR)
 * @return Motor mount configuration
 */
M1_MotorMount m1_get_motor_mount(uint8_t motor_id);

/**
 * @brief Verify chassis structural integrity (debugging only)
 * @return true if all motor mounts and sensor points are accessible
 */
bool m1_verify_assembly(void);

#endif /* M1_CHASSIS_H */