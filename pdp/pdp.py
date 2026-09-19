from graphlib import CycleError, TopologicalSorter
from itertools import count
from pathlib import Path

from rich.tree import Tree

from .pdp_config import PDPConfig
from .pdp_errors import InvalidConfigError
from .task import Task
from .utils import find_project_root


class PDP:
    def __init__(
        self, project_name: str | None = None, config: PDPConfig | None = None
    ) -> None:
        self.project_name = project_name

        if config:
            self.config = config
        else:
            self.config = PDPConfig(project_name, self.project_root / "pdp.yml")
        self.tasks = []

    def initialize(self) -> None:
        if self.initialized and not self.validate():
            raise InvalidConfigError("Invalid config file")

        self.config.initialize()
        self.project_name = self.config.name

        for task in self.config.tasks:
            self.create_task(task)

    def validation_errors(self) -> list[str]:
        """Reasons the project fails validation; empty if it's valid.
        Checks pdp.yml, input dir, output dir, adn task.yml for each task.
        Checks that Depends_on_tasks references real task, and no dependency cycles."""

        if not self.initialized:
            return ["Project not initialized."]

        errors = [f"pdp.yml: {error}" for error in self.config.validation_errors()]

        # Validate top level tasks. Each recurses through its own subtasks
        for task in self.tasks:
            errors += [
                f"{task.task_id}/task.yml: {error}"
                for error in task.validation_errors()
            ]

        # Flatten tasks to check circular dependencies
        flattened = self.flatten_tasks()

        for task_id, task in flattened.items():
            for dep in task.depends_on_tasks:
                if dep not in flattened:
                    errors.append(
                        f"{task_id}/task.yml: depends_on_tasks references unknown task '{dep}'"
                    )

        graph = {task_id: task.depends_on_tasks for task_id, task in flattened.items()}
        try:
            TopologicalSorter(graph).prepare()
        except CycleError:
            errors.append("depends_on_tasks contains a cycle.")

        return errors

    def validate(self) -> bool:
        return not self.validation_errors()

    def create_task(self, task_name: str) -> Task:
        self.config.add_task(task_name)

        task_directory = self.project_root / task_name

        task = Task(task_name, task_directory)
        task.scaffold()

        self.tasks.append(task)

        return task

    def create_task_from_current_location(self, task_name: str) -> None:
        if self.current_path == Path("."):
            return self.create_task(task_name)

        current_task = self.current_task

        if current_task is not None:
            return current_task.create_subtask(task_name)

        raise ValueError(
            "Tried to create task from location that is neither project root nor a task."
        )

    def scaffold(self) -> None:
        for task in self.tasks:
            task.scaffold()

    def run_task(self, task_name: str) -> int:
        task = self._find_task_by_name(task_name)
        if task is None:
            raise ValueError(f"Task {task_name} not found")

        return task.run()

    def run_all(self) -> int:
        for task in self.tasks:
            self.run_task(task.task_name)

        return 0

    def _find_task_by_name(self, task_name: str) -> Task | None:
        return next((t for t in self.tasks if t.task_name == task_name), None)

    def task_tree(self) -> Tree:
        """Create a tree structure of the tasks and subtasks.
        Subtasks are recursively nested within tasks."""
        tree = Tree(f"1. {self.project_name}")
        counter = count(2)
        for task in self.tasks:
            task.construct_subtree(counter, tree)

        return tree

    def flatten_tasks(self):
        """Create flat dict of tasks

        Returns:
            dict[task_id, Task]: Tasks
        """
        flattened = {}
        counter = count(1)

        def collect(num, task):
            flattened[task.task_id] = task

        for task in self.tasks:
            task.subtree_traversal(counter, collect)

        return flattened

    @property
    def current_path(self) -> Path:
        return Path.cwd().relative_to(self.project_root)

    @property
    def current_task(self) -> Task | None:
        return self._find_task_by_name(str(self.current_path))

    @property
    def project_root(self) -> Path:
        return find_project_root("pdp.yml")

    @property
    def initialized(self) -> bool:
        return self.config.initialized
