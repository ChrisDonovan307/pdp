from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from rich.tree import Tree

from .pdp_config import PDPConfig
from .pdp_errors import InvalidConfigError
from .task import Task
from .utils import TASK_NAME_RULE, find_project_root, is_valid_task_name


class PDP:
    def __init__(
        self, project_name: str | None = None, config: PDPConfig | None = None
    ) -> None:
        self.project_name: str | None = project_name

        if config:
            self.config = config
        else:
            self.config = PDPConfig(project_name, self.project_root / "pdp.yml")
        self.tasks: list[Task] = []

    def initialize(self) -> None:
        if self.initialized and not self.validate():
            raise InvalidConfigError("Invalid config file")

        self.config.initialize()
        self.project_name = self.config.name

        for task in self.config.tasks:
            self.create_task(task)

    def validation_errors(self) -> list[str]:
        """Reasons the project fails validation

        Checks pdp.yml, input dir, output dir, adn task.yml for each task.
        Checks that Depends_on references real task, and no dependency cycles.

        Returns:
            A list of strings of error messages. Empty if valid.
        """

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
            for dep in task.depends_on:
                if dep not in flattened:
                    errors.append(
                        f"{task_id}/task.yml: depends_on references unknown task '{dep}'"
                    )
                elif not flattened[dep].entrypoint:
                    errors.append(
                        f"{task_id}/task.yml: depends_on references '{dep}', "
                        "which is a group task with no output"
                    )

        graph = {task_id: task.depends_on for task_id, task in flattened.items()}
        try:
            TopologicalSorter(graph).prepare()
        except CycleError:
            errors.append("depends_on contains a cycle.")

        return errors

    def validate(self) -> bool:
        return not self.validation_errors()

    def create_task(self, task_name: str) -> Task:
        if not is_valid_task_name(task_name):
            raise ValueError(f"invalid task name '{task_name}': must be {TASK_NAME_RULE}")

        self.config.add_task(task_name)

        task_directory = self.project_root / task_name

        task = Task(task_name, task_directory)
        task.scaffold()

        self.tasks.append(task)

        return task

    def create_task_from_current_location(self, task_name: str) -> Task | None:
        if self.current_path == Path("."):
            return self.create_task(task_name)

        raise ValueError("tasks can only be created at the project root")

    def scaffold(self) -> None:
        """Set up folders for each task, then set symlinks for outputs"""
        for task in self.tasks:
            task.scaffold()
        task_ids: set[str] = set(self.flatten_tasks())
        for task in self.tasks:
            task.create_symlinks(task_ids)

    def _closure(self, flattened: dict[str, Task], task_id: str) -> set[str]:
        """Return task_id plus every task's task_id that it depends on.

        if project is import -> clean -> analyze, closure is {import, clean, analyze}

        Args:
            flattened: Every task in project
            task_id: Current task to run
            
        Returns:
            A set of every task_id in scope
        """
        touched = set()
        stack = [task_id]
        while stack:
            current = stack.pop()
            if current not in touched:
                touched.add(current)
                stack.extend(flattened[current].depends_on)
        return touched

    def _run_many(self, flattened: dict[str, Task], task_ids) -> int:
        graph = {tid: task.depends_on for tid, task in flattened.items()}
        order = [
            tid
            for tid in TopologicalSorter(graph).static_order()
            if tid in task_ids and flattened[tid].entrypoint
        ]

        all_task_ids = set(flattened)
        returncodes = []
        for tid in order:
            task = flattened[tid]
            if task.is_stale:
                task.create_symlinks(all_task_ids)
                returncodes.append(task.run())

        return 0 if all(rc == 0 for rc in returncodes) else 1

    def _validate_or_raise(self) -> None:
        if not self.validate():
            raise InvalidConfigError("\n".join(self.validation_errors()))

    def run_all(self) -> int:
        flattened = self.flatten_tasks()
        self._validate_or_raise()
        return self._run_many(flattened, flattened.keys())

    def run_task(self, task_id: str) -> int:
        flattened: dict[str, Task] = self.flatten_tasks()
        self._validate_or_raise()
        if task_id not in flattened:
            raise ValueError(f"Task {task_id} not found")
        scope = self._closure(flattened, task_id)
        return self._run_many(flattened, scope)

    def _find_task_by_id(self, task_id: str) -> Task | None:
        return self.flatten_tasks().get(task_id)

    def task_tree(self) -> Tree:
        """Flat numbered list of tasks under the project name."""
        tree = Tree(f"1. {self.project_name}")
        for num, task in enumerate(self.tasks, start=2):
            tree.add(f"{num}. {task.task_id}")
        return tree

    def flatten_tasks(self) -> dict[str, Task]:
        """Create dict of tasks. This is where subtask flattening would happen,
        temporarily deferred.

        Returns:
            dict[task_id, Task]: Tasks
        """
        flattened = {t.task_id: t for t in self.tasks}

        return flattened

    @property
    def current_path(self) -> Path:
        return Path.cwd().relative_to(self.project_root)

    @property
    def current_task(self) -> Task | None:
        return self._find_task_by_id(str(self.current_path))

    @property
    def project_root(self) -> Path:
        return find_project_root("pdp.yml")

    @property
    def initialized(self) -> bool:
        return self.config.initialized
