from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

import click

from .store import StoreError, load, record_for_path, save, upsert

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg"}


def iter_audio_files(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


def probe_audio(path: Path) -> dict[str, int | float | None]:
    """Read basic audio metadata with ffprobe, falling back to stdlib WAV parsing."""
    metadata: dict[str, int | float | None] = {
        "duration": None,
        "sample_rate": None,
        "channels": None,
    }
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        args = [
            ffprobe,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels:format=duration",
            "-of", "json",
            str(path),
        ]
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                payload: dict[str, Any] = json.loads(result.stdout)
                stream = next(iter(payload.get("streams", [])), {})
                duration = payload.get("format", {}).get("duration")
                metadata.update(
                    duration=float(duration) if duration is not None else None,
                    sample_rate=int(stream["sample_rate"]) if stream.get("sample_rate") else None,
                    channels=int(stream["channels"]) if stream.get("channels") else None,
                )
                return metadata
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav:
                rate = wav.getframerate()
                metadata.update(
                    duration=wav.getnframes() / rate if rate else None,
                    sample_rate=rate,
                    channels=wav.getnchannels(),
                )
        except (OSError, EOFError, wave.Error):
            pass
    return metadata


@click.command("scan")
@click.argument("path", type=click.Path(path_type=Path))
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    help="Also index files and audio metadata in a voiceprep database.",
)
def scan_command(path: Path, db_path: Path | None) -> None:
    """Recursively list audio files under PATH; optionally index them."""
    if not path.exists():
        raise click.ClickException(f"Path does not exist: {path}")
    if not path.is_dir():
        raise click.ClickException(f"Not a directory: {path}")

    files = iter_audio_files(path)
    for audio_file in files:
        click.echo(str(audio_file))

    if db_path is None:
        return
    try:
        db = load(db_path)
        for audio_file in files:
            fresh = record_for_path(audio_file)
            existing = db["files"].get(fresh["id"], {})
            record = {**fresh, **existing, "path": fresh["path"]}
            metadata = probe_audio(audio_file)
            record.update({key: value for key, value in metadata.items() if value is not None})
            upsert(db, record)
        save(db, db_path)
    except StoreError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Indexed {len(files)} file(s) in {db_path}.", err=True)


def register(root: click.Group) -> None:
    root.add_command(scan_command)
