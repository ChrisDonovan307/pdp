import os
import subprocess
from pathlib import Path
from unittest.mock import call, patch

import pytest
from expects import *
from ruamel.yaml import YAML
from typer.testing import CliRunner

from pdp.cli import app


@pytest.fixture
def runner(fs):
    runner = CliRunner(mix_stderr=False)
    _ = runner.invoke(app, ["init", "--name", "test"])

    return runner


def read_config_file(filename):
    return dict(YAML().load(Path(filename)))


def test_init_creates_pdp_yaml(runner, fs):
    config_dict = read_config_file("/pdp.yml")
    expect(config_dict["name"]).to(equal("test"))
    expect(config_dict["tasks"]).to(equal([]))


def test_create_tasks(runner, fs):
    _ = runner.invoke(app, ["create", "hello", "world"])

    expect(Path("/hello/input").exists()).to(be_true)
    expect(Path("/hello/output").exists()).to(be_true)
    expect(Path("/hello/src").exists()).to(be_true)

    expect(Path("/world/input").exists()).to(be_true)
    expect(Path("/world/output").exists()).to(be_true)
    expect(Path("/world/src").exists()).to(be_true)


def test_create_subtasks(runner, fs):
    _ = runner.invoke(app, ["create", "hello"])

    os.chdir("hello")

    _ = runner.invoke(app, ["create", "world"])

    expect(Path("/hello/input").exists()).to(be_false)
    expect(Path("/hello/output").exists()).to(be_false)
    expect(Path("/hello/src").exists()).to(be_false)

    expect(Path("/hello/world/input").exists()).to(be_true)
    expect(Path("/hello/world/output").exists()).to(be_true)
    expect(Path("/hello/world/src").exists()).to(be_true)

    _ = YAML()
    task_dict = read_config_file("/hello/task.yml")

    expect(task_dict["name"]).to(equal("hello"))
    expect(task_dict["entrypoint"]).to(equal(""))
    expect(task_dict["subtasks"]).to(equal(["world"]))


def test_create_errs_if_creating_task_from_invalid_location(runner, fs):
    Path("/not_a_task").mkdir(parents=True, exist_ok=True)
    os.chdir("not_a_task")

    result = runner.invoke(app, ["create", "hello"])

    expect(result.exit_code).to(equal(1))
    expect(result.stderr).to(contain("Cannot create task"))


def test_runs_current_task(runner, fs):
    result = runner.invoke(app, ["create", "hello"])

    os.chdir("hello")

    with open("/hello/task.yml", "w") as f:
        f.write("name: hello\nentrypoint: echo hello\nsubtasks: []")

    mock_result = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="world\n"
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = runner.invoke(app, ["run"])
        mock_run.assert_called_once_with("echo hello", cwd=Path("/hello"), shell=True, check=False)
        expect(result.exit_code).to(equal(0))


def test_runs_whole_project(runner, fs):
    result = runner.invoke(app, ["create", "hello"])
    result = runner.invoke(app, ["create", "world"])

    with open("/hello/task.yml", "w") as f:
        f.write("entrypoint: echo hello\nsubtasks: []")

    with open("/world/task.yml", "w") as f:
        f.write("entrypoint: echo world\nsubtasks: []")

    mock_hello = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="world\n"
    )

    mock_world = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="world\n"
    )

    with patch("subprocess.run", side_effect=[mock_hello, mock_world]) as mock_run:
        result = runner.invoke(app, ["run"])
        mock_run.assert_has_calls(
            [
                call("echo hello", cwd=Path("/hello"), shell=True, check=False),
                call("echo world", cwd=Path("/world"), shell=True, check=False),
            ]
        )
        expect(result.exit_code).to(equal(0))


def test_tree_enumerates_tasks_and_subtasks(runner, fs):
    result = runner.invoke(app, ["create", "hello"])
    result = runner.invoke(app, ["create", "world"])

    os.chdir("/world")
    result = runner.invoke(app, ["create", "subtask1"])

    result = runner.invoke(app, ["tree"])

    expect(result.stdout).to(
        equal(
            """1. test
├── 2. hello
└── 3. world
    └── 4. subtask1
"""
        )
    )
