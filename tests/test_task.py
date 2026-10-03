import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from expects import *
from ruamel.yaml import YAML

from pdp.task import Task, latest_mtime_in_dir
from tests.conftest import write_task_yml


def read_config_file(filename):
    return dict(YAML().load(Path(filename)))


def touch(path: Path, mtime: int):
    path.touch()
    os.utime(path, (mtime, mtime))


def test_task_runs_entrypoint_in_config(task, fs):
    task.scaffold()

    with open(task.task_config.path_to_config, "w") as f:
        f.write("entrypoint: echo hello\nsubtasks: []")

    mock_result = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="hello\n"
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        return_code = task.run()
        mock_run.assert_called_once_with(
            "echo hello", cwd=task.task_directory, shell=True, check=False
        )
        expect(return_code).to(equal(0))


def test_task_scaffold_creates_folders(task, fs):
    task.scaffold()

    expect(task.input_folder.is_dir()).to(be_true)
    expect(task.output_folder.is_dir()).to(be_true)
    expect(task.src_folder.is_dir()).to(be_true)


def test_task_scaffold_ignores_subtasks_and_always_creates_folders(fs):
    """Will revisit subtasks later"""
    Path("/hello").mkdir()
    write_task_yml("/hello", subtasks=["world"])
    task = Task("hello", Path("/hello"))

    task.scaffold()

    expect(task.input_folder.is_dir()).to(be_true)
    expect(task.output_folder.is_dir()).to(be_true)
    expect(task.src_folder.is_dir()).to(be_true)
    expect(Path("/hello/world").exists()).to(be_false)


def test_task_scaffold_passes_validation(task, fs):
    task.scaffold()

    expect(task.validation_errors()).to(equal([]))
    expect(task.validate()).to(be_true)


def test_task_validate_raises_on_unscaffolded_task(task, fs):
    errors = task.validation_errors()

    expect(errors).to(contain("Missing key(s): depends_on_tasks, entrypoint, name"))
    expect(errors).to(contain("name must be a non-empty string"))
    expect(errors).to(contain("input/ folder is missing"))
    expect(errors).to(contain("output/ folder is missing"))
    expect(task.validate()).to(be_false)


def test_task_id_is_directory_name(fs):
    Path("/pdp.yml").write_text("name: test\ntasks: []\n")

    task = Task("hello", Path("/somewhere/deeper/hello"))

    expect(task.task_id).to(equal("hello"))


def test_task_equality_based_on_repr(task, fs):
    task_name = "hello"
    task2 = Task(task_name, Path(task_name))

    expect(task).to(equal(task2))


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


def test_task_is_stale_when_output_dir_missing(raw_and_clean):
    raw, clean = raw_and_clean

    raw.output_folder.rmdir()

    expect(clean.is_stale).to(be_true)


def test_task_is_stale_when_src_is_newer(task, fs):
    task.scaffold()

    touch(task.src_folder / "script.py", 2000)
    touch(task.output_folder / "output.csv", 1000)
    expect(task.is_stale).to(be_true)


def test_task_not_stale_when_src_is_older(task, fs):
    task.scaffold()

    touch(task.src_folder / "script.py", 1000)
    touch(task.output_folder / "output.csv", 2000)

    expect(task.is_stale).to(be_false)


@pytest.fixture
def two_deps_and_clean(pdp, fs):
    raw1 = pdp.create_task("raw1")
    raw2 = pdp.create_task("raw2")
    clean = pdp.create_task("clean")
    pdp.scaffold()

    clean.task_config.update_config_key("depends_on_tasks", ["raw1", "raw2"])

    return raw1, raw2, clean


def test_task_is_stale_when_only_one_of_multiple_dependencies_is_newer(
    two_deps_and_clean,
):
    raw1, raw2, clean = two_deps_and_clean

    touch(clean.output_folder / "output.csv", 2000)
    touch(raw1.output_folder / "data1.csv", 1000)
    touch(raw2.output_folder / "data2.csv", 3000)

    expect(clean.is_stale).to(be_true)


def test_task_not_stale_when_all_dependencies_are_older(two_deps_and_clean):
    raw1, raw2, clean = two_deps_and_clean

    touch(clean.output_folder / "result.txt", 2000)
    touch(raw1.output_folder / "data1.txt", 1000)
    touch(raw2.output_folder / "data2.txt", 1500)

    expect(clean.is_stale).to(be_false)
