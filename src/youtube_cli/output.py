from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any

import click
import yaml
from rich.console import Console
from rich.pretty import Pretty

from .errors import YoutubeCliError

console = Console()


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"
    YAML = "yaml"


def resolve_output_format(as_json: bool, as_yaml: bool) -> OutputFormat:
    if as_json and as_yaml:
        raise click.ClickException("`--json` 和 `--yaml` 不能同时使用。")
    if as_json:
        return OutputFormat.JSON
    if as_yaml:
        return OutputFormat.YAML
    return OutputFormat.HUMAN


def envelope(
    *,
    command: str,
    data: Any,
    source: str = "yt_dlp",
    ok: bool = True,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "schema_version": 1,
        "source": source,
        "command": command,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data": data,
        "error": error,
    }


def emit(data: Any, *, command: str, output_format: OutputFormat, source: str = "yt_dlp") -> None:
    payload = envelope(command=command, data=data, source=source)
    if output_format is OutputFormat.JSON:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if output_format is OutputFormat.YAML:
        click.echo(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
        return
    console.print(Pretty(data, expand_all=True))


def emit_error(error: YoutubeCliError, *, command: str, output_format: OutputFormat) -> None:
    payload = envelope(
        command=command,
        data=None,
        source=error.source,
        ok=False,
        error=error.as_dict(),
    )
    if output_format is OutputFormat.JSON:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(error.exit_code)
    if output_format is OutputFormat.YAML:
        click.echo(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
        raise SystemExit(error.exit_code)
    console.print(f"[red]{error.code}[/red]: {error.message}")
    if error.hint:
        console.print(f"[yellow]hint[/yellow]: {error.hint}")
    raise SystemExit(error.exit_code)
