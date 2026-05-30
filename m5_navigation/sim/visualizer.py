"""Matplotlib animation for a recorded World run.

Usage:
    from m5_navigation.sim import World, Obstacle, install_mock_drivers, animate
    from m5_navigation.navigation import NavigationController

    world = World(width=100, height=300, obstacles=[Obstacle(40, 80, 20, 15)])
    install_mock_drivers(world)
    NavigationController(snapshot_callback=world.snapshot_event).run([(150, 1)])
    animate(world)               # interactive window
    # or: animate(world, save_path="run.gif")
"""
import math


def animate(world, save_path=None, interval_ms=300, robot_radius=5.0):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.animation import FuncAnimation, PillowWriter
    except ImportError:
        print("matplotlib not installed — printing text trace instead:")
        for i, f in enumerate(world.frames):
            print(f"  [{i:3d}] {f.label:30s}  pos=({f.x:6.1f},{f.y:6.1f}) "
                  f"hdg={f.heading_deg:5.1f}  L={f.left_cm:6.1f} "
                  f"F={f.front_cm:6.1f} R={f.right_cm:6.1f}")
        return

    fig, ax = plt.subplots(figsize=(6, 10))
    ax.set_xlim(-10, world.width + 10)
    ax.set_ylim(-10, world.height + 10)
    ax.set_aspect("equal")
    ax.set_xlabel("x (cm, east)")
    ax.set_ylabel("y (cm, north)")

    # Map outline.
    ax.add_patch(patches.Rectangle((0, 0), world.width, world.height,
                                   fill=False, edgecolor="black", linewidth=1.5))
    # Obstacles.
    for ob in world.obstacles:
        ax.add_patch(patches.Rectangle((ob.x, ob.y), ob.w, ob.h,
                                       facecolor="#d33", alpha=0.6, edgecolor="darkred"))

    trajectory_xs, trajectory_ys = [], []
    traj_line, = ax.plot([], [], color="#3a8", linewidth=1.2, alpha=0.7)

    robot_circle = patches.Circle((0, 0), robot_radius, facecolor="#37c", edgecolor="navy")
    ax.add_patch(robot_circle)

    heading_line, = ax.plot([], [], color="navy", linewidth=2)
    ray_lines = [ax.plot([], [], color=c, linewidth=0.8, alpha=0.5)[0]
                 for c in ("#888", "#888", "#888")]   # left, front, right

    title = ax.set_title("")

    def init():
        return [traj_line, robot_circle, heading_line, *ray_lines, title]

    def update(i):
        f = world.frames[i]
        trajectory_xs.append(f.x)
        trajectory_ys.append(f.y)
        traj_line.set_data(trajectory_xs, trajectory_ys)
        robot_circle.center = (f.x, f.y)

        rad = math.radians(f.heading_deg)
        hx = f.x + robot_radius * 1.8 * math.cos(rad)
        hy = f.y + robot_radius * 1.8 * math.sin(rad)
        heading_line.set_data([f.x, hx], [f.y, hy])

        for line, (off, dist) in zip(
            ray_lines,
            [(90, f.left_cm), (0, f.front_cm), (-90, f.right_cm)],
        ):
            a = math.radians(f.heading_deg + off)
            ex = f.x + dist * math.cos(a)
            ey = f.y + dist * math.sin(a)
            line.set_data([f.x, ex], [f.y, ey])

        title.set_text(
            f"[{i+1}/{len(world.frames)}] {f.label}\n"
            f"L={f.left_cm:.1f}  F={f.front_cm:.1f}  R={f.right_cm:.1f}"
        )
        return [traj_line, robot_circle, heading_line, *ray_lines, title]

    anim = FuncAnimation(fig, update, frames=len(world.frames),
                         init_func=init, interval=interval_ms,
                         blit=False, repeat=False)

    if save_path:
        anim.save(save_path, writer=PillowWriter(fps=max(1, 1000 // interval_ms)))
        print(f"Animation saved to {save_path}")
    else:
        plt.show()
    return anim
