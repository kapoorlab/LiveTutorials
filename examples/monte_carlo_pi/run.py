"""Run the Monte Carlo Pi algorithm with Hydra configuration."""

import hydra
from omegaconf import DictConfig
from livetutorials.monte_carlo_pi import MonteCarloPi, MonteCarloPiConfig


@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    """Run the Monte Carlo Pi algorithm.

    Args:
        cfg: Configuration from Hydra.
    """
    # Convert DictConfig to MonteCarloPiConfig
    config = MonteCarloPiConfig(
        num_samples=cfg.num_samples,
        seed=cfg.seed,
        verbose=cfg.verbose,
    )

    # Create and run the estimator
    estimator = MonteCarloPi(config)
    pi_estimate = estimator.compute()

    print(f"\n{'=' * 50}")
    print(f"Monte Carlo Pi Estimate")
    print(f"{'=' * 50}")
    print(f"Samples: {config.num_samples}")
    print(f"Seed: {config.seed}")
    print(f"Estimated pi: {pi_estimate:.15f}")
    print(f"Actual pi:  3.141592653589793")
    print(f"Error: {abs(pi_estimate - 3.141592653589793):.15f}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()