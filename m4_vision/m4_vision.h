#ifndef M4_VISION_H
#define M4_VISION_H

/**
 * @file m4_vision.h
 * @brief Current public design notes for M4 Vision
 *
 * The live Python module currently provides camera lifecycle management and
 * turn-direction hinting for M5. Fire/smoke inference remains planned work.
 */

#include <stdint.h>
#include <stdbool.h>

#define M4_FRAME_WIDTH        640
#define M4_FRAME_HEIGHT       480

typedef enum {
    M4_OK              =  0,
    M4_ERR_INIT        = -1,
    M4_ERR_NO_FRAME    = -2,
    M4_ERR_INVALID     = -3
} m4_status_t;

typedef enum {
    M4_TURN_NONE   = 0,
    M4_TURN_LEFT   = 1,
    M4_TURN_RIGHT  = 2
} m4_turn_hint_t;

m4_status_t m4_init(void);
m4_status_t m4_capture_frame(void *frame_out);
m4_status_t m4_determine_turn_direction(m4_turn_hint_t *hint_out);
m4_status_t m4_close(void);

#endif /* M4_VISION_H */
