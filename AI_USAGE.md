# AI Usage

This project uses AI assistance openly. The human author owns the project decisions, reviews the work, runs the software, and decides what is accepted and submitted.

## Roles

| Participant | Contribution |
|---|---|
| Tu Hao / Mr.Liang (human author) | Chose the problem and local-first constraints; defined requirements; reviewed and approved the architecture; supplied the original Cursor prompt; ran and captured CLI/test evidence; reviewed PR #2; selected scope and model candidates; authorizes repository operations; will test real audio, approve PR #3, record the demo, and submit the project. |
| Cursor free tier | Generated the initial minimal Click scaffold and scan tests from the human author's prompt. |
| OpenAI Codex / GPT | Reviewed architecture and evidence; implemented M1 storage/tag/export/doctor; merged the approved PR #2 under explicit authorization; reviewed and integrated Grok's M2/M3 patch; implemented follow-up fixes and tests; maintains technical handoff notes. |
| Grok Bot | Researched challenge fit and licenses; drafted the initial architecture and plan; drafted project documentation; reviewed PR #2; generated the M2/M3 patch for local Whisper and FFmpeg workflows, including the v2 patch integrating transcription results with the frozen `store.py` interface. |

The original commits were created by the human author. The public GitHub repository was created, and the first push performed, by Codex with the author's explicit authorization through the author's logged-in `gh` account. Later GitHub and commit operations performed by Codex are done only with the author's explicit authorization through the author's authenticated account. AI-generated code is not treated as accepted until tests pass and the human author reviews the pull request.

## Attribution log

| Commit / PR | Area | Origin | Human involvement |
|---|---|---|---|
| `ec94c8e` | Initial package, Click CLI, scan, and 4 tests | Cursor-generated | Author supplied the prompt, ran the result, captured evidence, and committed it. |
| `7b00606` | `.gitignore` | Codex-assisted | Author reviewed, staged, and committed it. |
| PR #2 | MIT license, JSON store, tag/export/doctor commands, tests | Codex-generated | Author set the frozen interface and scope; Grok reviewed the PR; author approved merge. |
| PR #3 (pending) | Whisper transcription, FFmpeg conversion, integration fixes, docs | Grok-generated patch plus Codex review and changes | Author requested the division of work and will review, test real audio, and approve or reject the PR. |

## Cursor evidence

The private project collaboration center contains screenshots covering:

1. The original prompt and Cursor generation result.
2. `pytest` passing.
3. `voiceprep --help` and `voiceprep scan .` output.
4. A clean working tree. The screenshots do not show the first commit; commit `ec94c8e` is evidenced by the public GitHub history.

Public repository history provides additional evidence for commits, issues, branches, and pull requests. Private screenshots can be attached to the hackathon submission where appropriate.

## Review policy

- Tests use mocks for Whisper and FFmpeg so routine CI does not download model weights or require system binaries.
- The author must perform a real local smoke test before the demo.
- AI suggestions may be changed or rejected when they conflict with the local-only scope, deadline, or safety requirements.
- The demo will use only self-recorded or explicitly licensed audio.

## Honesty statement

We will describe AI involvement truthfully if asked by judges, organizers, maintainers, or users. VoicePrep is an AI-assisted project with substantive human direction, validation, review, and presentation—not a claim of unaided authorship.
