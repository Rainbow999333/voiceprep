"""Shared helpers for collecting input audio files (M2/M3)."""

from __future__ import annotations

from pathlib import Path

import click

from .scan import AUDIO_EXTENSIONS, iter_audio_files


def collect_audio(paths: tuple[Path, ...] | list[Path]) -> dict[Path, Path]:
    """Expand files/directories into {audio file: relative output stem path}.

    A file inside a directory argument keeps its path relative to that directory
    (``dir/sub/a.wav`` -> ``sub/a``); a file argument maps to its own stem.
    Two inputs that would produce the same output path are rejected so outputs
    never silently overwrite each other.
    """
    found: dict[Path, Path] = {}
    for p in paths:
        if not p.exists():
            raise click.ClickException(f"Path does not exist: {p}")
        if p.is_dir():
            pairs = [(f, f.relative_to(p)) for f in iter_audio_files(p)]
        elif p.suffix.lower() in AUDIO_EXTENSIONS:
            pairs = [(p, Path(p.name))]
        else:
            pairs = []
        for f, rel in pairs:
            found.setdefault(f.resolve(), rel.with_suffix(""))
    owners: dict[Path, Path] = {}
    for f, stem in found.items():
        if stem in owners:
            raise click.ClickException(
                f"Output name collision: {owners[stem]} and {f} both map to '{stem}'. "
                "Rename one file or process them separately."
            )
        owners[stem] = f
    return dict(sorted(found.items()))
