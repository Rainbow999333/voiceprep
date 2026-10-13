from unittest.mock import patch

from click.testing import CliRunner

from voiceprep.cli import cli


def test_doctor_reports_optional_dependencies_without_failing() -> None:
    with patch("voiceprep.doctor.shutil.which", return_value=None), patch(
        "voiceprep.doctor._module_available", return_value=False
    ):
        result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "python: ok" in result.output
    assert "ffmpeg: missing (optional)" in result.output
    assert "ffprobe: missing (optional)" in result.output
    assert "whisper: missing (optional)" in result.output


def test_doctor_strict_fails_when_optional_dependencies_are_missing() -> None:
    with patch("voiceprep.doctor.shutil.which", return_value=None), patch(
        "voiceprep.doctor._module_available", return_value=False
    ):
        result = CliRunner().invoke(cli, ["doctor", "--strict"])

    assert result.exit_code != 0
    assert "Missing optional dependencies" in result.output
