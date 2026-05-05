#ifndef M2_MOTOR_H
#define M2_MOTOR_H

/**
 * @file m2_motor.h
 * @brief Current public design notes for M2 Motor & Power
 *
 * This header mirrors the live Python module at `m2_motor/motor.py`.
 * It is a documentation header, not a compiled source dependency.
 */

#include <stdint.h>
#include <stdbool.h>

/* Current constants mirrored from config.py */
#define M2_PWM_FREQ_HZ        1000
#define M2_SPEED_MIN          0
#define M2_SPEED_MAX          100
#define M2_BATTERY_MAX_V      8.4f
#define M2_BATTERY_NOMINAL_V  7.4f
#define M2_BATTERY_LOW_V      6.8f
#define M2_BATTERY_CRIT_V     6.4f
#define M2_VDIV_R1_OHM        20000.0f
#define M2_VDIV_R2_OHM        10000.0f

/* GPIO pin assignments */
#define M2_PIN_IN1            17
#define M2_PIN_IN2            18
#define M2_PIN_IN3            27
#define M2_PIN_IN4            22
#define M2_PIN_ENA            12
#define M2_PIN_ENB            13
#define M2_PIN_LED            26
#define M2_PIN_BUZZER         19
#define M2_PIN_ENC_LEFT       6
#define M2_PIN_ENC_RIGHT      21

typedef enum {
    M2_OK            =  0,
    M2_ERR_INIT      = -1,
    M2_ERR_INVALID   = -2,
    M2_ERR_HARDWARE  = -3
} m2_status_t;

typedef enum {
    M2_DIR_FORWARD     = 0,
    M2_DIR_BACKWARD    = 1,
    M2_DIR_TURN_LEFT   = 2,
    M2_DIR_TURN_RIGHT  = 3,
    M2_DIR_STOP        = 4
} m2_direction_t;

typedef struct {
    m2_direction_t direction;
    uint8_t speed;
    float battery_v;
    bool led_on;
    bool buzzer_on;
    float total_distance_cm;
} m2_state_t;

/* Current Python-facing API concepts */
m2_status_t m2_init_hardware(void);
m2_status_t m2_motor_drive(m2_direction_t direction, uint8_t speed);
m2_status_t m2_motor_turn(float angle_deg, uint8_t speed);
m2_status_t m2_motor_stop(void);
m2_status_t m2_set_alarm(bool led_on, bool buzzer_on);
m2_status_t m2_get_battery_voltage(float *voltage_out);
m2_status_t m2_drive_distance_cm(float distance_cm);
m2_status_t m2_turn_left_90(void);
m2_status_t m2_turn_right_90(void);
m2_status_t m2_stop(void);
m2_status_t m2_get_total_distance_cm(float *distance_out);
m2_status_t m2_set_total_distance_cm(float distance_cm);

#endif /* M2_MOTOR_H */
