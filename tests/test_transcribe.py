import builtins
import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from voiceprep import transcribe as tr
from voiceprep.cli import cli

RESULT = {"text": " 你好 世界 ", "segments": [
    {"start": 0.0, "end": 1.5, "text": " 你好"},
    {"start": 3661.0, "end": 3662.25, "text": "世界 "}]}


class FakeModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, path, **kw):
        self.calls.append((path, kw))
        return RESULT


def test_format_timestamp():
    assert tr.format_timestamp(0) == "00:00:00,000"
    assert tr.format_timestamp(1.5) == "00:00:01,500"
    assert tr.format_timestamp(3661.25) == "01:01:01,250"


def test_to_srt():
    srt = tr.to_srt(RESULT["segments"])
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,500\n你好\n")
    assert "2\n01:01:01,000 --> 01:01:02,250\n世界\n" in srt


def test_writes_outputs_and_resumes(tmp_path: Path):
    a = tmp_path / "a.wav"; a.write_bytes(b"")
    out = tmp_path / "out"
    model = FakeModel(); loads = []

    def loader(name):
        loads.append(name); return model

    r = tr.transcribe_files([a], out, language="zh", model_loader=loader)
    assert r["done"] == [a] and loads == ["tiny"]
    assert model.calls == [(str(a), {"language": "zh"})]
    assert (out / "a.txt").read_text(encoding="utf-8") == "你好 世界\n"
    assert json.loads((out / "a.json").read_text(encoding="utf-8"))["text"]
    assert (out / "a.srt").exists()

    r2 = tr.transcribe_files([a], out, model_loader=loader)
    assert r2["skipped"] == [a] and loads == ["tiny"]  # model not reloaded
    r3 = tr.transcribe_files([a], out, force=True, model_loader=loader)
    assert r3["done"] == [a]


def test_model_loaded_once_for_batch(tmp_path: Path):
    files = []
    for n in "abc":
        f = tmp_path / f"{n}.wav"; f.write_bytes(b""); files.append(f)
    loads = []
    tr.transcribe_files(files, tmp_path / "o", formats=["txt"],
                        model_loader=lambda n: loads.append(n) or FakeModel())
    assert len(loads) == 1


def test_missing_whisper_error(monkeypatch):
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "whisper":
            raise ImportError
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(tr.WhisperMissingError):
        tr.load_model("tiny")


def test_cli_missing_whisper_message(tmp_path, monkeypatch):
    (tmp_path / "a.wav").write_bytes(b"")

    def boom(name):
        raise tr.WhisperMissingError()

    monkeypatch.setattr(tr, "load_model", boom)
    monkeypatch.setattr(tr.transcribe_files, "__kwdefaults__",
                        {**tr.transcribe_files.__kwdefaults__, "model_loader": boom})
    res = CliRunner().invoke(cli, ["transcribe", str(tmp_path), "--out-dir",
                                   str(tmp_path / "o")])
    assert res.exit_code != 0 and "voiceprep[whisper]" in res.output


def test_cli_bad_format(tmp_path):
    res = CliRunner().invoke(cli, ["transcribe", str(tmp_path), "--formats", "doc"])
    assert res.exit_code != 0


def test_relative_path_naming_and_collision(tmp_path: Path):
    from voiceprep._inputs import collect_audio
    root = tmp_path / "in"
    for sub in ("a", "b"):
        (root / sub).mkdir(parents=True)
        (root / sub / "clip.wav").write_bytes(sub.encode())
    stems = collect_audio([root])
    assert sorted(stems.values()) == [Path("a/clip"), Path("b/clip")]
    out = tmp_path / "out"
    tr.transcribe_files(list(stems), out, formats=["txt"], stems=stems,
                        model_loader=lambda n: FakeModel())
    assert (out / "a" / "clip.txt").exists() and (out / "b" / "clip.txt").exists()

    (root / "a" / "clip.mp3").write_bytes(b"x")
    with pytest.raises(click.ClickException, match="collision"):
        collect_audio([root])


def test_cli_writes_transcript_to_store(tmp_path: Path, monkeypatch):
    from voiceprep.store import load
    audio = tmp_path / "in" / "s1"; audio.mkdir(parents=True)
    (audio / "x.wav").write_bytes(b"x-audio")
    (audio / "bad.wav").write_bytes(b"bad-audio")

    class Model:
        def transcribe(self, path, **kw):
            if path.endswith("bad.wav"):
                raise RuntimeError("decode error")
            return RESULT

    monkeypatch.setattr(tr.transcribe_files, "__kwdefaults__",
                        {**tr.transcribe_files.__kwdefaults__, "model_loader": lambda n: Model()})
    db = tmp_path / "db.json"
    runner = CliRunner()
    # tag first so we can prove transcribe keeps existing fields
    assert runner.invoke(cli, ["tag", "add", str(audio / "x.wav"), "calm", "--db", str(db)]).exit_code == 0
    res = runner.invoke(cli, ["transcribe", str(tmp_path / "in"), "--out-dir", str(tmp_path / "o"),
                              "--formats", "txt,srt", "--lang", "zh", "--db", str(db)])
    assert res.exit_code == 1 and "1 transcribed" in res.output and "1 failed" in res.output
    records = {Path(r["path"]).name: r for r in load(db)["files"].values()}
    ok = records["x.wav"]
    assert ok["tags"] == ["calm"]
    assert ok["transcript"]["status"] == "completed" and ok["transcript"]["text"] == "你好 世界"
    assert ok["transcript"]["language"] == "zh" and ok["transcript"]["model"] == "tiny"
    assert set(ok["transcript"]["outputs"]) == {"txt", "srt"}
    assert Path(ok["transcript"]["outputs"]["txt"]) == (tmp_path / "o" / "s1" / "x.txt").resolve()
    assert records["bad.wav"]["transcript"]["status"] == "failed"
    assert "decode error" in records["bad.wav"]["transcript"]["error"]
    # export --format list now carries the transcript text (M1 <-> M2 integration)
    res = runner.invoke(cli, ["export", "--tag", "calm", "--format", "list", "--db", str(db)])
    assert res.output.strip().endswith("|speaker|auto|你好 世界")


def test_cli_without_db_does_not_write_store(tmp_path: Path, monkeypatch):
    audio = tmp_path / "in"; audio.mkdir()
    (audio / "x.wav").write_bytes(b"x-audio")
    monkeypatch.setattr(tr.transcribe_files, "__kwdefaults__",
                        {**tr.transcribe_files.__kwdefaults__, "model_loader": lambda n: FakeModel()})
    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        res = CliRunner().invoke(cli, ["transcribe", str(audio), "--out-dir", "o", "--formats", "txt"])
        assert res.exit_code == 0 and "1 transcribed" in res.output
        assert not Path("voiceprep.json").exists()
