# Integration QA results

Date: 2026-09-12 (Europe/London)

Commands: `/usr/bin/time -p python3 test_integration.py` and `python3 -m unittest -v test_pipeline.py`

## Passing checks

- Real local transcription of `.runtime/sample.mp4` / `.runtime/sample.wav` with `large-v3-turbo-q5_0` completed in `18.35 s` wall time for the full integration run (including the >300 s exercise).
- Sample duration: `71.36 s`; transcription returned `11` shorter segments.
- Local analysis mode returned `7` labelled heuristic candidates without an API key.
- Two approved contiguous ranges (`2–32 s`, `40–70 s`) rendered successfully.
- Export measured `60.046406 s` and `854x480`, within the intended duration tolerance. A persistent `.data/qa-export.mp4` also passed `ffmpeg -v error -i ... -f null -` audio/video decode.
- The >300 s test measured `356.846406 s` and returned `54` ordered, non-overlapping segments after the backend's version-2 checkpoint/non-overlap chunk change.

## Resolved boundary issue and remaining limits

The backend now uses non-overlapping 300-second chunks and version-2 checkpoints, so the >300-second ordering test passes. Full Whisper JSON preserves token-derived word spans and range edges snap to those spans when available. A sentence may still straddle a 300-second boundary; DTW alignment is not enabled because this turbo build rejects the large-v3 preset.

Historical snapshot: all 10 unit and HTTP tests passed (`python3 -m unittest -v test_pipeline test_analysis test_server`), including mocked analysis coverage, score calculation, montage ranges, audit rejection, call-budget limits, mode isolation and checkpoint resume. Mocked API responses test our logic; they do not prove live model quality. Cloud analysis was untested in that snapshot because `OPENAI_API_KEY` was intentionally blank. The real 100 GB input path and arbitrary container/codec matrix remain untested. No unrelated stored credentials were searched.

## Current verification

The current suite contains 24 unit and HTTP tests across `test_pipeline`, `test_analysis`, and `test_server`; the local run passed. The server tests use ephemeral ports. The real-video evidence remains the completed third live run in `.data/real-video-test/RESULTS.md`: three suggestions, one clean 90-second 480p export, two suggestions needing trim, and uncalibrated scores. No new paid API calls were made for this documentation update.

## Browser verification

`node test_ui.cjs` passed against a newly created job: 11 transcript segments with word spans, 7 local candidates, one completed export and a 321580-byte MP4 download. Desktop and mobile screenshots were captured. The HTTP tests also cover malformed JSON, foreign-origin rejection, byte ranges and path traversal. Analysis tests cover prompt version propagation, cache reuse, token-to-word parsing, and word-edge fallback.
