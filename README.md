# voiceprep

Local-first CLI for preparing authorized reference audio for voice and TTS projects. It scans audio, stores tags and metadata in JSON, exports datasets, transcribes locally with Whisper, and converts audio with FFmpeg. Audio is not sent to a paid or hosted API.

Built for MLH Global Hack Week: Open Source, October 9–15, 2026.

## Features

- Recursively scan `.wav`, `.flac`, `.mp3`, `.m4a`, and `.ogg` files.
- Index duration, sample rate, and channel count in an atomically written `voiceprep.json` database.
- Add, remove, and list tags using file, directory, or glob inputs.
- Export all records or filter tags with AND/OR logic; supports paths and GPT-SoVITS `.list` output.
- Transcribe batches locally with `openai-whisper`, write SRT/TXT/JSON, and resume by skipping existing outputs.
- Convert batches to 16 kHz mono PCM WAV without overwriting source audio.
- Check local dependencies with `voiceprep doctor`.

pgvector semantic search is intentionally deferred until the core local workflow and demo are complete.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/Rainbow999333/voiceprep.git
cd voiceprep
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

For local transcription, install the optional Whisper dependency and place FFmpeg on `PATH`:

```bash
python -m pip install -e ".[whisper]"
```

Whisper model weights are downloaded on first use and cached locally. The CLI defaults to `tiny`; the final demo uses `base`, selected after local CPU testing documented below.

## Usage

```bash
voiceprep --help
voiceprep doctor

# List files only; no database side effect
voiceprep scan ./samples

# List and index files plus audio metadata
voiceprep scan ./samples --db voiceprep.json

# Tags are stored by content hash
voiceprep tag add ./samples/narrator calm female --db voiceprep.json
voiceprep tag add "samples/**/*.wav" zh --db voiceprep.json
voiceprep tag remove ./samples/narrator female --db voiceprep.json
voiceprep tag list --db voiceprep.json

# Export every record, or filter by tags
voiceprep export --db voiceprep.json
voiceprep export --tag calm --tag female --db voiceprep.json
voiceprep export --tag calm --tag zh --any --format list --speaker narrator --language zh --output train.list --db voiceprep.json

# Local Whisper; output subdirectories mirror the input tree
voiceprep transcribe ./samples --model tiny --lang zh --formats srt,txt,json --out-dir transcripts --db voiceprep.json

# Local FFmpeg conversion; originals stay untouched
voiceprep convert ./samples --out-dir samples_16k --sr 16000 --mono
```

`transcribe` writes transcript fields to the database only when `--db` is given (like `scan --db`). Known limitation: records are keyed by content hash, so files produced by `convert` become separate records from their originals; transcribe the originals if you want transcripts and tags on the same record.

`transcribe` skips a file when all requested outputs already exist. Use `--force` to run it again. `convert` also skips existing outputs unless `--force` is supplied.

## Data format

The schema is versioned. Records are keyed by a SHA-256 content hash, so tags and transcript state survive a rename when the file is seen again.

```json
{
  "version": 1,
  "files": {
    "sha256:...": {
      "id": "sha256:...",
      "path": "C:/audio/clip01.wav",
      "duration": 4.21,
      "sample_rate": 44100,
      "channels": 2,
      "tags": ["calm", "female"],
      "transcript": {
        "status": "completed",
        "text": "Example transcript",
        "outputs": {"srt": "C:/output/clip01.srt"},
        "model": "tiny",
        "language": "en",
        "error": null
      }
    }
  }
}
```

Database saves use a temporary file and atomic replacement. Transcription saves after each completed or failed item so an interrupted batch keeps its progress.

## Responsible use

VoicePrep prepares data; it does not clone voices. Use only your own voice or audio you are explicitly authorized to process. Do not collect or process another person's voice without consent. Demo audio should be self-recorded or publicly licensed, with its source and license documented.

**Demo audio:** Demo audio was generated locally with the open-source [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Apache-2.0; Hugging Face model cards also list Apache-2.0) using its default built-in voice; no real person's voice was cloned or recorded. The audio file itself is not committed to this repository.

## Local test results

Real (non-mock) runs on the author's Windows machine, CPU only, PR #3 head `944d6b2`:

- `pytest`: 35 passed. `voiceprep doctor --strict`: all dependencies found, exit code 0.
- `scan --db`: wrote real duration, sample rate (48 kHz), and channel count for the author's own recordings.
- `convert`: ffprobe confirmed output `pcm_s16le`, 16000 Hz, 1 channel; a second run skipped existing output.
- `transcribe` resume: a repeated run reported `0 transcribed, 1 skipped, 0 failed`. All TXT/SRT/JSON and database files decoded as strict UTF-8.
- Author's own quiet phone recordings (~6 s and ~9 s, about -37 to -40 dB mean volume): `tiny` produced unusable output (`mmm` on the first clip, many wrong words on the second); `base` was clearly better but still had wrong words. Converting to 16 kHz mono or loudness-normalizing barely changed `base` results, so format conversion was not the cause.
- Final demo clip (Qwen3-TTS, ~20.9 s, 24 kHz mono MP3): `base` recognized all of the content, differing only in Traditional/Simplified characters and omitted punctuation; the SRT has 8 segments. `tiny` had several clear word errors.
- Timing was not formally benchmarked. Whisper's "FP16 is not supported on CPU" warning is a normal fallback to FP32, not an error.
- Windows CMD tip: run `chcp 65001` or use `Get-Content -Encoding utf8` to view UTF-8 output; `type` under code page 936 shows garbled text even though files are correct.

We do not claim high accuracy; the demo proves the local end-to-end workflow.

## Components and licenses

| Component | Role | License | Execution |
|---|---|---|---|
| [Click](https://github.com/pallets/click) | CLI framework | BSD-3-Clause | Local |
| [openai-whisper](https://github.com/openai/whisper) | Optional speech-to-text code and weights | MIT | Local |
| [FFmpeg](https://ffmpeg.org/legal.html) | Separately installed audio tooling | LGPL-2.1-or-later by default; some builds are GPL-2.0-or-later | Local subprocess |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Generated the demo audio only (not a dependency) | Apache-2.0 | Local, run by the author |

This project is licensed under the [MIT License](LICENSE).

## Hackathon evidence

- Initial Click scaffold and `scan` command: generated in Cursor free tier from the author's prompt, commit `ec94c8e`.
- Repository management: public repository, issue #1, feature branches, and milestone pull requests.
- AI collaboration and human participation are documented in [AI_USAGE.md](AI_USAGE.md).

Before submission, the author will verify each selected challenge's current submission page and retain screenshots of the Cursor prompt, generated result, tests, commands, commits, and pull requests.
