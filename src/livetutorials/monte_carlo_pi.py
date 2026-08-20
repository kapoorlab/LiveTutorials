"""Monte Carlo algorithm for computing the value of pi."""

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class MonteCarloPiConfig:
    """Configuration for the Monte Carlo Pi algorithm."""

    num_samples: int = 1000000
    """Number of random samples to generate."""

    seed: Optional[int] = None
    """Random seed for reproducibility. If None, uses system time."""

    verbose: bool = False
    """Whether to print progress information."""


class MonteCarloPi:
    """Monte Carlo algorithm for computing the value of pi.

    This class implements the Monte Carlo method to estimate pi by
    generating random points in a unit square and counting how many
    fall inside the unit circle.

    The algorithm works by:
    1. Generating random points (x, y) where 0 <= x, y <= 1
    2. Counting points that satisfy x^2 + y^2 <= 1 (inside the circle)
    3. Estimating pi as 4 * (points_in_circle / total_points)

    Example:
        ```python
        config = MonteCarloPiConfig(num_samples=1000000, seed=42)
        mc = MonteCarloPi(config)
        pi_estimate = mc.compute()
        print(f"Estimated pi: {pi_estimate}")
        ```
    """

    def __init__(self, config: Optional[MonteCarloPiConfig] = None):
        """Initialize the Monte Carlo Pi estimator.

        Args:
            config: Configuration for the algorithm. If None, uses default
                   values from MonteCarloPiConfig.
        """
        self.config = config or MonteCarloPiConfig()

        if self.config.seed is not None:
            random.seed(self.config.seed)

        self.points_in_circle = 0
        self.total_points = 0

    def _is_inside_circle(self, x: float, y: float) -> bool:
        """Check if a point is inside the unit circle.

        Args:
            x: x-coordinate of the point.
            y: y-coordinate of the point.

        Returns:
            True if the point is inside the unit circle, False otherwise.
        """
        return x * x + y * y <= 1.0

    def _sample_point(self) -> tuple:
        """Generate a random point in the unit square.

        Returns:
            Tuple of (x, y) coordinates.
        """
        x = random.random()
        y = random.random()
        return x, y

    def compute(self) -> float:
        """Compute pi using the Monte Carlo method.

        Returns:
            Estimated value of pi.
        """
        if self.config.verbose:
            print(f"Computing pi with {self.config.num_samples} samples")

        for i in range(self.config.num_samples):
            x, y = self._sample_point()
            if self._is_inside_circle(x, y):
                self.points_in_circle += 1
            self.total_points += 1

            if self.config.verbose and (i + 1) % 100000 == 0:
                current_estimate = 4.0 * self.points_in_circle / self.total_points
                print(f"After {i + 1} samples: pi = {current_estimate:.10f}")

        pi_estimate = 4.0 * self.points_in_circle / self.total_points

        if self.config.verbose:
            print(f"Final estimate: pi = {pi_estimate:.10f}")
            print(f"Error: {abs(pi_estimate - 3.141592653589793):.10f}")

        return pi_estimate

    def reset(self) -> None:
        """Reset the estimator for a new computation."""
        self.points_in_circle = 0
        self.total_points = 0
        if self.config.seed is not None:
            random.seed(self.config.seed)