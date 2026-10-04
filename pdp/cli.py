from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console

from pdp.pdp import PDP
from pdp.pdp_errors import InvalidConfigError

app = typer.Typer(no_args_is_help=True)
err_console = Console(stderr=True)
console = Console()


def _print_version():
    rprint(pkg_version("pdp"))


def _version_callback(value: bool):
    if value:
        _print_version()
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    pass


def load_pdp():
    pdp = PDP()

    if not pdp.initialized:
        err_console.print("No project detected. Try `pdp init`.")
        raise typer.Exit(1)

    pdp.initialize()

    return pdp


@app.command()
def init(
    project_name: str = typer.Option(None, "--name", "-n", prompt="Project name")
) -> None:
    """
    Initialize the project.
    """

    pdp = PDP(project_name)
    pdp.initialize()


@app.command()
def scaffold():
    """
    Scaffold the project. That is, for each task, create input and output folders if they don't already exist.
    """

    pdp = load_pdp()
    pdp.scaffold()


@app.command()
def create(task_names: list[str]) -> None:
    """
    Create a task.
    
    Task names may contain uppercase or lowercase letters, numbers, and single underscores
    or dashes.
    """

    pdp = load_pdp()

    try:
        for task_name in task_names:
            pdp.create_task_from_current_location(task_name)
    except ValueError as e:
        err_console.print(f"Cannot create task: {e}")
        raise typer.Exit(1)


@app.command()
def validate():
    """
    Validate the pdp yml.
    """

    pdp = load_pdp()
    errors = pdp.validation_errors()

    if errors:
        err_console.print("Validation failed.")
        for error in errors:
            err_console.print(f"  {error}")
        raise typer.Exit(1)

    console.print("Valid.")


@app.command()
def run(task_id: Annotated[str | None, typer.Argument()] = None) -> None:
    """
    Run a task (by id) or all tasks (if no id given).
    """

    pdp = load_pdp()

    try:
        if task_id:
            return_code = pdp.run_task(task_id)
        elif pdp.current_path == Path("."):
            return_code = pdp.run_all()
        else:
            current_task = pdp.current_task

            if current_task is None:
                err_console.print(f"No task at {pdp.current_path}.")
                raise typer.Exit(1)

            return_code = pdp.run_task(current_task.task_id)
    except InvalidConfigError as e:
        err_console.print("Validation failed.")
        for error in str(e).split("\n"):
            err_console.print(f"  {error}")
        raise typer.Exit(1)

    raise typer.Exit(return_code)


@app.command()
def tree() -> None:
    """
    Print the task tree.
    """

    pdp = load_pdp()
    tree = pdp.task_tree()
    rprint(tree)

    raise typer.Exit(0)
