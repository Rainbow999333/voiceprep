from __future__ import annotations

from pathlib import Path

import click

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg"}


def iter_audio_files(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


@click.group()
def cli() -> None:
    """Prepare local audio files for later processing."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
def scan(path: Path) -> None:
    """Recursively list audio files under PATH."""
    if not path.exists():
        raise click.ClickException(f"Path does not exist: {path}")
    if not path.is_dir():
        raise click.ClickException(f"Not a directory: {path}")

    for audio_file in iter_audio_files(path):
        click.echo(str(audio_file))
