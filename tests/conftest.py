from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ruamel.yaml import YAML

from pdp.pdp import PDP
from pdp.pdp_config import PDPConfig
from pdp.task import Task


def write_task_yml(task_dir, *, entrypoint="", depends_on_tasks=(), **overrides):
    """Write a valid flat task.yml into task_dir"""
    task_dir = Path(task_dir)
    config = {
        "name": task_dir.name,
        "entrypoint": entrypoint,
        "depends_on_tasks": list(depends_on_tasks),
        **overrides,
    }
    YAML().dump(config, task_dir / "task.yml")


@pytest.fixture
def config(fs):
    config = PDPConfig("test", Path("pdp.yml"))

    yield config


@pytest.fixture
def hello_world_tasks(pdp):
    pdp.create_task("hello")
    pdp.create_task("world")
    yield pdp


@pytest.fixture
def make_task(pdp):
    task = pdp.create_task("hello")
    task.run = MagicMock()
    write_task_yml("/hello", entrypoint="make")

    yield task


@pytest.fixture
def empty_pdp_yaml(fs):
    path_to_config = Path("pdp.yml")
    path_to_config.touch()

    yield fs


@pytest.fixture
def yaml_without_tasks(fs):
    with open("pdp.yml", "w") as f:
        f.write("hello:\n  - hello\n  - world\n")

    yield fs


@pytest.fixture
def pdp(fs):
    pdp = PDP("test")
    pdp.initialize()

    yield pdp


@pytest.fixture
def task(fs):
    task_name = "hello"
    task = Task(task_name, Path(task_name))

    return task


@pytest.fixture
def raw_and_clean(fs):
    """create two tasks: 'raw' and 'clean'"""
    Path("/pdp.yml").write_text("tasks:\n  - raw\n  - clean\n")

    raw = Task("raw", Path("/raw"))
    raw.scaffold()

    Path("/clean").mkdir()
    write_task_yml("/clean", depends_on_tasks=["raw"])
    clean = Task("clean", Path("/clean"))
    clean.scaffold()

    return raw, clean
