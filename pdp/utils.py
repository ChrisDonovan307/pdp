import re
from pathlib import Path

from rich.emoji import Emoji

ICONS = {
    "success": Emoji("white_check_mark"),
    "error": Emoji("x"),
}

TASK_NAME_RULE = "letters and digits, separated by single underscores or dashes"
_TASK_NAME = re.compile(r"[A-Za-z0-9]+([_-][A-Za-z0-9]+)*")


def is_valid_task_name(task_name) -> bool:
    """Only allow upper/lower case letters and digits separated by single underscores
    or single dashes. This lets us get a clean input_env_var and reserves double
    under score `__` for eventual nested subtasks."""
    return isinstance(task_name, str) and _TASK_NAME.fullmatch(task_name) is not None


def input_env_var(task_id: str) -> str:
    """Turn task_id into uppercase var with only `_` for shell"""
    return f"PDP_INPUT_{task_id.upper().replace('-', '_')}"


def find_project_root(config_name: str, start: Path | None = None) -> Path:
    """Walk up directories until you find config file. Starts by current cwd()
    by default, but can be given a path to accommodate using it Task.task_id

    Args:
        config_name: Name of config file
        start: Path to start walking from. Defaults to None.

    Returns:
        Path: Absolute path to project root
    """
    current_path = (start or Path.cwd()).resolve()
    while current_path != current_path.parent:
        if (current_path / config_name).exists():
            return current_path
        current_path = current_path.parent

    if (current_path / config_name).exists():
        return current_path

    return (start or Path.cwd()).resolve()
