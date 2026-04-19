#ifndef M4_VISION_H
#define M4_VISION_H

/**
 * @file m4_vision.h
 * @brief AI & Vision Pipeline - public interface (YOLOv8n + OpenCV)
 * @author Emre Can Tuncer (200104004115), Semih Sarkoca (220104004038)
 * @date 2025-03-01
 * @version 0.1
 *
 * Changelog:
 * v0.1 (2025-03-01) - Initial draft: pipeline control, detection structs, snapshot
 */

#include <stdint.h>
#include <stdbool.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define M4_INPUT_WIDTH          320     /**< YOLO input frame width (px) */
#define M4_INPUT_HEIGHT         320     /**< YOLO input frame height (px) */
#define M4_FPS_TARGET           5       /**< Minimum acceptable inference FPS */
#define M4_CONF_THRESHOLD       0.5f    /**< Default YOLO confidence threshold */
#define M4_MAX_DETECTIONS       16      /**< Max detections stored per frame */
#define M4_CLASS_FIRE           0       /**< YOLO class index for "fire" */
#define M4_CLASS_SMOKE          1       /**< YOLO class index for "smoke" */

/* ── Data Types ─────────────────────────────────────────────────────────── */

/** @brief Status codes returned by M4 functions */
typedef enum {
    M4_OK              =  0,  /**< Success */
    M4_ERR_INIT        = -1,  /**< Camera or model failed to load */
    M4_ERR_NO_FRAME    = -2,  /**< No frame available yet */
    M4_ERR_THREAD      = -3,  /**< Inference thread error */
    M4_ERR_INVALID     = -4   /**< NULL pointer or bad parameter */
} m4_status_t;

/** @brief Bounding box in pixel coordinates */
typedef struct {
    uint16_t x;     /**< Top-left x coordinate */
    uint16_t y;     /**< Top-left y coordinate */
    uint16_t w;     /**< Bounding box width */
    uint16_t h;     /**< Bounding box height */
} m4_bbox_t;

/**
 * @brief Single object detection result from YOLOv8n inference.
 */
typedef struct {
    uint8_t    class_id;           /**< Detected class: M4_CLASS_FIRE or M4_CLASS_SMOKE */
    char       class_name[16];     /**< Human-readable label: "fire" or "smoke" */
    float      confidence;         /**< Detection confidence score (0.0–1.0) */
    m4_bbox_t  bbox;               /**< Bounding box in 320×320 pixel space */
    double     frame_timestamp;    /**< Unix epoch of the captured frame */
} m4_detection_t;

/**
 * @brief Complete result from the latest inference cycle.
 *        Consumed by M6 Decision Engine on every FSM iteration.
 */
typedef struct {
    m4_detection_t detections[M4_MAX_DETECTIONS]; /**< Array of detections */
    uint8_t        detection_count;               /**< Number of valid entries */
    float          fps;                            /**< Current inference FPS */
    bool           is_running;                    /**< True if pipeline is active */
    double         result_timestamp;              /**< Unix epoch of this result */
} m4_vision_result_t;

/* ── Vision Pipeline API ────────────────────────────────────────────────── */

/**
 * @brief Initialise the camera and load the YOLOv8n INT8 model.
 *        Spawns a background inference thread.
 * @return M4_OK on success, M4_ERR_INIT if camera or model fails to load.
 */
m4_status_t m4_start_pipeline(void);

/**
 * @brief Stop the inference thread and release camera resources.
 * @return M4_OK always.
 */
m4_status_t m4_stop_pipeline(void);

/**
 * @brief Retrieve the most recent inference result (non-blocking).
 *        Thread-safe: uses an internal mutex to copy the latest result.
 *        Called by M6 Decision Engine on every FSM iteration (~500 ms).
 * @param result_out  Pointer to caller-owned m4_vision_result_t struct.
 * @return M4_OK on success, M4_ERR_NO_FRAME if pipeline not yet ready,
 *         M4_ERR_INVALID if result_out is NULL.
 */
m4_status_t m4_get_latest_result(m4_vision_result_t *result_out);

/**
 * @brief Capture the current camera frame and encode it as JPEG.
 *        Called by M6 only when entering ALARM state.
 * @param buf      Caller-owned buffer to receive JPEG bytes.
 * @param buf_size Size of buf in bytes.
 * @param out_len  Pointer to size_t; receives the number of bytes written.
 * @return M4_OK on success, M4_ERR_NO_FRAME if no frame available,
 *         M4_ERR_INVALID if buf is NULL or too small.
 */
m4_status_t m4_capture_snapshot(uint8_t *buf, uint32_t buf_size, uint32_t *out_len);

/**
 * @brief Query whether the inference pipeline is currently running.
 * @param running_out  Pointer to bool; set to true if pipeline is active.
 * @return M4_OK on success, M4_ERR_INVALID if running_out is NULL.
 */
m4_status_t m4_is_running(bool *running_out);

#endif /* M4_VISION_H */
