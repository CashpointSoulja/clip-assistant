# Clip Assistant build log

## 12 September 2026

### Loop 1 — remove ambiguity

**Observed:** Local candidates all used the same `Provisional highlight` label, had no useful range context, and the saved-job selector was flooded by repeated test runs.

**Changed:** Candidate titles now come from the selected transcript passage when local mode has no model title. Cards show the exact time range and `Local · no ranking`. Identical source/settings runs are grouped in the selector and the newest run is shown first.

### Loop 2 — reduce waiting and scanning

**Observed:** A long transcription only said `transcribing`, and mobile users had to pass the entire transcript before reaching candidates.

**Changed:** The pipeline reports `transcribing chunk N of M`; the UI uses `Review ready` and `Export ready` states, keeps `Local ready` visible on mobile, keeps the selected editor in normal flow on desktop, and places candidates before the full transcript on mobile.

### Verification

- 21 Python unit and HTTP tests pass locally and on GitHub Actions.
- Browser fixture flow passes: 7 candidates, one approved 480p export, and a downloaded MP4.
- Mobile browser check confirms candidate cards precede the transcript, show ranges, and never render the generic `Highlight` fallback.
- Public repository scan confirms ignored secrets, local models, generated jobs, and Blender backup files are absent.

## Production boundary

This is production-ready as a local-first editor workstation pilot. It intentionally does not claim SaaS production readiness: authentication, multi-user persistence, deployment, arbitrary 100 GB codec coverage, and observed producer adoption still need real operational evidence. The next loop is two producer sessions using real interviews, measuring time returned, verification rate, rework, export success, and repeat use before expanding the system.

### Loop 3 — make the signal repeatable

**Observed:** Live analysis had no replay boundary, the installed turbo model was unused, and cuts only knew segment edges.

**Changed:** Added `PROMPT_VERSION`, a local cache keyed by transcript/settings/model/prompt version, stable tie ordering, and cache metrics. The runtime now defaults to `large-v3-turbo-q5_0` with `base.en` fallback, requests full Whisper JSON at temperature zero, preserves token-derived word spans, and snaps candidate/export ranges to those word edges when available.

**Verified:** Same-input live analysis reuses the cached result without another model call; 24 Python tests pass; the actual turbo model produced 11 segments with word spans; the >5-minute integration run and 480p export pass.

### Loop 4 — raise the transcript floor

**Observed:** The stronger `large-v3-turbo-q5_0` model was present on the Mac but not selected, and segment-only timing left cuts several seconds wide.

**Changed:** Fresh setup now downloads turbo with a documented `base.en` fallback. Full Whisper JSON is parsed into word spans, deterministic temperature-zero decoding is used, and candidate/export ranges snap to word edges when the spans are available. DTW remains disabled because the installed turbo build rejects the `large.v3` alignment preset.

**Verified:** Turbo transcription produced 11 segments with word spans; the integration run completed in 18.35 seconds with a valid 854×480 export; 24 tests pass.

### Loop 5 — make selection tangible

**Observed:** Selecting a candidate opened its controls but left the playhead unchanged, and the sticky editor let the candidate list show through.

**Changed:** Candidate selection now previews the first range immediately. The editor uses a solid surface in normal flow so the selected state remains legible without overlap.

**Verified:** Browser regression confirms playback starts inside the selected range and the editor is opaque; GitHub Actions passes on commit `6a0a930`.

### Loop 6 — make the workstation reversible

**Observed:** Finished jobs and exports could only accumulate, long runs could not be stopped, and Whisper punctuation was being used as a false score penalty.

**Changed:** Added per-job and bulk deletion that preserves source videos, cooperative cancellation with checkpoint resume, a truthful restart message, free-space guards before transcribe/export, visible cache state, and automatic prompt-version hashing. Boundary punctuation now remains a review warning without changing editorial scores.

**Verified:** 29 Python tests pass, including delete/source preservation, cancel/retry, disk guard, score stability, and checkpoint behavior. Browser checks cover the new playback/editor interactions; GitHub Actions remains the final gate.

### Loop 7 — keep exploration open

**Changed:** Added an explicit `Another take` path for live jobs. It bypasses the canonical analysis cache, records the bypass metric, and leaves the first cached result intact for comparison.

**Verified:** Cache-bypass regression passes without replacing the canonical cached answer; the local cancellation/delete smoke test leaves the source video untouched.
