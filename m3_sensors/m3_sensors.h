#ifndef M3_SENSORS_H
#define M3_SENSORS_H

/**
 * @file m3_sensors.h
 * @brief Sensor Integration Hub - public interface
 * @author Alperen Sahin (220104004943), Bekir Emre Sarpinar (220104004039), Batuhan Yanar (220104004059)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: sensor init, fusion API, navigation API
 */

#include <stdint.h>
#include <stdbool.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M3_SMOKE_THRESHOLD_DEFAULT   300    /**< MQ-2 ADC alarm level (0-1023) */
#define M3_IR_TEMP_THRESHOLD_DEFAULT 60.0f  /**< MLX90614 surface alarm temp (°C) */
#define M3_ULTRASONIC_COUNT          2      /**< Number of HC-SR04 sensors */
#define M3_ADC_MAX                   1023   /**< Maximum MQ-2 ADC reading */
#define M3_I2C_MLX90614_ADDR         0x5A   /**< MLX90614 I2C address */
#define M3_I2C_MPU6050_ADDR          0x68   /**< MPU6050 I2C address */
#define M3_TRIG_LEFT_PIN             23
#define M3_ECHO_LEFT_PIN             24
#define M3_TRIG_RIGHT_PIN            25
#define M3_ECHO_RIGHT_PIN            8
#define M3_DHT22_PIN                 4
#define M3_MQ2_CS_PIN                5

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M3 functions */
typedef enum {
    M3_OK             =  0,  /**< Success */
    M3_ERR_INIT       = -1,  /**< Sensor initialisation failed */
    M3_ERR_READ       = -2,  /**< Sensor read timeout or CRC error */
    M3_ERR_I2C        = -3,  /**< I2C bus error */
    M3_ERR_INVALID    = -4   /**< Invalid parameter */
} m3_status_t;

/**
 * @brief Sensor fusion data packet consumed by M6 Decision Engine.
 *        Populated by get_fusion_sensors(); all fields always present.
 */
typedef struct {
    int32_t smoke_level;    /**< MQ-2 raw ADC value (0–1023) */
    bool    smoke_alert;    /**< True if smoke_level exceeds configured threshold */
    float   ir_temp;        /**< MLX90614 object surface temperature (°C) */
    float   ambient_temp;   /**< DHT22 ambient air temperature (°C) */
    float   humidity;       /**< DHT22 relative humidity (%) */
    double  timestamp;      /**< Unix epoch seconds at moment of sampling */
} m3_fusion_data_t;

/**
 * @brief Ultrasonic distance readings consumed by M5 Navigation.
 */
typedef struct {
    float left_cm;          /**< HC-SR04 left sensor distance (cm); -1 = error */
    float right_cm;         /**< HC-SR04 right sensor distance (cm); -1 = error */
    double timestamp;       /**< Unix epoch seconds at moment of sampling */
} m3_ultrasonic_t;

/**
 * @brief Full navigation sensor packet consumed by M5 Navigation.
 */
typedef struct {
    m3_ultrasonic_t ultrasonic;  /**< Distance readings from both HC-SR04 sensors */
    float           imu_heading; /**< MPU6050 yaw angle in degrees (0–360) */
    double          timestamp;   /**< Unix epoch seconds */
} m3_nav_data_t;

/* ── Configuration API ──────────────────────────────────────────────────── */

/**
 * @brief Initialise all sensors: MQ-2, MLX90614, DHT22, HC-SR04 × 2, MPU6050.
 * @return M3_OK if all sensors initialised, M3_ERR_INIT on partial/full failure.
 */
m3_status_t m3_init_sensors(void);

/**
 * @brief Override the MQ-2 smoke alarm threshold.
 * @param threshold  ADC value (0–1023) above which smoke_alert becomes true.
 * @return M3_OK on success, M3_ERR_INVALID if threshold is out of range.
 */
m3_status_t m3_set_smoke_threshold(int32_t threshold);

/**
 * @brief Override the IR surface temperature alarm threshold.
 * @param threshold_c  Temperature in °C above which ir_temp triggers VERIFY state.
 * @return M3_OK on success, M3_ERR_INVALID if value is unreasonable.
 */
m3_status_t m3_set_ir_temp_threshold(float threshold_c);

/* ── Fusion Sensor API (→ M6) ───────────────────────────────────────────── */

/**
 * @brief Read all fire-detection sensors and return a fused data packet.
 *        Called by M6 Decision Engine approximately every 500 ms.
 * @param data_out  Pointer to caller-owned m3_fusion_data_t struct.
 * @return M3_OK on success, M3_ERR_READ if any sensor read fails.
 */
m3_status_t m3_get_fusion_sensors(m3_fusion_data_t *data_out);

/* ── Navigation Sensor API (→ M5) ───────────────────────────────────────── */

/**
 * @brief Read both HC-SR04 ultrasonic sensors and return distances.
 *        Called by M5 Navigation approximately every 100–200 ms.
 * @param data_out  Pointer to caller-owned m3_ultrasonic_t struct.
 * @return M3_OK on success, M3_ERR_READ on timeout.
 */
m3_status_t m3_get_ultrasonic_distances(m3_ultrasonic_t *data_out);

/**
 * @brief Read the MPU6050 IMU and return current heading in degrees.
 * @param heading_out  Pointer to float where yaw angle (0–360°) is stored.
 * @return M3_OK on success, M3_ERR_I2C on bus failure.
 */
m3_status_t m3_get_imu_heading(float *heading_out);

/**
 * @brief Read all navigation sensors (ultrasonic + IMU) in one call.
 *        Called by M5 Navigation approximately every 100–200 ms.
 * @param data_out  Pointer to caller-owned m3_nav_data_t struct.
 * @return M3_OK on success, M3_ERR_READ or M3_ERR_I2C on failure.
 */
m3_status_t m3_get_navigation_sensors(m3_nav_data_t *data_out);

/**
 * @brief Release GPIO and I2C resources.
 * @return M3_OK always.
 */
m3_status_t m3_cleanup(void);

#endif /* M3_SENSORS_H */
