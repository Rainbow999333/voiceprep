from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from .store import StoreError, load


def _safe_list_field(value: Any, name: str) -> str:
    text = "" if value is None else str(value)
    if "|" in text or "\n" in text or "\r" in text:
        raise click.ClickException(f"{name} cannot contain pipes or newlines in .list output.")
    return text


@click.command("export")
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Tag to match; repeat for multiple tags. Omit to export all records.",
)
@click.option("--any", "match_any", is_flag=True, help="Match any tag instead of requiring all tags.")
@click.option("--format", "output_format", type=click.Choice(["paths", "list"]), default="paths", show_default=True)
@click.option("--output", type=click.Path(path_type=Path), help="Write to a file instead of stdout.")
@click.option("--speaker", default="speaker", show_default=True, help="Speaker field for GPT-SoVITS .list output.")
@click.option("--language", default="auto", show_default=True, help="Language field for GPT-SoVITS .list output.")
@click.option("--db", "db_path", type=click.Path(path_type=Path), default="voiceprep.json", show_default=True)
def export_command(
    tags: tuple[str, ...],
    match_any: bool,
    output_format: str,
    output: Path | None,
    speaker: str,
    language: str,
    db_path: Path,
) -> None:
    """Export records matching tags as paths or GPT-SoVITS .list lines."""
    requested = {tag.strip().casefold() for tag in tags if tag.strip()}
    if tags and not requested:
        raise click.ClickException("Provide a non-empty --tag value.")
    try:
        db = load(db_path)
    except StoreError as exc:
        raise click.ClickException(str(exc)) from exc

    selected: list[dict[str, Any]] = []
    for record in db["files"].values():
        available = set(record.get("tags", []))
        if not requested or (match_any and requested & available) or (not match_any and requested <= available):
            selected.append(record)
    selected.sort(key=lambda record: record["path"])

    if output_format == "paths":
        lines = [record["path"] for record in selected]
    else:
        safe_speaker = _safe_list_field(speaker, "speaker")
        safe_language = _safe_list_field(language, "language")
        lines = []
        for record in selected:
            transcript = record.get("transcript", {})
            lines.append(
                "|".join(
                    [
                        _safe_list_field(record["path"], "audio path"),
                        safe_speaker,
                        safe_language,
                        _safe_list_field(transcript.get("text"), "transcript text"),
                    ]
                )
            )

    content = "\n".join(lines)
    if lines:
        content += "\n"
    if output is None:
        click.echo(content, nl=False)
        return
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Could not write export {output}: {exc}") from exc
    click.echo(f"Exported {len(lines)} record(s) to {output}.", err=True)


def register(root: click.Group) -> None:
    root.add_command(export_command)
