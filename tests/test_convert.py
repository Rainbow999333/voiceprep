from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

from voiceprep import convert as cv
from voiceprep.cli import cli


def test_build_args_default():
    args = cv.build_ffmpeg_args("ffmpeg", Path("in.mp3"), Path("o/in.wav"))
    assert args[:1] == ["ffmpeg"] and "-n" in args
    assert args[args.index("-ar") + 1] == "16000"
    assert args[args.index("-ac") + 1] == "1"
    assert args[args.index("-c:a") + 1] == "pcm_s16le"
    assert args[-1] == str(Path("o/in.wav"))


def test_build_args_stereo_custom_sr():
    args = cv.build_ffmpeg_args("ff", Path("a"), Path("b"), sr=22050, mono=False)
    assert "-ac" not in args and "22050" in args


def test_missing_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(cv.shutil, "which", lambda _: None)
    with pytest.raises(click.ClickException, match="ffmpeg not found"):
        cv.find_ffmpeg()
    (tmp_path / "a.wav").write_bytes(b"")
    res = CliRunner().invoke(cli, ["convert", str(tmp_path)])
    assert res.exit_code != 0 and "ffmpeg not found" in res.output


def test_convert_skip_force_and_originals(monkeypatch, tmp_path):
    monkeypatch.setattr(cv.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    src = tmp_path / "in"; src.mkdir()
    a = src / "a.mp3"; a.write_bytes(b"orig")
    out = tmp_path / "out"
    calls = []

    def runner(args, **kw):
        calls.append(args); Path(args[-1]).write_bytes(b"wav")
        return SimpleNamespace(returncode=0)

    r = cv.convert_files([a], out, runner=runner)
    assert r["done"] == [a] and (out / "a.wav").exists()
    assert a.read_bytes() == b"orig"
    assert cv.convert_files([a], out, runner=runner)["skipped"] == [a]
    assert len(calls) == 1
    assert cv.convert_files([a], out, force=True, runner=runner)["done"] == [a]
    assert len(calls) == 2


def test_refuses_overwrite_original(monkeypatch, tmp_path):
    monkeypatch.setattr(cv.shutil, "which", lambda _: "ffmpeg")
    a = tmp_path / "a.wav"; a.write_bytes(b"x")
    with pytest.raises(click.ClickException, match="overwrite original"):
        cv.convert_files([a], tmp_path, runner=lambda *a, **k: None)
    assert a.read_bytes() == b"x"


def test_failed_ffmpeg_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(cv.shutil, "which", lambda _: "ffmpeg")
    a = tmp_path / "a.ogg"; a.write_bytes(b"")
    r = cv.convert_files([a], tmp_path / "o",
                         runner=lambda *x, **k: SimpleNamespace(returncode=1))
    assert r["failed"] == [a]


def test_convert_mirrors_relative_paths(monkeypatch, tmp_path):
    from voiceprep._inputs import collect_audio
    monkeypatch.setattr(cv.shutil, "which", lambda _: "ffmpeg")
    root = tmp_path / "in"
    for sub in ("a", "b"):
        (root / sub).mkdir(parents=True); (root / sub / "v.mp3").write_bytes(b"x")
    stems = collect_audio([root])

    def runner(args, **kw):
        Path(args[-1]).write_bytes(b"wav"); return SimpleNamespace(returncode=0)

    r = cv.convert_files(list(stems), tmp_path / "o", runner=runner, stems=stems)
    assert len(r["done"]) == 2
    assert (tmp_path / "o" / "a" / "v.wav").exists() and (tmp_path / "o" / "b" / "v.wav").exists()
