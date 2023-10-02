# SPDX-License-Identifier: Apache-2.0

from typing import *

import os
import re
import shlex

import click

import rich.box
import rich.columns
import rich.console
import rich.json
import rich.markdown
import rich.markup
import rich.padding
import rich.panel
import rich.prompt
import rich.style
import rich.text
import rich.table

import typer.core

__all__ = [
    "AliasGroup",
    "Group",
    "Panel",
    "Table",
    "confirm",
    "console_width",
    "err",
    "error_message",
    "exit_with_error",
    "incompatible_with",
    "label",
    "markdown",
    "out",
    "status",
]

_out = rich.console.Console(soft_wrap=False)

_err = rich.console.Console(stderr=True, soft_wrap=False)

is_plain = os.getenv("TERM") in ("dumb", "unknown")

TABLE_HEADER_STYLE = "bright_yellow"
TABLE_BORDER_STYLE = "dim"
PANEL_TITLE_STYLE = "bright_yellow"
LABEL_STYLE = "cyan1"
SECOND_LABEL_STYLE = "cyan"
VALUE_STYLE = "dim"


def run_status_style(status: str):
    match status:
        case "completed":
            return "green4"
        case "error" | "terminated":
            return "red3"
        case "staged" | "pending":
            return "dim"
        case "running":
            return "yellow italic"
        case _:
            return ""


def console_width():
    return _out.width


def out(val: Any, style: str | None = None, wrap: bool = False, err: bool = False):
    print = _err.print if err else _out.print
    print(val, soft_wrap=not wrap, style=style)


def err(val: Any, style: str | None = None):
    out(val, err=True)


def error_message(msg: str):
    err(msg)


def exit_with_error(msg: str, code: int = 1) -> NoReturn:
    error_message(msg)
    raise SystemExit(code)


def text(s: str, style: str | rich.style.Style = ""):
    return rich.text.Text(s, style=style)


def json(val: Any):
    return rich.json.JSON.from_data(val)


def label(s: str):
    return text(s, style=LABEL_STYLE)


def markdown(md: str):
    return rich.markdown.Markdown(md)


def markup(mu: str):
    return rich.markup.render(mu)


def pad(val: Any, padding: rich.padding.PaddingDimensions):
    return rich.padding.Padding(val, padding)


class YesNoConfirm(rich.prompt.Confirm):
    prompt_suffix = " "

    def make_prompt(self, default: bool) -> rich.text.Text:
        prompt = self.prompt.copy()
        prompt.end = ""
        prompt.append(" ")
        default_part = rich.text.Text(
            "(Y/n)" if default else "(y/N)",
            style="prompt.default",
        )
        prompt.append(default_part)
        prompt.append(self.prompt_suffix)
        return prompt


def confirm(prompt: str, default: bool = False):
    return YesNoConfirm.ask(prompt, default=default)


def status(description: str):
    return _out.status(description)


def incompatible_with(*incompatible: str):
    """Decorator to specify incompatible params."""

    def callback(value: Any, param: typer.core.TyperArgument, ctx: click.Context):
        if not value:
            return value
        for used_param in ctx.params:
            if param.name == used_param or used_param not in incompatible:
                continue
            err(
                markup(
                    f"[b cyan]{param.name}[/] and [b cyan]{used_param}[/] "
                    "cannot be used together.\n\n"
                    f"Try '[b]{ctx.command_path} {ctx.help_option_names[0]}[/b]' "
                    "for help."
                )
            )
            raise SystemExit()
        return value

    return callback


class pager:
    _pager_env = os.getenv("PAGER") or os.getenv("MANPAGER")

    def __init__(self):
        self._pager = _out.pager(styles=_pager_supports_styles(self._pager_env))

    def __enter__(self):
        if self._pager_env is None:
            os.environ["PAGER"] = "less -r"
        return self._pager.__enter__()

    def __exit__(self, *exc: Any):
        self._pager.__exit__(*exc)
        if self._pager_env is None:
            del os.environ["PAGER"]


def _pager_supports_styles(pager: str | None):
    if pager is None:
        return True
    parts = shlex.split(pager)
    return parts[0] == "less" and "-r" in parts[1:]


ColSpec = str | tuple[str, dict[str, Any]]


def Table(header: list[ColSpec] | None = None, **kw: Any):
    t = rich.table.Table(
        show_header=header is not None,
        box=rich.box.ROUNDED if not is_plain else rich.box.MARKDOWN,
        border_style=TABLE_BORDER_STYLE,
        header_style=TABLE_HEADER_STYLE,
        **kw,
    )
    for col in header or []:
        col_header, col_kw = _split_col(col)
        t.add_column(col_header, **col_kw)
    return t


def _split_col(col: ColSpec) -> tuple[str, dict[str, Any]]:
    if isinstance(col, str):
        return col, {}
    else:
        header, kw = col
        return header, kw


def Panel(renderable: rich.console.RenderableType, **kw: Any):
    return rich.panel.Panel(
        renderable,
        box=rich.box.ROUNDED if not is_plain else rich.box.MARKDOWN,
        **kw,
    )


def Group(*renderables: rich.console.RenderableType):
    return rich.console.Group(*renderables)


def Columns(renderables: Iterable[rich.console.RenderableType], **kw: Any):
    return rich.columns.Columns(renderables, **kw)


class AliasGroup(typer.core.TyperGroup):
    """click Group subclass that supports commands with aliases.

    To alias a command, include the aliases in the command name,
    separated by commas.
    """

    _CMD_SPLIT_P = re.compile(r", ?")

    def get_command(self, ctx: click.Context, cmd_name: str):
        return super().get_command(ctx, self._map_name(cmd_name))

    def _map_name(self, default_name: str):
        for cmd in self.commands.values():
            if cmd.name and default_name in self._CMD_SPLIT_P.split(cmd.name):
                return cmd.name
        return default_name


def rich_markdown_element(name: str):
    def decorator(cls: Type[rich.markdown.MarkdownElement]):
        rich.markdown.Markdown.elements[name] = cls

    return decorator


@rich_markdown_element("heading_open")
class _MarkdownHeading(rich.markdown.Heading):
    """Internal Rich Markdown heading.

    To change the hard-coded heading alignment from center to left, we
    need to patch `rich.markdown.Markdown.elements` with a modified
    heading implementation.
    """

    def __rich_console__(
        self,
        console: rich.console.Console,
        options: rich.console.ConsoleOptions,
    ) -> rich.console.RenderResult:
        text = self.text
        text._text = [s.upper() for s in text._text]
        if self.tag == "h1":
            text.justify = "center"
            yield rich.panel.Panel(text)
        else:
            if self.tag == "h2":
                yield Text("")
            yield text


@rich_markdown_element("table_open")
class _TableElement(rich.markdown.TableElement):
    def __rich_console__(
        self,
        console: rich.console.Console,
        options: rich.console.ConsoleOptions,
    ) -> rich.console.RenderResult:
        table = rich.table.Table(box=rich.box.ROUNDED)

        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                table.add_column(column.content)

        if self.body is not None:
            for row in self.body.rows:
                row_content = [element.content for element in row.cells]
                table.add_row(*row_content)

        yield table


class PlainHelpFormatter(click.HelpFormatter):
    def write_text(self, text: str) -> None:
        super().write_text(_strip_markup(text))

    def write_dl(
        self,
        rows: Sequence[Tuple[str, str]],
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        super().write_dl(
            [(name, _strip_markup(val)) for name, val in rows],
            col_max,
            col_spacing,
        )


def _strip_markup(s: str):
    return rich.markup.render(s).plain
