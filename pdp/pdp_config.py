from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ruamel.yaml import YAML

from .pdp_errors import UninitializedProjectError


def requires_initialization(method):
    def wrapper(self, *args, **kwargs):
        if not self.initialized:
            raise UninitializedProjectError("Config not initialized.")
        return method(self, *args, **kwargs)

    return wrapper


class GenericConfig(ABC):
    def __init__(self, name, task_key, path_to_config) -> None:
        self.yaml = YAML()

        self.task_key = task_key
        self.path_to_config = Path(path_to_config).resolve()
        self.config = self.read_config_file()
        self.name = name or self.config.get("name", None)

    def read_config_file(self):
        try:
            return dict(self.yaml.load(self.path_to_config))
        except (TypeError, FileNotFoundError):
            return {}

    @requires_initialization
    def update_config(self, config):
        """Write new config, overwrites old config"""
        self.yaml.dump(config, self.path_to_config)
        self.config = config

    @requires_initialization
    def update_config_key(self, key, value) -> None:

        self.config[key] = value
        self.update_config(self.config)

    @property
    def initialized(self):
        if not self.path_to_config.exists():
            return False

        return len(self.config) != 0

    @requires_initialization
    def add_task(self, task_name):
        tasks = self.config[self.task_key]

        if task_name not in tasks:
            tasks.append(task_name)

            self.update_config_key(self.task_key, tasks)

    @property
    def tasks(self):
        return self.config.get(self.task_key, [])

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}, {self.path_to_config})"

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def validation_errors(self) -> list[str]:
        """Reasons self.config fails validation. Empty if valid."""

    def validate(self) -> bool:
        return not self.validation_errors()


class PDPConfig(GenericConfig):
    def __init__(self, project_name, path_to_config) -> None:
        super().__init__(project_name, "tasks", path_to_config)

    def initialize(self):
        if self.initialized:
            return

        self.yaml.dump({"name": self.name, "tasks": []}, self.path_to_config)

        self.config = self.read_config_file()

    def validation_errors(self) -> list[str]:
        errors = []

        missing_keys = [key for key in ("tasks", "name") if key not in self.config]
        if missing_keys:
            errors.append(f"Missing key(s) in pdp.yml: {(',').join(missing_keys)}")
        else:
            if not isinstance(self.config["tasks"], list):
                errors.append(
                    f"tasks must be a list, got {type(self.config['tasks']).__name__}"
                )

        return errors


class TaskConfig(GenericConfig):
    def __init__(self, task_name, path_to_config) -> None:
        super().__init__(task_name, "subtasks", path_to_config)

    CONFIG_DEFAULTS: ClassVar[dict[str, object]] = {
        "entrypoint": "",
        "subtasks": [],
        "depends_on_tasks": [],
        "depends_on_files": [],
    }

    def initialize(self) -> None:
        if self.initialized:
            self.config = self.read_config_file()
            return

        self.yaml.dump({"name": self.name, **self.CONFIG_DEFAULTS}, self.path_to_config)

        self.config = self.read_config_file()

    def validation_errors(self) -> list[str]:
        """Error messages from failed self.config validation. Empty if valid."""

        # Validate task yml
        allowed_keys = {"name", *self.CONFIG_DEFAULTS}
        errors = []

        unexpected = set(self.config.keys()) - allowed_keys
        missing = allowed_keys - set(self.config.keys())

        if unexpected:
            errors.append(f"Unexpected key(s): {', '.join(sorted(unexpected))}")

        if missing:
            errors.append(f"Missing key(s): {', '.join(sorted(missing))}")

        if not self.config.get("name"):
            errors.append("name must be a non-empty string")

        # Organize all errors for output
        for key, default in self.CONFIG_DEFAULTS.items():
            if key in self.config and not isinstance(self.config[key], type(default)):
                errors.append(
                    f"{key} must be {type(default).__name__}, "
                    f"got {type(self.config[key]).__name__}"
                )

        return errors

    @property
    @requires_initialization
    def entrypoint(self):
        self.config = self.read_config_file()
        return self.config["entrypoint"]

    @property
    @requires_initialization
    def depends_on_tasks(self):
        self.config = self.read_config_file()
        return self.config.get("depends_on_tasks", [])

    @property
    @requires_initialization
    def depends_on_files(self):
        self.config = self.read_config_file()
        return self.config.get("depends_on_files", [])
