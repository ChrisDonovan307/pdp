from pathlib import Path

import pytest
from expects import *
from ruamel.yaml import YAML

from pdp.pdp_config import PDPConfig, TaskConfig
from pdp.utils import TASK_NAME_RULE


@pytest.fixture
def config(fs):
    config = PDPConfig("test", Path("pdp.yml"))
    yield config


def read_config_file(filename):
    return dict(YAML().load(Path(filename)))


class TestInit:
    def test_config_initialization(self, config, fs):
        expect(config.read_config_file()).to(equal({}))

        config.path_to_config.touch()
        expect(config.read_config_file()).to(equal({}))

        expect(config.initialized).to(be_false)

    def test_config_initialize_creates_file(self, config, fs):
        config.initialize()

        config_dict = read_config_file("pdp.yml")
        expect(config_dict["name"]).to(equal("test"))
        expect(config_dict["tasks"]).to(equal([]))

    def test_task_config_initializes_with_entrypoint(self, fs):
        # TODO: Bring back subtasks
        config = TaskConfig("task1", "task.yml")
        config.initialize()

        config_dict = read_config_file("task.yml")
        expect(config_dict["entrypoint"]).to(equal(""))
        expect(config_dict["depends_on"]).to(equal([]))


def test_config_add_task(config, fs):
    config.initialize()

    config.add_task("hello")
    expect(config.config["tasks"]).to(equal(["hello"]))

    config.add_task("world")
    expect(config.config["tasks"]).to(equal(["hello", "world"]))

    config.add_task("hello")
    expect(config.config["tasks"]).to(equal(["hello", "world"]))

    config_dict = read_config_file("pdp.yml")
    expect(config_dict["tasks"]).to(equal(["hello", "world"]))


class TestValidate:
    def test_config_validate(self, config, fs):
        config.initialize()

        expect(config.validate()).to(be_true)

        config.update_config({"tasks": "hello"})
        expect(config.validate()).to(be_false)

        config.update_config({"no_tasks": 123})
        expect(config.validate()).to(be_false)

    def test_config_validate_flags_bad_task_name(self, fs):
        Path("pdp.yml").write_text("name: test\ntasks:\n  - import\n  - clean.data\n")

        errors = PDPConfig("test", "pdp.yml").validation_errors()

        expect(errors).to(
            equal([f"invalid task name 'clean.data': must be {TASK_NAME_RULE}"])
        )

    def test_task_config_validation_requires_default_config_keys(self, fs):
        config = TaskConfig("task1", "task.yml")
        config.initialize()

        expect(config.validate()).to(be_true)

        # only subtasks, without entrypoint
        config.update_config({"subtasks": []})
        expect(config.validate()).to(be_false)

        # only entrypoint, without subtasks
        config.update_config({"entrypoint": "make"})
        expect(config.validate()).to(be_false)


def test_task_config_repr_prints_name_and_path(fs):
    config = TaskConfig("task1", "task.yml")
    expect(str(config)).to(equal("TaskConfig(task1, /task.yml)"))


def test_pdp_config_repr_prints_config_path(config, fs):
    expect(str(config)).to(equal("PDPConfig(test, /pdp.yml)"))
