"""M5 navigation simulator.

Provides a 2D ground-truth world, ray-cast sensor model, and matplotlib
visualizer so the navigation algorithm can be exercised step-by-step on a
dev machine without any Raspberry Pi hardware.
"""
from .world import World, Obstacle, Robot
from .mock_drivers import install_mock_drivers
from .visualizer import animate

__all__ = ["World", "Obstacle", "Robot", "install_mock_drivers", "animate"]
