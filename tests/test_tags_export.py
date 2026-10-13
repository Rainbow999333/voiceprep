from pathlib import Path

from click.testing import CliRunner

from voiceprep.cli import cli
from voiceprep.store import load


def _add(runner: CliRunner, db_path: Path, pattern: Path, *tags: str):
    return runner.invoke(
        cli,
        ["tag", "add", str(pattern), *tags, "--db", str(db_path)],
    )


def test_tag_add_list_remove_and_content_hash_deduplication(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"same audio")
    second.write_bytes(b"same audio")
    db_path = tmp_path / "voiceprep.json"
    runner = CliRunner()

    result = _add(runner, db_path, first, " Calm ", "FEMALE")
    assert result.exit_code == 0, result.output
    result = _add(runner, db_path, second, "studio")
    assert result.exit_code == 0, result.output

    db = load(db_path)
    assert len(db["files"]) == 1
    record = next(iter(db["files"].values()))
    assert record["path"] == str(second.resolve())
    assert record["tags"] == ["calm", "female", "studio"]

    listed = runner.invoke(cli, ["tag", "list", "--db", str(db_path)])
    assert listed.exit_code == 0
    assert listed.output.splitlines() == ["calm\t1", "female\t1", "studio\t1"]

    removed = runner.invoke(
        cli,
        ["tag", "remove", str(second), "female", "--db", str(db_path)],
    )
    assert removed.exit_code == 0, removed.output
    assert next(iter(load(db_path)["files"].values()))["tags"] == ["calm", "studio"]


def test_tag_add_supports_recursive_glob_and_rejects_empty_matches(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "a.wav").write_bytes(b"a")
    (nested / "b.mp3").write_bytes(b"b")
    (nested / "ignore.txt").write_text("x", encoding="utf-8")
    db_path = tmp_path / "voiceprep.json"
    runner = CliRunner()

    result = _add(runner, db_path, tmp_path / "**" / "*", "demo")
    assert result.exit_code == 0, result.output
    assert len(load(db_path)["files"]) == 2

    missing = _add(runner, db_path, tmp_path / "*.flac", "demo")
    assert missing.exit_code != 0
    assert "No supported audio files matched" in missing.output


def test_export_and_or_paths_and_list_format(tmp_path: Path) -> None:
    calm = tmp_path / "calm.wav"
    bright = tmp_path / "bright.wav"
    calm.write_bytes(b"calm")
    bright.write_bytes(b"bright")
    db_path = tmp_path / "voiceprep.json"
    runner = CliRunner()
    assert _add(runner, db_path, calm, "calm", "female").exit_code == 0
    assert _add(runner, db_path, bright, "bright", "female").exit_code == 0

    and_result = runner.invoke(
        cli,
        ["export", "--tag", "calm", "--tag", "female", "--db", str(db_path)],
    )
    assert and_result.exit_code == 0
    assert and_result.output == f"{calm.resolve()}\n"

    any_result = runner.invoke(
        cli,
        ["export", "--tag", "calm", "--tag", "bright", "--any", "--db", str(db_path)],
    )
    assert any_result.exit_code == 0
    assert any_result.output.splitlines() == sorted([str(calm.resolve()), str(bright.resolve())])

    list_result = runner.invoke(
        cli,
        [
            "export",
            "--tag",
            "calm",
            "--format",
            "list",
            "--speaker",
            "narrator",
            "--language",
            "zh",
            "--db",
            str(db_path),
        ],
    )
    assert list_result.exit_code == 0
    assert list_result.output == f"{calm.resolve()}|narrator|zh|\n"


def test_export_writes_output_file(tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"clip")
    db_path = tmp_path / "voiceprep.json"
    output = tmp_path / "exports" / "clips.txt"
    runner = CliRunner()
    assert _add(runner, db_path, audio, "demo").exit_code == 0

    result = runner.invoke(
        cli,
        ["export", "--tag", "demo", "--output", str(output), "--db", str(db_path)],
    )
    assert result.exit_code == 0, result.output
    assert output.read_text(encoding="utf-8") == f"{audio.resolve()}\n"
