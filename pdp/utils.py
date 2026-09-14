from pathlib import Path


def find_project_root(config_name: str, start: Path | None = None) -> Path:
    """Walk up directories until you find config file. Starts by current cwd() 
    by default, but can be given a path to accommodate using it Task.task_id

    Args:
        config_name (str): Name of config file
        start (Path | None, optional): Path to start walking from. Defaults to None.

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
