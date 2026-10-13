from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class StoreError(ValueError):
    """Raised when a voiceprep database cannot be read or validated."""


def empty_db() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "files": {}}


def _default_transcript() -> dict[str, Any]:
    return {
        "status": "pending",
        "text": None,
        "outputs": {},
        "model": None,
        "language": None,
        "error": None,
    }


def _normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise StoreError("Each file record must be a JSON object.")

    normalised = deepcopy(record)
    record_id = normalised.get("id")
    if not isinstance(record_id, str) or not _ID_PATTERN.fullmatch(record_id):
        raise StoreError("Record id must be 'sha256:' followed by 64 lowercase hex digits.")

    path = normalised.get("path")
    if not isinstance(path, str) or not path.strip():
        raise StoreError(f"Record {record_id} has no valid path.")
    normalised["path"] = str(Path(path).expanduser().resolve())

    for field in ("duration", "sample_rate", "channels"):
        normalised.setdefault(field, None)

    tags = normalised.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise StoreError(f"Record {record_id} tags must be a list of strings.")
    normalised["tags"] = sorted(
        {tag.strip().casefold() for tag in tags if tag.strip()}
    )

    transcript = normalised.get("transcript")
    if transcript is None:
        transcript = {}
    if not isinstance(transcript, dict):
        raise StoreError(f"Record {record_id} transcript must be a JSON object.")
    merged_transcript = _default_transcript()
    merged_transcript.update(deepcopy(transcript))
    if not isinstance(merged_transcript.get("outputs"), dict):
        raise StoreError(f"Record {record_id} transcript outputs must be a JSON object.")
    normalised["transcript"] = merged_transcript
    return normalised


def _normalise_db(db: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(db, dict):
        raise StoreError("Database root must be a JSON object.")
    if db.get("version") != SCHEMA_VERSION:
        raise StoreError(f"Unsupported database version: {db.get('version')!r}.")

    files = db.get("files")
    if not isinstance(files, dict):
        raise StoreError("Database 'files' must be a JSON object keyed by record id.")

    normalised = deepcopy(db)
    normalised_files: dict[str, dict[str, Any]] = {}
    for key, record in files.items():
        item = _normalise_record(record)
        if key != item["id"]:
            raise StoreError(f"Record key {key!r} does not match id {item['id']!r}.")
        normalised_files[key] = item
    normalised["files"] = normalised_files
    return normalised


def load(path: str | Path) -> dict[str, Any]:
    """Load and validate a database, or return a new one when PATH is absent."""
    db_path = Path(path).expanduser()
    if not db_path.exists():
        return empty_db()
    if not db_path.is_file():
        raise StoreError(f"Database path is not a file: {db_path}")

    try:
        with db_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StoreError(f"Could not read database {db_path}: {exc}") from exc
    return _normalise_db(raw)


def save(db: dict[str, Any], path: str | Path) -> None:
    """Atomically validate and save DB beside its destination."""
    normalised = _normalise_db(db)
    db_path = Path(path).expanduser()
    parent = db_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StoreError(f"Could not create database directory {parent}: {exc}") from exc

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{db_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(normalised, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, db_path)
    except OSError as exc:
        raise StoreError(f"Could not save database {db_path}: {exc}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def upsert(db: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace RECORD in DB and return the stored normalised record."""
    if not isinstance(db, dict) or db.get("version") != SCHEMA_VERSION:
        raise StoreError("Database must use voiceprep schema version 1.")
    files = db.get("files")
    if not isinstance(files, dict):
        raise StoreError("Database 'files' must be a JSON object keyed by record id.")
    normalised = _normalise_record(record)
    files[normalised["id"]] = normalised
    return normalised


def sha256_id(path: str | Path) -> str:
    """Return a stable content id without loading the entire file into memory."""
    digest = hashlib.sha256()
    file_path = Path(path)
    try:
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise StoreError(f"Could not hash audio file {file_path}: {exc}") from exc
    return f"sha256:{digest.hexdigest()}"


def record_for_path(path: str | Path) -> dict[str, Any]:
    """Build the shared minimal record for an audio file."""
    resolved = Path(path).expanduser().resolve()
    return {
        "id": sha256_id(resolved),
        "path": str(resolved),
        "duration": None,
        "sample_rate": None,
        "channels": None,
        "tags": [],
        "transcript": _default_transcript(),
    }
