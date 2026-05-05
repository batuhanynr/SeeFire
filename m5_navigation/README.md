# M5 Navigation

Current purpose: traverse a **static, pre-drawn route** from south to north, trigger midpoint/waypoint snapshot hooks, and bypass obstacles using front ultrasonic plus encoder-backed motion.

## Current Behavior

- No exploration
- No occupancy grid generation
- No automatic map persistence
- Start position is verified with left/right HC-SR04 readings
- Route comes from `config.WAYPOINTS`
- Front sensor triggers obstacle avoidance
- Obstacle bypass direction is chosen by M4 camera hint or left/right ultrasonic fallback

## Python Entry Points

- `NavigationController`
- `ObstacleAvoidance`
- `PositionVerifier`

## Dependencies

- M2 distance/turn API
- M3 `left/front/right` navigation readings
- M4 optional turn-direction hint

## Integration Status

- Implemented in Python
- Not yet wired into a real M6 FSM
- Can be exercised standalone

## Notes

See `navigation_modulu.md` for the current design rationale. Older drafts that mention wall-following, occupancy maps, or Arduino are obsolete for this repository state.
