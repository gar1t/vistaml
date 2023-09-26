# SPDX-License-Identifier: Apache-2.0

from typing import *

import os

import typer

from .__init__ import __version__

from ._internal import cli
from ._internal import exitcodes

from ._internal.commands.main import main_app

if os.getenv("TERM") in ("unknown", "dumb"):
    import typer.core

    # Disable use of Rich formatting
    typer.core.rich = None  # type: ignore


def main():
    app = main_app()
    try:
        app()
    except SystemExit as e:
        handle_system_exit(e)


def handle_system_exit(e: SystemExit):
    msg, code = system_exit_params(e)
    if msg:
        cli.err(f"gage: {msg}")
    raise SystemExit(code)


def system_exit_params(e: SystemExit) -> tuple[str | None, int]:
    msg: str | None
    code: int
    if isinstance(e.code, tuple) and len(e.code) == 2:
        msg, code = cast(tuple[str, int], e.code)
    elif isinstance(e.code, int):
        msg, code = None, e.code
    else:
        msg, code = e.code, exitcodes.DEFAULT_ERROR
    return msg, code


if __name__ == "__main__":
    main()
