# SPDX-License-Identifier: Apache-2.0

from typing import *

from vml._vendor import click

from vml._internal import cli
from vml._internal import click_util

from .runs_archive import archive_runs
from .runs_comment import comment_runs
from .runs_delete import delete_runs
from .runs_export import export_runs
from .runs_import import import_runs
from .runs_info import run_info
from .runs_label import label_runs
from .runs_list import list_runs, runs_list_options
from .runs_mark import mark_runs
from .runs_merge import merge_runs
from .runs_publish import publish_runs
from .runs_pull import pull_runs
from .runs_purge import purge_runs
from .runs_push import push_runs
from .runs_restore import restore_runs
from .runs_stop import stop_runs
from .runs_tag import tag_runs


@click.group(invoke_without_command=True, cls=click_util.Group)
@runs_list_options
@click.pass_context
def runs(ctx: click.Context, **kw: Any):
    """Show or manage runs.

    If `COMMAND` is omitted, lists runs. Refer to ``vml runs list --help`` for
    more information on the `list` command.
    """
    if not ctx.invoked_subcommand:
        ctx.invoke(list_runs, **kw)
    else:
        if _params_specified(kw):
            cli.error(
                f"options cannot be listed before command ('{ctx.invoked_subcommand}')"
            )


def _params_specified(kw: Dict[str, Any]):
    return any((kw[key] for key in kw))


runs.add_command(archive_runs)
runs.add_command(comment_runs)
runs.add_command(delete_runs)
runs.add_command(export_runs)
runs.add_command(import_runs)
runs.add_command(label_runs)
runs.add_command(list_runs)
runs.add_command(mark_runs)
runs.add_command(merge_runs)
runs.add_command(publish_runs)
runs.add_command(pull_runs)
runs.add_command(purge_runs)
runs.add_command(push_runs)
runs.add_command(restore_runs)
runs.add_command(run_info)
runs.add_command(stop_runs)
runs.add_command(tag_runs)
