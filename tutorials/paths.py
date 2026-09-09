"""Data classes for managing project paths."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DataPaths:
    """Project directory structure."""

    base_dir: str
    project_name: str
    working_dir: Path = field(init=False)

    def __post_init__(self):
        """Compute derived paths after dataclass initialization."""
        base = Path(self.base_dir).expanduser().resolve()
        self.working_dir = base / self.project_name


# Example usage:
if __name__ == "__main__":
    # Create with different values
    paths1 = DataPaths(base_dir="/data", project_name="my_project")
    print(paths1.working_dir)  # /data/my_project

    paths2 = DataPaths(base_dir="/tmp", project_name="test_run")
    print(paths2.working_dir)  # /tmp/test_run