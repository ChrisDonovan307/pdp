from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pdp.pdp import PDP
from pdp.pdp_config import PDPConfig
from pdp.task import Task


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

    with open("/hello/task.yml", "w") as f:
        f.write(
            "name: hello\nentrypoint: make\nsubtasks: []\n"
            "depends_on_tasks: []\ndepends_on_files: []"
        )

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
    Path("/pdp.yml").write_text("tasks:\n  - raw\n  - clean\n")

    raw = Task("raw", Path("/raw"))
    raw.scaffold()

    clean = Task("clean", Path("/clean"))
    clean.scaffold()
    clean.task_config.update_config_key("depends_on_tasks", ["raw"])

    return raw, clean
