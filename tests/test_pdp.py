import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from expects import *
from ruamel.yaml import YAML

from pdp.pdp import PDP, PDPConfig
from pdp.pdp_errors import InvalidConfigError
from pdp.task import Task
from pdp.utils import find_project_root


def read_config_file(filename):
    return dict(YAML().load(Path(filename)))


class TestUtilities:
    def test_find_project_root(self, fs):
        pdp = PDP("test")
        pdp.initialize()

        root = find_project_root("pdp.yml", start=pdp.project_root)
        assert root == pdp.project_root


class TestInitialize:
    def test_pdp_uninitialized_when_config_file_does_not_exist(self, fs):
        pdp = PDP("test")

        expect(pdp.initialized).to(be_false)

    def test_pdp_uninitialized_when_config_file_empty(self, empty_pdp_yaml, fs):
        path = Path("pdp.yml")
        path.touch()

        pdp = PDP("test")
        expect(pdp.initialized).to(be_false)

        pdp.initialize()

        expect(pdp.initialized).to(be_true)

    def test_pdp_inits_empty_task_list(self, fs, pdp):
        config_dict = read_config_file("pdp.yml")
        expect(config_dict["tasks"]).to(equal([]))

    def test_pdp_init_is_idempotent_on_files(self, hello_world_tasks, pdp):
        expect(pdp.config.config).to(equal({
            "name": "test",
            "tasks": ["hello", "world"]
        }))

    def test_pdp_initialize_raises_error_if_invalid_config(self, yaml_without_tasks):
        config = PDPConfig("test", "pdp.yml")
        with pytest.raises(InvalidConfigError):
            pdp = PDP(config=config)
            pdp.initialize()


class TestValidate:
    def test_pdp_validate_fails_if_config_has_no_tasks(self, empty_pdp_yaml):
        pdp = PDP()
        expect(pdp.validate()).to(be_false)

    def test_pdp_validate_passes_with_no_depends_on_tasks(self, pdp):
        pdp.create_task("hello")
        expect(pdp.validate()).to(be_true)

    def test_pdp_validate_raises_when_depends_on_bad_task(self, pdp):
        task = pdp.create_task("hello")
        task.task_config.update_config_key("depends_on_tasks", ["bad_task"])
        expect(pdp.validate()).to(be_false)

    def test_pdp_validate_raises_on_cycle(self, pdp):
        task1 = pdp.create_task("hello")
        task1.task_config.update_config_key("depends_on_tasks", ["world"])

        task2 = pdp.create_task("world")
        task2.task_config.update_config_key("depends_on_tasks", ["hello"])

        expect(pdp.validate()).to(be_false)


class TestScaffoldTask:
    def test_pdp_create_task(self, pdp):
        pdp.create_task("hello")

        expect(pdp.config.tasks).to(equal(["hello"]))

        hello_path = Path("hello")
        hello_path_input = hello_path / "input"
        hello_path_output = hello_path / "output"
        hello_path_src = hello_path / "src"
        hello_path_task_config = hello_path / "task.yml"

        expect(hello_path_input.exists()).to(be_true)
        expect(hello_path_output.exists()).to(be_true)
        expect(hello_path_src.exists()).to(be_true)
        expect(hello_path_task_config.exists()).to(be_true)

    def test_pdp_create_task_idempotent(self, pdp):
        pdp.create_task("hello")
        pdp.create_task("hello")
        expect(pdp.config.tasks).to(equal(["hello"]))

    def test_pdp_scaffold(self, hello_world_tasks, pdp):
        pdp.scaffold()

        hello_path = Path("hello")
        hello_path_input = hello_path / "input"
        hello_path_output = hello_path / "output"

        expect(hello_path_input.exists()).to(be_true)
        expect(hello_path_output.exists()).to(be_true)

        world_path = Path("world")
        world_path_input = world_path / "input"
        world_path_output = world_path / "output"

        expect(world_path_input.exists()).to(be_true)
        expect(world_path_output.exists()).to(be_true)

    def test_pdp_creates_task_from_root(self, pdp):
        pdp.create_task_from_current_location("hello")
        expect(pdp.config.tasks).to(equal(["hello"]))

        hello_path = Path("hello")
        hello_path_input = hello_path / "input"
        hello_path_output = hello_path / "output"

        expect(hello_path_input.exists()).to(be_true)
        expect(hello_path_output.exists()).to(be_true)

    def test_pdp_creates_task_from_current_location(self, hello_world_tasks, pdp):
        pdp.scaffold()

        os.chdir("hello")

        pdp.create_task_from_current_location("foo")

        expect(pdp.config.tasks).to(equal(["hello", "world"]))

        yaml = YAML()
        task_yaml = dict(yaml.load(Path("/hello/task.yml")))

        expect(task_yaml["name"]).to(equal("hello"))
        expect(task_yaml["entrypoint"]).to(equal(""))
        expect(task_yaml["subtasks"]).to(equal(["foo"]))

    def test_pdp_task_tree_generates_tree(self, pdp):
        pdp.scaffold()

        pdp.create_task("hello")
        pdp.create_task("world")

        os.chdir("/hello")
        pdp.create_task_from_current_location("foo")

        os.chdir("/world")
        pdp.create_task_from_current_location("bar")

        tree = pdp.task_tree()

        expect(tree.label).to(equal("1. test"))
        expect(tree.children[0].label).to(equal("2. hello"))
        expect(tree.children[0].children[0].label).to(equal("3. foo"))
        expect(tree.children[1].label).to(equal("4. world"))
        expect(tree.children[1].children[0].label).to(equal("5. bar"))

    def test_pdp_create_task_from_current_location_raises_if_not_in_task(self, fs):
        pdp = PDP()
        pdp.initialize()

        Path("/not_a_task").mkdir(parents=True, exist_ok=True)
        os.chdir("/not_a_task")

        with pytest.raises(ValueError) as excinfo:
            pdp.create_task_from_current_location("foo")

    def test_pdp_detects_current_directory(self, hello_world_tasks, pdp):
        pdp.scaffold()

        expect(pdp.current_path).to(equal(Path(".")))

        os.chdir("hello")

        expect(pdp.current_path).to(equal(Path("hello")))

    def test_pdp_detects_current_task(self, hello_world_tasks, pdp):
        pdp.scaffold()

        expect(pdp.current_task).to(be_none)

        os.chdir("hello")

        expect(pdp.current_task.task_name).to(equal("hello"))

        os.mkdir("dummy")

        os.chdir("dummy")

        expect(pdp.current_task).to(be_none)

    def test_pdp_picks_up_name_from_config(self, pdp):
        pdp.scaffold()

        pdp2 = PDP()
        pdp2.initialize()

        expect(pdp2.project_name).to(equal("test"))


class TestFlattenTasks:
    def test_flatten_tasks_creates_dict(self, hello_world_tasks, pdp):
        flattened = pdp.flatten_tasks()

        expect(isinstance(flattened, dict))
        expect(set(flattened.keys())).to(equal({"hello", "world"}))
        expect(flattened["hello"]).to(be_a(Task))

    def test_flatten_tasks_has_unique_task_ids(self, pdp):
        pdp.create_task("clean")
        pdp.create_task("analyze")

        os.chdir("/clean")
        pdp.create_task_from_current_location("generic_task")
        os.chdir("/analyze")
        pdp.create_task_from_current_location("generic_task")
        os.chdir("/")

        flattened = pdp.flatten_tasks()

        expect(set(flattened.keys())).to(
            equal({"clean", "analyze", "clean/generic_task", "analyze/generic_task"})
        )


class TestRun:
    def test_pdp_runs_task_by_name(self, pdp):
        task = pdp.create_task("hello")
        task.task_config.update_config({"entrypoint": "make"})

        mock_result = subprocess.CompletedProcess(
            args=["make"], returncode=0, stdout="hello\n"
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            return_code = pdp.run_task("hello")
            mock_run.assert_called_once_with("make", cwd=task.task_directory, shell=True)
            expect(return_code).to(equal(0))

    def test_pdp_raises_error_if_task_not_found(self, pdp):
        pdp.create_task("hello")

        with pytest.raises(ValueError) as excinfo:
            pdp.run_task("world")

        expect(str(excinfo.value)).to(equal("Task world not found"))

    def test_pdp_runs_all_tasks(self, make_task, pdp):
        pdp.scaffold()

        pdp.run_all()

        make_task.run.assert_called_once()
