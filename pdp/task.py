from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.tree import Tree

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
        self.subtasks = []

    def scaffold(self):
        self.task_directory.mkdir(parents=True, exist_ok=True)

        self.task_config.initialize()

        for subtask in self.task_config.tasks:
            self.create_subtask(subtask)

        if len(self.subtasks) == 0:
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
        errors = self.task_config.validation_errors()

        if not self.subtasks:
            if not self.input_folder.is_dir():
                errors.append("input/ folder is missing")
            if not self.output_folder.is_dir():
                errors.append("output/ folder is missing")

            # Validate paths for files dependencies
            for file in self.task_config.config.get("depends_on_files", []):
                if Path(file).is_absolute():
                    errors.append(
                        f"depends_on_files entry '{file}' must be a relative path"
                    )
                    continue

                resolved = (self.task_directory / file).resolve()
                if not resolved.is_relative_to(self.task_directory):
                    errors.append(
                        f"depends_on_files entry '{file}' is outside the task directory"
                    )

        for subtask in self.subtasks:
            errors += [
                f"{subtask.task_name}: {error}" for error in subtask.validation_errors()
            ]

        return errors

    def validate(self) -> bool:
        return not self.validation_errors()

    def create_subtask(self, subtask_name: str) -> Task | None:
        self.task_config.add_task(subtask_name)
        subtask_directory = self.task_directory / subtask_name

        subtask = Task(subtask_name, subtask_directory)
        subtask.scaffold()

        if (
            is_empty(self.input_folder)
            and is_empty(self.output_folder)
            and is_empty(self.src_folder)
        ):
            try:
                self.input_folder.rmdir()
            except FileNotFoundError:
                pass

            try:
                self.output_folder.rmdir()
            except FileNotFoundError:
                pass

            try:
                self.src_folder.rmdir()
            except FileNotFoundError:
                pass

        self.subtasks.append(subtask)

        return subtask

    def construct_subtree(self, counter, parent_tree) -> None:
        """Create a tree structure of the tasks and subtasks.
        Subtasks are recursively nested within tasks."""
        num = next(counter)
        node = parent_tree.add(f"{num}. {self.task_name}")
        for task in self.subtasks:
            task.construct_subtree(counter, node)

    def subtree_traversal(self, counter, callback) -> None:
        """Iterate over the tasks and subtasks in a tree structure.
        Subtasks are recursively nested within tasks."""
        num = next(counter)
        callback(num, self)
        for task in self.subtasks:
            task.subtree_traversal(counter, callback)

    @property
    def entrypoint(self) -> str:
        return self.task_config.entrypoint

    @property
    def depends_on_tasks(self) -> list[str]:
        return self.task_config.depends_on_tasks

    @property
    def depends_on_files(self) -> list[str]:
        return self.task_config.depends_on_files

    def __repr__(self):
        return f"Task({self.task_name}, {self.task_directory})"

    def __eq__(self, other):
        return repr(self) == repr(other)

    @property
    def task_id(self) -> str:
        root = find_project_root("pdp.yml", start=self.task_directory)
        relative = self.task_directory.relative_to(root)
        return "/".join(relative.parts)

    @property
    def is_stale(self) -> bool:
        """Stale if (1) no output folder, (2) no outputs for task,
        or (3) any dependency (depends_on_files, depends_on_tasks, or
        this task's src) is newer than this task's output."""

        # 1 + 2
        if is_empty(self.output_folder):
            return True

        task_mtime = latest_mtime_in_dir(self.output_folder)

        root = find_project_root("pdp.yml", start=self.task_directory)
        dependency_paths = [root / dep / "output" for dep in self.depends_on_tasks]
        dependency_paths += [self.task_directory / f for f in self.depends_on_files]
        dependency_paths.append(self.src_folder)

        # 3
        for path in dependency_paths:
            if not path.exists():
                return True

            dep_mtime = latest_mtime(path)
            if dep_mtime is not None and dep_mtime > task_mtime:
                return True

        return False
