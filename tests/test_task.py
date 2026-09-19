import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from itertools import count

from ruamel.yaml import YAML
from expects import *
import pytest

from pdp.task import Task, latest_mtime_in_dir
from pdp.pdp_config import TaskConfig


def read_config_file(filename):
    return dict(YAML().load(Path(filename)))


@pytest.fixture
def task(fs):
    task_name = "hello"
    task = Task(task_name, Path(task_name))

    return task


def test_task_runs_entrypoint_in_config(task, fs):
    task.scaffold()

    with open(task.task_config.path_to_config, "w") as f:
        f.write("entrypoint: echo hello\nsubtasks: []")

    mock_result = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="hello\n"
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        return_code = task.run()
        mock_run.assert_called_once_with("echo hello", cwd=task.task_directory)
        expect(return_code).to(equal(0))


def test_task_create_subtask(task, fs):
    task.scaffold()

    subtask = task.create_subtask("world")

    task_dict = read_config_file("/hello/task.yml")

    expect(task_dict["name"]).to(equal("hello"))
    expect(task_dict["entrypoint"]).to(equal(""))
    expect(task_dict["subtasks"]).to(equal(["world"]))

    expect(Path("/hello/world/input").exists()).to(be_true)
    expect(Path("/hello/world/output").exists()).to(be_true)
    expect(Path("/hello/world/src").exists()).to(be_true)

    subtask_dict = read_config_file("/hello/world/task.yml")
    expect(subtask_dict["name"]).to(equal("world"))
    expect(subtask_dict["entrypoint"]).to(equal(""))
    expect(subtask_dict["subtasks"]).to(equal([]))

    # Removes the hello input, output, and src
    expect(Path("/hello/input").exists()).to(be_false)
    expect(Path("/hello/output").exists()).to(be_false)
    expect(Path("/hello/src").exists()).to(be_false)


def test_task_create_subtask_leaves_folders_if_nonempty(task, fs):
    task.scaffold()

    Path("/hello/src/test.py").touch()

    subtask = task.create_subtask("world")

    expect(Path("/hello/input").exists()).to(be_true)
    expect(Path("/hello/output").exists()).to(be_true)
    expect(Path("/hello/src").exists()).to(be_true)


def test_task_scaffold_scaffolds_subtasks(task, fs):
    task.scaffold()
    with open(task.task_config.path_to_config, "w") as f:
        f.write("entrypoint: \nsubtasks: ['world']")

    task.scaffold()
    expect(Path("/hello/world/input").exists()).to(be_true)
    expect(Path("/hello/world/output").exists()).to(be_true)
    expect(Path("/hello/world/src").exists()).to(be_true)

    expect(Path("/hello/input").exists()).to(be_false)
    expect(Path("/hello/output").exists()).to(be_false)
    expect(Path("/hello/src").exists()).to(be_false)


def test_task_equality_based_on_repr(task, fs):
    task_name = "hello"
    task2 = Task(task_name, Path(task_name))

    expect(task).to(equal(task2))


def test_task_runs_subtasks_if_exist(task, fs):
    task.scaffold()

    subtask = task.create_subtask("world")

    with open(subtask.task_config.path_to_config, "w") as f:
        f.write("entrypoint: echo world\nsubtasks: []")

    mock_result = subprocess.CompletedProcess(
        args=["echo", "world"], returncode=0, stdout="world\n"
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        return_code = task.run()
        mock_run.assert_called_once_with("echo world", cwd=subtask.task_directory)
        expect(return_code).to(equal(0))


def test_task_traverses_subtree(task, fs):
    task.scaffold()
    subtask = task.create_subtask("world")
    subtask2 = task.create_subtask("world2")
    subtask_world_child = task.create_subtask("world_child")

    counter = count(1)

    results = []
    callback = lambda num, task: results.append((num, task.task_name))
    task.subtree_traversal(counter, callback)

    expect(results).to(
        equal([(1, "hello"), (2, "world"), (3, "world2"), (4, "world_child")])
    )


def test_latest_mtime_in_dir_returns_newest_mtime(task, fs):
    task.scaffold()

    older_file = task.output_folder / "old.txt"
    older_file.touch()
    os.utime(older_file, (1000, 1000))

    newer_file = task.output_folder / "new.txt"
    newer_file.touch()
    os.utime(newer_file, (2000, 2000))

    expect(latest_mtime_in_dir(task.output_folder)).to(equal(2000))


def test_latest_mtime_in_dir_checks_subdirs(task, fs):
    task.scaffold()

    nested_dir = task.output_folder / "nested"
    nested_dir.mkdir()

    top_file = task.output_folder / "top.txt"
    top_file.touch()
    os.utime(top_file, (1000, 1000))

    nested_file = nested_dir / "deep.txt"
    nested_file.touch()
    os.utime(nested_file, (5000, 5000))

    expect(latest_mtime_in_dir(task.output_folder)).to(equal(5000))


def test_latest_mtime_in_dir_empty_returns_none(task, fs):
    task.scaffold()

    expect(latest_mtime_in_dir(task.output_folder)).to(be_none)


def touch(path: Path, mtime: int):
    path.touch()
    os.utime(path, (mtime, mtime))


@pytest.fixture
def raw_and_clean(fs):
    Path("/pdp.yml").write_text("tasks:\n  - raw\n  - clean\n")

    raw = Task("raw", Path("/raw"))
    raw.scaffold()

    clean = Task("clean", Path("/clean"))
    clean.scaffold()
    clean.task_config.update_config_key("depends_on_tasks", ["raw"])

    return raw, clean


def test_task_is_stale_when_output_missing(raw_and_clean):
    _, clean = raw_and_clean

    expect(clean.is_stale).to(be_true)


def test_task_is_stale_when_dependency_is_newer(raw_and_clean):
    raw, clean = raw_and_clean

    touch(clean.output_folder / "result.txt", 1000)
    touch(raw.output_folder / "data.txt", 2000)

    expect(clean.is_stale).to(be_true)


def test_task_not_stale_when_own_output_is_newer_than_dependency(raw_and_clean):
    raw, clean = raw_and_clean

    touch(raw.output_folder / "data.txt", 1000)
    touch(clean.output_folder / "result.txt", 2000)

    expect(clean.is_stale).to(be_false)
