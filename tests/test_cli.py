from pathlib import Path
import wave

from click.testing import CliRunner

from voiceprep.cli import cli
from voiceprep.store import load

AUDIO_NAMES = {
    "clip.wav",
    "song.flac",
    "talk.mp3",
    "note.m4a",
    "ambience.ogg",
}


def test_help_succeeds() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output
    assert "Usage" in result.output


def test_scan_finds_nested_audio(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "deeper"
    nested.mkdir(parents=True)
    expected = []
    for name in AUDIO_NAMES:
        target = nested / name
        target.write_bytes(b"")
        expected.append(target)

    result = CliRunner().invoke(cli, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    found = [Path(line) for line in result.output.splitlines() if line]
    assert found == sorted(expected)


def test_scan_ignores_non_audio_files(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignore me too", encoding="utf-8")
    audio = tmp_path / "keep.wav"
    audio.write_bytes(b"")

    result = CliRunner().invoke(cli, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    found = [Path(line) for line in result.output.splitlines() if line]
    assert found == [audio]


def test_scan_invalid_directory_fails(tmp_path: Path) -> None:
    runner = CliRunner()
    missing = tmp_path / "does-not-exist"
    missing_result = runner.invoke(cli, ["scan", str(missing)])
    assert missing_result.exit_code != 0
    assert "does not exist" in missing_result.output

    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("not a directory", encoding="utf-8")
    file_result = runner.invoke(cli, ["scan", str(not_a_dir)])
    assert file_result.exit_code != 0
    assert "Not a directory" in file_result.output


def test_scan_can_index_wav_metadata(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "tone.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 4000)
    db_path = tmp_path / "voiceprep.json"
    monkeypatch.setattr("voiceprep.scan.shutil.which", lambda _: None)

    result = CliRunner().invoke(
        cli,
        ["scan", str(tmp_path), "--db", str(db_path)],
    )

    assert result.exit_code == 0, result.output
    record = next(iter(load(db_path)["files"].values()))
    assert record["duration"] == 0.5
    assert record["sample_rate"] == 8000
    assert record["channels"] == 1
