import subprocess
import os
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


class Task:
    def __init__(self, task_name: str, task_directory: str | Path):
        self.task_name = task_name
        self.task_directory = Path(task_directory).resolve()
        self.task_config = TaskConfig(task_name, task_directory / "task.yml")
        self.input_folder = task_directory / "input"
        self.output_folder = task_directory / "output"
        self.src_folder = task_directory / "src"
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
        returncodes = []
        for subtask in self.subtasks:
            returncodes.append(subtask.run())

        if self.entrypoint:
            result = subprocess.run(self.entrypoint, cwd=self.task_directory)
            returncodes.append(result.returncode)

        all_success = all([rc == 0 for rc in returncodes])

        if all_success:
            return 0

        return 1

    def create_subtask(self, subtask_name: str) -> None:
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
    def depends_on(self) -> list[str]:
        return self.task_config.depends_on

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
        """Stale if (1) no output folder (2) no outputs for this task or 
        (3) dependency output is newer than task output"""

        if not os.path.isdir(self.output_folder):
            return True
        
        if os.listdir(self.output_folder) == []:
            return True

        task_mtime = latest_mtime_in_dir(self.output_folder)

        root = find_project_root("pdp.yml", start=self.task_directory)
        dep_mtimes = []
        for dep in self.depends_on:
            dep_mtimes.append(latest_mtime_in_dir(root / dep / "output"))
        
        return task_mtime < max(dep_mtimes)
