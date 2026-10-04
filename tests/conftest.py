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
def import_and_clean(fs):
    """create two tasks: 'import' and 'clean'"""
    Path("/pdp.yml").write_text("tasks:\n  - import\n  - clean\n")

    import_task = Task("import", Path("/import"))
    import_task.scaffold()

    Path("/clean").mkdir()
    write_task_yml("/clean", depends_on_tasks=["import"])
    clean = Task("clean", Path("/clean"))
    clean.scaffold()

    return import_task, clean


def make_real_task(root: Path, name: str, deps=()) -> Task:
    (root / name).mkdir()
    write_task_yml(root / name, depends_on_tasks=deps)
    task = Task(name, root / name)
    task.scaffold()

    return task


@pytest.fixture
def real_task(tmp_path):
    """Scaffolded task on the real filesystem"""
    (tmp_path / "pdp.yml").write_text("name: test\ntasks:\n  - hello\n")
    task = Task("hello", tmp_path / "hello")
    task.scaffold()

    return task


@pytest.fixture
def real_chain(tmp_path):
    """import -> clean -> report on real filesystem"""
    (tmp_path / "pdp.yml").write_text(
        "name: test\ntasks:\n  - importw\n  - clean\n  - report\n"
    )
    import_task = make_real_task(tmp_path, "import")
    clean = make_real_task(tmp_path, "clean", ["import"])
    report = make_real_task(tmp_path, "report", ["clean"])

    return import_task, clean, report


@pytest.fixture
def two_deps_and_clean(pdp, fs):
    import1 = pdp.create_task("import1")
    import2 = pdp.create_task("import2")
    clean = pdp.create_task("clean")
    pdp.scaffold()

    clean.task_config.update_config_key("depends_on_tasks", ["import2", "import2"])

    return import1, import2, clean


@pytest.fixture
def real_pdp(tmp_path, monkeypatch):
    """Initialized project on the real filesystem, cwd at its root"""
    monkeypatch.chdir(tmp_path)
    pdp = PDP("test")
    pdp.initialize()

    return pdp


@pytest.fixture
def import_and_clean_project(real_pdp):
    """Real project where clean depends on import"""
    real_pdp.create_task("import")
    real_pdp.create_task("clean")
    write_task_yml("clean", depends_on_tasks=["import"])

    return real_pdp
