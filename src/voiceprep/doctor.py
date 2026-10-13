from __future__ import annotations

import importlib.util
import shutil
import sys

import click


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


@click.command("doctor")
@click.option("--strict", is_flag=True, help="Fail when an optional dependency is missing.")
def doctor_command(strict: bool) -> None:
    """Report local Python, Whisper, and FFmpeg availability."""
    python_ok = sys.version_info >= (3, 10)
    click.echo(
        f"python: {'ok' if python_ok else 'unsupported'} "
        f"({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})"
    )

    optional = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "whisper": "installed" if _module_available("whisper") else None,
    }
    for name, location in optional.items():
        click.echo(f"{name}: {location or 'missing (optional)'}")

    if not python_ok:
        raise click.ClickException("Python 3.10 or newer is required.")
    missing = [name for name, location in optional.items() if location is None]
    if strict and missing:
        raise click.ClickException(f"Missing optional dependencies: {', '.join(missing)}")


def register(root: click.Group) -> None:
    root.add_command(doctor_command)
