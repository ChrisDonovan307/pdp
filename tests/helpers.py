import os
from pathlib import Path

from ruamel.yaml import YAML

from pdp.task import Task


def write_task_yml(task_dir, *, entrypoint="", depends_on=(), **overrides):
    """Write a valid flat task.yml into task_dir. Compatible with tmp_path"""
    task_dir = Path(task_dir)
    config = {
        "name": task_dir.name,
        "entrypoint": entrypoint,
        "depends_on": list(depends_on),
        **overrides,
    }
    YAML().dump(config, task_dir / "task.yml")


def backdate_task_yml(*tasks: Task) -> None:
    """Make task.yml older than mtimes a test sets"""
    for task in tasks:
        os.utime(task.task_directory / "task.yml", (1, 1))


def make_real_task(root: Path, name: str, deps=()) -> Task:
    (root / name).mkdir()
    write_task_yml(root / name, depends_on=deps)
    task = Task(name, root / name)
    task.scaffold()
    backdate_task_yml(task)

    return task
