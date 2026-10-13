from __future__ import annotations

import fnmatch
import glob
from collections import Counter
from pathlib import Path
from typing import Any

import click

from .scan import AUDIO_EXTENSIONS, iter_audio_files
from .store import StoreError, load, record_for_path, save, upsert


def _audio_matches(pattern: str) -> list[Path]:
    candidate = Path(pattern).expanduser()
    if candidate.exists() and candidate.is_dir():
        matches = iter_audio_files(candidate)
    elif glob.has_magic(pattern):
        matches = [Path(item) for item in glob.glob(pattern, recursive=True)]
    else:
        matches = [candidate]

    return sorted(
        {
            path.resolve()
            for path in matches
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        }
    )


def _normalise_tags(tags: tuple[str, ...]) -> set[str]:
    cleaned = {tag.strip().casefold() for tag in tags if tag.strip()}
    if not cleaned:
        raise click.ClickException("Provide at least one non-empty tag.")
    return cleaned


def _load_or_error(path: Path) -> dict[str, Any]:
    try:
        return load(path)
    except StoreError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group("tag")
def tag_group() -> None:
    """Add, remove, or list local audio tags."""


@tag_group.command("add")
@click.argument("pattern")
@click.argument("tags", nargs=-1, required=True)
@click.option("--db", "db_path", type=click.Path(path_type=Path), default="voiceprep.json", show_default=True)
def add_tags(pattern: str, tags: tuple[str, ...], db_path: Path) -> None:
    """Add TAGS to audio files matching PATTERN."""
    matches = _audio_matches(pattern)
    if not matches:
        raise click.ClickException(f"No supported audio files matched: {pattern}")
    requested = _normalise_tags(tags)
    db = _load_or_error(db_path)

    try:
        for audio_path in matches:
            new_record = record_for_path(audio_path)
            existing = db["files"].get(new_record["id"], {})
            record = {**new_record, **existing, "path": str(audio_path)}
            record["tags"] = sorted(set(record.get("tags", [])) | requested)
            upsert(db, record)
        save(db, db_path)
    except StoreError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Tagged {len(matches)} file(s).")


@tag_group.command("remove")
@click.argument("pattern")
@click.argument("tags", nargs=-1, required=True)
@click.option("--db", "db_path", type=click.Path(path_type=Path), default="voiceprep.json", show_default=True)
def remove_tags(pattern: str, tags: tuple[str, ...], db_path: Path) -> None:
    """Remove TAGS from stored records whose path matches PATTERN."""
    requested = _normalise_tags(tags)
    db = _load_or_error(db_path)
    absolute_pattern = str(Path(pattern).expanduser().absolute())
    matched = 0
    for record in db["files"].values():
        if fnmatch.fnmatch(record["path"], absolute_pattern):
            record["tags"] = sorted(set(record.get("tags", [])) - requested)
            matched += 1
    if not matched:
        raise click.ClickException(f"No stored audio paths matched: {pattern}")
    try:
        save(db, db_path)
    except StoreError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Updated {matched} file(s).")


@tag_group.command("list")
@click.option("--db", "db_path", type=click.Path(path_type=Path), default="voiceprep.json", show_default=True)
def list_tags(db_path: Path) -> None:
    """List all tags and the number of records using each one."""
    db = _load_or_error(db_path)
    counts = Counter(tag for record in db["files"].values() for tag in record.get("tags", []))
    for tag, count in sorted(counts.items()):
        click.echo(f"{tag}\t{count}")


def register(root: click.Group) -> None:
    root.add_command(tag_group)
