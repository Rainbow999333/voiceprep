import json
from pathlib import Path
from unittest.mock import patch

import pytest

from voiceprep.store import StoreError, empty_db, load, record_for_path, save, upsert


def test_store_round_trip_preserves_extension_fields(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"audio")
    record = record_for_path(audio)
    record["tags"] = [" Calm ", "calm", "FEMALE"]
    record["future_field"] = {"keep": True}
    db = empty_db()

    stored = upsert(db, record)
    db_path = tmp_path / "data" / "voiceprep.json"
    save(db, db_path)
    loaded = load(db_path)

    assert stored["tags"] == ["calm", "female"]
    assert loaded["files"][record["id"]]["future_field"] == {"keep": True}
    assert loaded["files"][record["id"]]["transcript"]["status"] == "pending"
    assert not list(db_path.parent.glob(".voiceprep.json.*.tmp"))


def test_load_missing_returns_new_database(tmp_path: Path) -> None:
    assert load(tmp_path / "missing.json") == {"version": 1, "files": {}}


def test_invalid_json_is_not_overwritten(tmp_path: Path) -> None:
    db_path = tmp_path / "voiceprep.json"
    db_path.write_text("not json", encoding="utf-8")

    with pytest.raises(StoreError, match="Could not read database"):
        load(db_path)

    assert db_path.read_text(encoding="utf-8") == "not json"


def test_save_writes_valid_utf8_json(tmp_path: Path) -> None:
    audio = tmp_path / "声音.wav"
    audio.write_bytes(b"voice")
    db = empty_db()
    upsert(db, record_for_path(audio))
    db_path = tmp_path / "voiceprep.json"

    save(db, db_path)

    raw = json.loads(db_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert next(iter(raw["files"].values()))["path"].endswith("声音.wav")


def test_failed_replace_preserves_previous_database(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    db_path = tmp_path / "voiceprep.json"
    original = empty_db()
    upsert(original, record_for_path(first))
    save(original, db_path)

    changed = load(db_path)
    upsert(changed, record_for_path(second))
    with patch("voiceprep.store.os.replace", side_effect=OSError("simulated interruption")):
        with pytest.raises(StoreError, match="Could not save database"):
            save(changed, db_path)

    reloaded = load(db_path)
    assert list(reloaded["files"]) == list(original["files"])
    assert not list(tmp_path.glob(".voiceprep.json.*.tmp"))
