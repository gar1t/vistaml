# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import *

import click

from .. import click_util

from . import ac_support
from . import runs_support


def publish_params(fn: Callable[..., Any]):
    click_util.append_params(
        fn,
        [
            runs_support.runs_arg,
            click.Option(
                ("-d", "--dest"),
                metavar="DIR",
                help="Destination to publish runs.",
                shell_complete=ac_support.ac_dir(),
            ),
            click.Option(
                ("-t", "--template"),
                metavar="VAL",
                help="Run template used to publish runs.",
            ),
            click.Option(
                ("-i", "--index-template"),
                metavar="VAL",
                help="Index template used to publish runs.",
            ),
            click.Option(
                ("-f", "--files"),
                help=(
                    "Copy run files as configured by the operation. "
                    "By default, run files are not copied. Use `--all-files` "
                    "to copy all files regardless of how the operation is "
                    "configured."
                ),
                is_flag=True,
            ),
            click.Option(
                ("-a", "--all-files"),
                help=(
                    "Copy all run files. By default, run files are not copied. "
                    "Use `--files` to copy only files as configured by the "
                    "operation."
                ),
                is_flag=True,
            ),
            click.Option(
                ("-L", "--include-links"),
                help="Include links when publishing files. Implies --files.",
                is_flag=True,
            ),
            click.Option(
                ("--no-md5",),
                help="Do not calculate MD5 digests for run files.",
                is_flag=True,
            ),
            click.Option(
                ("--include-batch",), help="Include batch runs.", is_flag=True
            ),
            click.Option(
                ("-r", "--refresh-index"),
                help="Refresh runs index without publishing anything.",
                is_flag=True,
            ),
            runs_support.all_filters,
            click.Option(
                ("-y", "--yes"),
                help="Do not prompt before publishing.",
                is_flag=True,
            ),
        ],
    )
    return fn


@click.command("publish")
@publish_params
@click.pass_context
@click_util.use_args
@click_util.render_doc
def publish_runs(ctx: click.Context, args: Any):
    """Publish one or more runs.

    By default, runs are published to 'published-runs' subdirectory. To specify
    a different location, use `--dest`.

    A published run is a subdirectory of destination `DIR` that contains
    run-specific files:

    - `run.yml` - run information (e.g. run ID, operation, status, etc.)

    - `flags.yml` - run flags

    - `output.txt` - run output written to stdout/stderr

    - `scalars.csv` - summary of run scalar values

    - `files.csv` - list of files associated with the run

    - `sourcecode/` - subdirectory containing project source code at the time
      run was started

    - `runfiles/` - files associated with the run

    {{ runs_support.runs_arg }}

    {{ runs_support.all_filters }}
    """
    print("TODO publish runs")

    # from . import publish_impl

    # publish_impl.publish(args, ctx)
