from pathlib import Path

from click.testing import CliRunner

from voiceprep.cli import cli

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
