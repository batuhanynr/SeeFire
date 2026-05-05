#ifndef M3_SENSORS_H
#define M3_SENSORS_H

/**
 * @file m3_sensors.h
 * @brief Current public design notes for M3 Sensor Integration
 *
 * Mirrors the live Python module at `m3_sensors/sensors.py`.
 */

#include <stdint.h>
#include <stdbool.h>

#define M3_SMOKE_THRESHOLD_DEFAULT   300
#define M3_IR_TEMP_THRESHOLD_DEFAULT 60.0f
#define M3_ULTRASONIC_COUNT          3
#define M3_ADC_MAX                   4095
#define M3_I2C_MLX90614_ADDR         0x5A

#define M3_TRIG_LEFT_PIN             23
#define M3_ECHO_LEFT_PIN             24
#define M3_TRIG_RIGHT_PIN            25
#define M3_ECHO_RIGHT_PIN            8
#define M3_TRIG_FRONT_PIN            16
#define M3_ECHO_FRONT_PIN            20

#define M3_MQ2_ADC_CH                0
#define M3_BATTERY_ADC_CH            1
#define M3_SPI_CS_PIN                5

typedef enum {
    M3_OK             =  0,
    M3_ERR_INIT       = -1,
    M3_ERR_READ       = -2,
    M3_ERR_I2C        = -3,
    M3_ERR_INVALID    = -4,
    M3_ERR_WARMUP     = -5
} m3_status_t;

typedef struct {
    int32_t smoke_level;   /* 0..4095 in current code */
    bool smoke_alert;
    float ir_temp;
    double timestamp;
} m3_fusion_data_t;

typedef struct {
    float left_cm;
    float front_cm;
    float right_cm;
    double timestamp;
} m3_nav_data_t;

m3_status_t m3_init_sensors(void);
m3_status_t m3_get_fusion_sensors(m3_fusion_data_t *data_out);
m3_status_t m3_get_navigation_sensors(m3_nav_data_t *data_out);
m3_status_t m3_get_navigation_sensors_filtered(m3_nav_data_t *data_out, uint8_t samples);
m3_status_t m3_read_battery_adc(int32_t *adc_out);
m3_status_t m3_cleanup(void);

#endif /* M3_SENSORS_H */
