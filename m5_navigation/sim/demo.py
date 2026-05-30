"""Run pre-built scenarios in the M5 simulator.

Usage:
    python3 -m m5_navigation.sim.demo                  # single obstacle, interactive
    python3 -m m5_navigation.sim.demo wall             # wall-hugging obstacle (retreat)
    python3 -m m5_navigation.sim.demo blocked          # both sides blocked (abort)
    python3 -m m5_navigation.sim.demo <name> --save run.gif
"""
import argparse
import logging

from .world import World, Obstacle, Robot
from .mock_drivers import install_mock_drivers
from .visualizer import animate


def _scenario_single():
    """One small obstacle in the middle of the corridor."""
    return World(
        width=60.0, height=220.0,
        obstacles=[Obstacle(x=20.0, y=70.0, w=20.0, h=15.0)],
        robot=Robot(x=30.0, y=0.0, heading_deg=90.0),
        turn_hint=None,            # let ultrasonic decide
    )


def _scenario_wall():
    """Obstacle touches the right wall → RIGHT bypass should fail, LEFT succeeds."""
    return World(
        width=60.0, height=220.0,
        obstacles=[Obstacle(x=15.0, y=70.0, w=45.0, h=15.0)],
        robot=Robot(x=30.0, y=0.0, heading_deg=90.0),
        turn_hint="RIGHT",         # force RIGHT first to demonstrate retreat
    )


def _scenario_blocked():
    """Obstacle spans the whole corridor → both directions blocked."""
    return World(
        width=60.0, height=220.0,
        obstacles=[Obstacle(x=0.0, y=70.0, w=60.0, h=15.0)],
        robot=Robot(x=30.0, y=0.0, heading_deg=90.0),
        turn_hint="RIGHT",
    )


def _scenario_multi():
    """Three sectors. Two obstacles placed so the user can compare scan
    triggers in different situations:
      - Sector 1 (0→90, mid=45): route clear at midpoint → scan happens
        on-route. Then robot encounters an obstacle at y=60-75 and bypasses.
      - Sector 2 (90→180, mid=135): obstacle at y=115-130 forces a bypass;
        midpoint y=135 falls *during* the forward-pass → off-route scan
        (robot is shifted east or west of the route line).
      - Sector 3 (180→270, mid=225): clear corridor → on-route scan.
    Each sector yields one 4-direction scan + one waypoint snapshot.
    """
    return World(
        width=60.0, height=320.0,
        obstacles=[
            Obstacle(x=20.0, y=60.0,  w=20.0, h=15.0),
            Obstacle(x=20.0, y=115.0, w=25.0, h=15.0),
        ],
        robot=Robot(x=30.0, y=0.0, heading_deg=90.0),
        turn_hint=None,
    )


SCENARIOS = {
    "single":  _scenario_single,
    "wall":    _scenario_wall,
    "blocked": _scenario_blocked,
    "multi":   _scenario_multi,
}

WAYPOINTS = {
    "single":  [(150.0, 1)],
    "wall":    [(150.0, 1)],
    "blocked": [(150.0, 1)],
    "multi":   [(90.0, 1), (180.0, 2), (270.0, 3)],
}


def run(name: str, save_path: str = None, interval_ms: int = 300):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    world = SCENARIOS[name]()
    install_mock_drivers(world)

    # Import AFTER patching so the controller sees mocked modules.
    from m5_navigation.navigation import NavigationController
    from m5_navigation.obstacle import ObstacleBlockedError

    controller = NavigationController(snapshot_callback=world.snapshot_event)
    try:
        controller.run(waypoints=WAYPOINTS[name])
    except ObstacleBlockedError as e:
        logging.warning("[SIM] Navigation aborted: %s", e)
        world.snapshot_event("ABORT")
    except RuntimeError as e:
        logging.warning("[SIM] RuntimeError: %s", e)

    print(f"Recorded {len(world.frames)} frames.")
    animate(world, save_path=save_path, interval_ms=interval_ms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", default="single",
                        choices=list(SCENARIOS))
    parser.add_argument("--save", help="Save animation as .gif instead of showing.")
    parser.add_argument("--interval", type=int, default=300,
                        help="Milliseconds per frame (default 300).")
    args = parser.parse_args()
    run(args.scenario, save_path=args.save, interval_ms=args.interval)


if __name__ == "__main__":
    main()
