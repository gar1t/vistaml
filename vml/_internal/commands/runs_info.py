# SPDX-License-Identifier: Apache-2.0

from typing import *

from vml._vendor import click

from vml._internal import click_util

from . import remote_support
from . import runs_support


@click.command("info")
@runs_support.run_arg
@click.option("-c", "--comments", help="Show run comments.", is_flag=True)
@click.option("-e", "--env", help="Show run environment.", is_flag=True)
@click.option("-d", "--deps", help="Show resolved dependencies.", is_flag=True)
@click.option("-m", "--manifest", help="Show manifest.", is_flag=True)
@click.option("-p", "--plugins", help="Show plugins.", is_flag=True)
@click.option(
    "-s",
    "--all-scalars",
    help=(
        "Show all scalar values. By default only shows last values for "
        "non-system scalars."
    ),
    is_flag=True,
)
@click.option("--json", help="Format information as JSON.", is_flag=True)
@click.option("--private-attrs", is_flag=True, hidden=True)
@runs_support.all_filters
@remote_support.remote_option("Show info for remote run.")
@click.pass_context
@click_util.use_args
@click_util.render_doc
def run_info(ctx: click.Context, args: Any):
    """Show run information.

    This command shows information for a single run.

    {{ runs_support.run_arg }}

    If RUN isn't specified, the latest run is selected.

    ### Additional Information

    You can show additional run information by specifying options. You may use
    multiple options to show more information. Refer to the options below for
    what additional information is available.

    {{ runs_support.all_filters }}

    ### Remote Runs

    Use `--remote` to show info for a remote run.

    {{ remote_support.remote_option }}
    """
    print("TODO show runs info")

    # from . import runs_impl

    # runs_impl.run_info(args, ctx)
