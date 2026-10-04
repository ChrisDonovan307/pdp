from __future__ import annotations

import os
import subprocess
import warnings
from pathlib import Path

from .pdp_config import TaskConfig
from .utils import find_project_root


def latest_mtime_in_dir(dir: Path):
    mtimes = []
    for root, _, files in os.walk(dir):
        for file in files:
            path = os.path.join(root, file)
            if os.path.exists(path):  # follows file symlinks; skips broken ones
                mtimes.append(os.path.getmtime(path))

    return max(mtimes, default=None)


class Task:
    def __init__(self, task_name: str, task_directory: str | Path):
        self.task_name = task_name
        self.task_directory = Path(task_directory).resolve()
        self.task_config = TaskConfig(task_name, self.task_directory / "task.yml")
        self.input_folder = self.task_directory / "input"
        self.output_folder = self.task_directory / "output"
        self.src_folder = self.task_directory / "src"
        self.hand_folder = None

    def scaffold(self):
        self.task_directory.mkdir(parents=True, exist_ok=True)

        self.task_config.initialize()

        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.src_folder.mkdir(parents=True, exist_ok=True)

    def create_symlinks(self, task_ids: set[str]) -> None:
        """Symlink into task input/ the outputs of dependent tasks.

        First, removes any existing symlinks that PDP created, so links
        to folders that no longer exist are pruned. Only removes what
        is demonstrably its own - symlink, named after task, target inside project.
        Then declares new symlinks.

        Args:
            task_ids: _description_
        """        
        root = find_project_root(config_name="pdp.yml", start=self.task_directory)
        for entry in self.input_folder.iterdir():
            if (
                # confirm PDP owns it
                entry.name in task_ids
                and entry.is_symlink()
                and entry.resolve().is_relative_to(root)
            ):
                entry.unlink()

        for dep in self.depends_on_tasks:
            try:
                (self.input_folder / dep).symlink_to(Path("..", "..", dep, "output"))
            except OSError as e:  # catch Windows - can't symlink without privilege
                warnings.warn(f"{self.task_id}: could not link input/{dep}: {e}")

    def run(self):
        if not self.entrypoint:
            return 0

        result = subprocess.run(
            self.entrypoint, check=False, cwd=self.task_directory, shell=True
        )
        return result.returncode

    def validation_errors(self) -> list[str]:
        errors: list[str] = self.task_config.validation_errors()

        for folder in (self.input_folder, self.output_folder, self.src_folder):
            if not folder.is_dir():
                errors.append(f"{folder.name} is missing")

        if self.hand_folder is not None and not self.hand_folder.is_dir():
            errors.append("hand/ folder is missing")

        for dep in self.depends_on_tasks:
            link = self.input_folder / dep
            if not link.is_symlink() and link.exists():
                errors.append(
                    f"input/{dep} is a real file or directory, not a dependency link"
                )

        return errors

    def validate(self) -> bool:
        return not self.validation_errors()

    @property
    def entrypoint(self) -> str:
        return self.task_config.entrypoint

    @property
    def depends_on_tasks(self) -> list[str]:
        return self.task_config.depends_on_tasks

    def __repr__(self):
        return f"Task({self.task_name}, {self.task_directory})"

    def __eq__(self, other):
        return repr(self) == repr(other)

    @property
    def task_id(self) -> str:
        """Without subtasks, task_id is just the directory name.
        Revisit when subtasks come back."""
        return self.task_directory.name

    @property
    def is_stale(self) -> bool:
        """Task is stale if it has a stale task dependency, if outputs are missing,
        or if outputs are older than the rest of the task"""

        # stale dependency
        root = find_project_root("pdp.yml", start=self.task_directory)
        if any(Task(dep, root / dep).is_stale for dep in self.depends_on_tasks):
            return True

        # missing outputs (no folder, empty, or no readable files)
        task_mtime = latest_mtime_in_dir(self.output_folder)
        if task_mtime is None:
            return True

        # outputs older than input, src, hand, or a dependency's output.
        # missing/empty folders skipped
        for folder in (
            self.src_folder,
            self.input_folder,
            self.task_directory / "hand",
            *(root / dep / "output" for dep in self.depends_on_tasks),
        ):
            mtime = latest_mtime_in_dir(folder)
            if mtime is not None and mtime > task_mtime:
                return True

        return False
