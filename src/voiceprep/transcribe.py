"""M2: batch speech-to-text with local openai-whisper (no cloud, no paid API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import click

from ._inputs import collect_audio
from .store import StoreError, load, record_for_path, save, upsert

FORMATS = ("srt", "txt", "json")
# CLI default only; final demo model (tiny vs base) is pending local testing.
DEFAULT_MODEL = "tiny"


class WhisperMissingError(click.ClickException):
    def __init__(self) -> None:
        super().__init__(
            "openai-whisper is not installed. Install it with: "
            "pip install \"voiceprep[whisper]\"  (FFmpeg must also be on PATH)"
        )


def load_model(name: str) -> Any:
    """Lazily import whisper and load the model once."""
    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise WhisperMissingError() from exc
    return whisper.load_model(name)


def format_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp HH:MM:SS,mmm."""
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: list[dict]) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        blocks.append(
            f"{i}\n{format_timestamp(seg['start'])} --> "
            f"{format_timestamp(seg['end'])}\n{seg['text'].strip()}\n"
        )
    return "\n".join(blocks)


def output_paths(audio: Path, out_dir: Path, formats: list[str],
                 stem: Path | None = None) -> dict[str, Path]:
    """Outputs mirror the input's relative path: out_dir/sub/a.srt for dir/sub/a.wav."""
    base = out_dir / (stem if stem is not None else Path(audio.stem))
    return {fmt: base.parent / f"{base.name}.{fmt}" for fmt in formats}


def write_outputs(result: dict, paths: dict[str, Path]) -> None:
    for fmt, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "srt":
            content = to_srt(result.get("segments", []))
        elif fmt == "txt":
            content = result.get("text", "").strip() + "\n"
        else:
            content = json.dumps(result, ensure_ascii=False, indent=2)
        path.write_text(content, encoding="utf-8")


def transcribe_files(
    files: list[Path],
    out_dir: Path,
    *,
    model_name: str = DEFAULT_MODEL,
    language: str | None = None,
    formats: list[str] = list(FORMATS),
    force: bool = False,
    model_loader: Callable[[str], Any] = load_model,
    on_done: Callable[[Path, dict[str, Path], dict], None] | None = None,
    on_fail: Callable[[Path, Exception], None] | None = None,
    stems: dict[Path, Path] | None = None,
) -> dict[str, list[Path]]:
    """Transcribe files; skip ones whose outputs all exist unless force.

    `on_done(file, paths, result)` / `on_fail(file, exc)` are the store.py hooks.
    A failing file is reported and the batch continues.
    """
    report: dict[str, list[Path]] = {"done": [], "skipped": [], "failed": []}
    todo = []
    for f in files:
        paths = output_paths(f, out_dir, formats, (stems or {}).get(f))
        if not force and all(p.exists() for p in paths.values()):
            report["skipped"].append(f)
        else:
            todo.append((f, paths))
    if not todo:
        return report
    model = model_loader(model_name)  # loaded once for the whole batch
    for f, paths in todo:
        kwargs = {"language": language} if language else {}
        try:
            result = model.transcribe(str(f), **kwargs)
            write_outputs(result, paths)
        except Exception as exc:  # keep the batch going; record the failure
            report["failed"].append(f)
            if on_fail:
                on_fail(f, exc)
            continue
        report["done"].append(f)
        if on_done:
            on_done(f, paths, result)
    return report


def _parse_formats(value: str) -> list[str]:
    fmts = [v.strip().lower() for v in value.split(",") if v.strip()]
    bad = [v for v in fmts if v not in FORMATS]
    if bad or not fmts:
        raise click.BadParameter(f"choose from {','.join(FORMATS)}; got {value!r}")
    return fmts


@click.command("transcribe")
@click.argument("paths", nargs=-1, required=True, type=click.Path(path_type=Path))
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("transcripts"),
              show_default=True, help="Directory for srt/txt/json outputs.")
@click.option("--model", "model_name", default=DEFAULT_MODEL, show_default=True,
              help="Whisper model (tiny, base, small, ...). Default not final; pending local test.")
@click.option("--lang", default=None, help="Language code, e.g. zh. Auto-detect if omitted.")
@click.option("--formats", default="srt,txt,json", show_default=True,
              help="Comma-separated output formats.")
@click.option("--force", is_flag=True, help="Re-transcribe even if outputs exist.")
@click.option("--db", "db_path", type=click.Path(path_type=Path), default=None,
              help="voiceprep database to update with transcript fields (only written when given).")
def transcribe_cmd(paths, out_dir, model_name, lang, formats, force, db_path) -> None:
    """Transcribe audio files locally with Whisper (resumable)."""
    fmts = _parse_formats(formats)
    stems = collect_audio(paths)
    if not stems:
        raise click.ClickException("No audio files found.")
    on_done = on_fail = None
    if db_path is not None:
        try:
            db = load(db_path)
        except StoreError as exc:
            raise click.ClickException(str(exc)) from exc
        adapter = StoreAdapter(db, db_path, model_name, lang)
        on_done, on_fail = adapter.done, adapter.failed
    report = transcribe_files(list(stems), out_dir, model_name=model_name,
                              language=lang, formats=fmts, force=force,
                              on_done=on_done, on_fail=on_fail, stems=stems)
    for key, label in (("skipped", "skip"), ("done", "done"), ("failed", "FAIL")):
        for f in report[key]:
            click.echo(f"{label}  {f}")
    click.echo(f"{len(report['done'])} transcribed, {len(report['skipped'])} skipped, "
               f"{len(report['failed'])} failed")
    if report["failed"]:
        raise SystemExit(1)


class StoreAdapter:
    """Write transcript results into the frozen store schema via upsert + atomic save."""

    def __init__(self, db: dict, db_path: Path, model: str, language: str | None) -> None:
        self.db, self.db_path, self.model, self.language = db, db_path, model, language

    def _write(self, audio: Path, transcript: dict) -> None:
        try:
            fresh = record_for_path(audio)
            existing = self.db["files"].get(fresh["id"], {})
            record = {**fresh, **existing, "path": fresh["path"]}
            record["transcript"] = {**record.get("transcript", {}), **transcript}
            upsert(self.db, record)
            save(self.db, self.db_path)  # saved per file so an interrupted batch keeps progress
        except StoreError as exc:
            raise click.ClickException(str(exc)) from exc

    def done(self, audio: Path, paths: dict[str, Path], result: dict) -> None:
        self._write(audio, {
            "status": "completed",
            "text": (result.get("text") or "").strip() or None,
            "outputs": {fmt: str(p.resolve()) for fmt, p in paths.items()},
            "model": self.model,
            "language": self.language or result.get("language"),
            "error": None,
        })

    def failed(self, audio: Path, exc: Exception) -> None:
        self._write(audio, {"status": "failed", "model": self.model,
                            "language": self.language, "error": str(exc)})


def register(root: click.Group) -> None:
    root.add_command(transcribe_cmd)
