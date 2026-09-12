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

### Loop 8 — keep the editing state singular

**Observed:** The dark redesign kept `Select to edit.` visible above an open editor, making one action look like two competing states.

**Changed:** The hint now disappears while the editor is open.

**Verified:** Browser check confirms the hint is hidden, candidate playback starts, and the dark editor remains legible.

### Loop 9 — preserve the editor’s intent

**Observed:** Playback could run past a selected range, async job responses could arrive out of order, and manual trims could disappear when the editor switched context.

**Changed:** Candidate preview now uses the full selected sequence and stops at its end. Job polling, selection, new-run, delete, clear, and export responses are guarded against stale state. Manual ranges persist locally per job and candidate and restore after refresh.

**Verified:** The browser flow passes with a real 480p export; 32 Python tests and JavaScript regression checks pass.

### Loop 10 — protect provenance

**Observed:** A checkpoint could be reused after the source file or Whisper model changed, and reasoning-effort changes could reuse a low-effort analysis cache.

**Changed:** Jobs and checkpoints now record source identity, Whisper identity, and reasoning effort. Changed inputs are rejected with a fresh-job message; cache keys include the active reasoning configuration.

**Verified:** Provenance tests pass, including changed-source rejection and cache-key separation.

### Loop 11 — make async editing safe

**Observed:** A delayed job action could restore an old selection; an open editor could survive a job switch; invalid manual ranges could reach playback.

**Changed:** Retry, Stop, Another take, export, and job selection now guard against stale responses. Transitions close the editor and stop playback. Preview, sequence playback, and export share range validation and playback snapshots.

**Verified:** Browser smoke passes with candidate playback, editor close cleanup, and a real 480p export.

### Loop 12 — compare the whole candidate pool

**Observed:** Per-batch model scores were being treated as globally comparable, so early truncation could hide a stronger moment from a later batch.

**Changed:** Live analysis now sends the complete validated candidate pool through one strict-ID ranking pass before context audit. Ranking evidence is deduplicated and capped per candidate to keep long interviews within a bounded prompt. Final clips retain the separate `ranking_score` alongside the audited rubric score. Metrics record pre-rank count, batch counts, and empty-result reason.

**Verified:** Cross-batch ranking tests pass; 36 Python tests pass.

### Loop 13 — stop paid work when the editor stops

**Observed:** Stop could cancel transcription/export but editorial network calls continued through the remaining analysis stages.

**Changed:** `analyze()` checks the job cancellation event before each batch, ranking pass, and audit call. A stopped job exits through the existing checkpoint-safe cancellation path.

**Verified:** Cancellation regression prevents later model calls; full real-media integration remains green.

### Loop 14 — measure repeatability honestly

**Observed:** The existing score variance metric described one run, not run-to-run stability.

**Changed:** Kept the metric scoped to one run and measured the local fixture five times separately rather than presenting it as live model calibration.

**Evidence:** 5/5 local runs returned 7 candidates with 7/7 range overlap. Live uncached variance still requires a controlled API-backed evaluation with a fixed prompt/model budget.

### Loop 15 — apply the taste pass

**Reading:** Product workspace for editors, with a Steven.com editorial language and restrained motion.

**Changed:** Removed em-dash punctuation from visible UI copy, keeping the dark palette, single accent, compact labels, and restrained hierarchy consistent across the source, review, and output surfaces.

**Verified:** Intro, hero-motion, browser smoke, and 36 Python tests pass. The refreshed local preview is open at `http://127.0.0.1:8765/`.
