from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .pdp_config import TaskConfig
from .utils import find_project_root


def is_empty(directory):
    return not directory.exists() or not any(directory.iterdir())


def latest_mtime_in_dir(dir: Path):
    mtimes = []
    for root, _, files in os.walk(dir):
        for file in files:
            mtimes.append(os.path.getmtime(os.path.join(root, file)))

    return max(mtimes, default=None)


def latest_mtime(path: Path):
    """Newest mtime under path: the file's own mtime if it's a file,
    or the newest mtime of any file inside it if it's a directory."""
    if path.is_file():
        return path.stat().st_mtime

    return latest_mtime_in_dir(path)


class Task:
    def __init__(self, task_name: str, task_directory: str | Path):
        self.task_name = task_name
        self.task_directory = Path(task_directory).resolve()
        self.task_config = TaskConfig(task_name, self.task_directory / "task.yml")
        self.input_folder = self.task_directory / "input"
        self.output_folder = self.task_directory / "output"
        self.src_folder = self.task_directory / "src"

    def scaffold(self):
        self.task_directory.mkdir(parents=True, exist_ok=True)

        self.task_config.initialize()

        self.input_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.src_folder.mkdir(parents=True, exist_ok=True)

    def run(self):
        if not self.entrypoint:
            return 0

        result = subprocess.run(
            self.entrypoint, check=False, cwd=self.task_directory, shell=True
        )
        return result.returncode

    def validation_errors(self) -> list[str]:
        errors: list[str] = self.task_config.validation_errors()

        if not self.input_folder.is_dir():
            errors.append("input/ folder is missing")
        if not self.output_folder.is_dir():
            errors.append("output/ folder is missing")
        if not self.src_folder.is_dir():
            errors.append("src/ folder is missing")

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
        """Stale if (1) no output folder, (2) no outputs for task,
        or (3) any task dependency is_stale"""

        if is_empty(self.output_folder):
            return True

        task_mtime = latest_mtime_in_dir(self.output_folder)

        root = find_project_root("pdp.yml", start=self.task_directory)
        dependency_paths = [root / dep / "output" for dep in self.depends_on_tasks]
        dependency_paths.append(self.src_folder)

        for path in dependency_paths:
            if not path.exists():
                return True

            dep_mtime = latest_mtime(path)
            if dep_mtime is not None and dep_mtime > task_mtime:
                return True

        return False
