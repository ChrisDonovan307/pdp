from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console

from pdp.pdp import PDP, RunReport
from pdp.pdp_errors import InvalidConfigError
from pdp.utils import ICONS

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


def _exit_validation_failed(error: InvalidConfigError):
    err_console.print(f"{ICONS['error']} Validation failed.")
    for line in str(error).split("\n"):
        err_console.print(f"  {line}")
    raise typer.Exit(1)


def load_pdp():
    try:
        pdp = PDP()

        if not pdp.initialized:
            err_console.print("No project detected. Try `pdp init`.")
            raise typer.Exit(1)

        pdp.initialize()
    except InvalidConfigError as e:
        _exit_validation_failed(e)

    return pdp


@app.command()
def init(
    project_name: str = typer.Option(None, "--name", "-n"),
) -> None:
    """Initialize the project.

    Prompts for a project name and creates the root pdp.yml file
    """    
    try:
        pdp = PDP(project_name)
        if pdp.initialized:
            console.print(f"Project '{pdp.config.name}' is already initialized.")
        elif not project_name:
            pdp.config.name = typer.prompt("Project name")
        pdp.initialize()
    except InvalidConfigError as e:
        _exit_validation_failed(e)


@app.command()
def scaffold():
    """
    Scaffold the project. 
    
    For each task, create input and output folders if they don't already exist.
    """

    pdp = load_pdp()
    pdp.scaffold()


@app.command()
def create(
    task_names: list[str],
    deps: Annotated[
        list[str] | None,
        typer.Option("--dep", "-d", help="Existing task this depends on. Repeatable."),
    ] = None,
) -> None:
    """
    Create a task.

    Task names may contain uppercase or lowercase letters, numbers, and single underscores
    or dashes.
    """

    pdp = load_pdp()

    try:
        for task_name in task_names:
            pdp.create_task_from_current_location(task_name, deps or [])
    except ValueError as e:
        err_console.print(f"Cannot create task: {e}")
        raise typer.Exit(1)


@app.command()
def depend(task_name: str, deps: list[str]) -> None:
    """
    Add task dependencies to an existing task.
    
    Both the task and the dependencies must already exist and be valid.
    """

    pdp = load_pdp()

    try:
        pdp.add_dependencies(task_name, deps)
    except ValueError as e:
        err_console.print(f"Cannot add dependency: {e}")
        raise typer.Exit(1)


@app.command()
def validate():
    """Validate the PDP project

    Validates that:\n
    - Project is initiated and there are no circular task dependencies\n
    - Each task contains input/, output/, and src/ folders\n
    - Outputs of task dependencies are symlinked into task/input/.
    """
    pdp = load_pdp()
    errors = pdp.validation_errors()

    if errors:
        err_console.print(f"{ICONS['error']} Validation failed.")
        for error in errors:
            err_console.print(f"  {error}")
        raise typer.Exit(1)

    console.print(f"{ICONS['success']} Project is valid.")


@app.command()
def run(
    task_id: Annotated[str | None, typer.Argument()] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Run tasks regardless of staleness.")
    ] = False,
) -> None:
    """
    Run a task (by id) or all tasks (if no id given).
    """

    pdp = load_pdp()

    try:
        if task_id:
            report: RunReport = pdp.run_task(task_id, force)
        elif pdp.current_path == Path("."):
            report: RunReport = pdp.run_all(force)
        else:
            current_task = pdp.current_task

            if current_task is None:
                err_console.print(f"No task at {pdp.current_path}.")
                raise typer.Exit(1)

            report: RunReport = pdp.run_task(current_task.task_id, force)
    except InvalidConfigError as e:
        _exit_validation_failed(e)
    except ValueError as e:
        # Bad task id
        err_console.print(str(e))
        raise typer.Exit(1)

    report.render(console, err_console)

    raise typer.Exit(report.exit_code)


@app.command()
def tree() -> None:
    """
    Print the task tree.
    """

    pdp = load_pdp()
    tree = pdp.task_tree()
    rprint(tree)

    raise typer.Exit(0)

@app.command()
def status() -> None:
    """
    Check project status.
    """

    console.print("status!")

    raise typer.Exit(0)
