"""M3: normalize audio to 16 kHz mono PCM WAV via a local FFmpeg binary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click

from ._inputs import collect_audio


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise click.ClickException(
            "ffmpeg not found on PATH. Install FFmpeg (https://ffmpeg.org/download.html)."
        )
    return exe


def build_ffmpeg_args(ffmpeg: str, src: Path, dst: Path, sr: int = 16000,
                      mono: bool = True) -> list[str]:
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n", "-i", str(src),
            "-vn", "-ar", str(sr)]
    if mono:
        args += ["-ac", "1"]
    args += ["-c:a", "pcm_s16le", str(dst)]
    return args


def target_path(src: Path, out_dir: Path, stem: Path | None = None) -> Path:
    """out_dir/sub/a.wav for dir/sub/a.mp3 (mirrors the input's relative path)."""
    base = out_dir / (stem if stem is not None else Path(src.stem))
    return base.parent / f"{base.name}.wav"


def convert_files(files: list[Path], out_dir: Path, *, sr: int = 16000,
                  mono: bool = True, force: bool = False,
                  runner=subprocess.run,
                  stems: dict[Path, Path] | None = None) -> dict[str, list[Path]]:
    ffmpeg = find_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, list[Path]] = {"done": [], "skipped": [], "failed": []}
    for src in files:
        dst = target_path(src, out_dir, (stems or {}).get(src))
        if dst.resolve() == src.resolve():
            raise click.ClickException(f"Refusing to overwrite original: {src}")
        if dst.exists():
            if not force:
                report["skipped"].append(src)
                continue
            dst.unlink()
        dst.parent.mkdir(parents=True, exist_ok=True)
        proc = runner(build_ffmpeg_args(ffmpeg, src, dst, sr, mono),
                      capture_output=True, text=True)
        (report["done"] if proc.returncode == 0 else report["failed"]).append(src)
    return report


@click.command("convert")
@click.argument("paths", nargs=-1, required=True, type=click.Path(path_type=Path))
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("converted"),
              show_default=True, help="Separate output directory; originals untouched.")
@click.option("--sr", default=16000, show_default=True, type=int, help="Sample rate (Hz).")
@click.option("--mono/--no-mono", default=True, show_default=True, help="Downmix to mono.")
@click.option("--force", is_flag=True, help="Overwrite existing converted outputs.")
def convert_cmd(paths, out_dir, sr, mono, force) -> None:
    """Convert audio to PCM WAV (default 16 kHz mono) with FFmpeg."""
    stems = collect_audio(paths)
    if not stems:
        raise click.ClickException("No audio files found.")
    report = convert_files(list(stems), out_dir, sr=sr, mono=mono, force=force, stems=stems)
    for key in ("skipped", "done", "failed"):
        for f in report[key]:
            click.echo(f"{key:7} {f}")
    click.echo(f"{len(report['done'])} converted, {len(report['skipped'])} skipped, "
               f"{len(report['failed'])} failed")
    if report["failed"]:
        raise SystemExit(1)


def register(root: click.Group) -> None:
    root.add_command(convert_cmd)
