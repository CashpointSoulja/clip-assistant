# Clip Assistant build log

## 12 September 2026

### Loop 1 — remove ambiguity

**Observed:** Local candidates all used the same `Provisional highlight` label, had no useful range context, and the saved-job selector was flooded by repeated test runs.

**Changed:** Candidate titles now come from the selected transcript passage when local mode has no model title. Cards show the exact time range and `Local · no ranking`. Identical source/settings runs are grouped in the selector and the newest run is shown first.

### Loop 2 — reduce waiting and scanning

**Observed:** A long transcription only said `transcribing`, and mobile users had to pass the entire transcript before reaching candidates.

**Changed:** The pipeline reports `transcribing chunk N of M`; the UI uses `Review ready` and `Export ready` states, keeps `Local ready` visible on mobile, makes the selected editor sticky on desktop, and places candidates before the full transcript on mobile.

### Verification

- 21 Python unit and HTTP tests pass locally and on GitHub Actions.
- Browser fixture flow passes: 7 candidates, one approved 480p export, and a downloaded MP4.
- Mobile browser check confirms candidate cards precede the transcript, show ranges, and never render the generic `Highlight` fallback.
- Public repository scan confirms ignored secrets, local models, generated jobs, and Blender backup files are absent.

## Production boundary

This is production-ready as a local-first editor workstation pilot. It intentionally does not claim SaaS production readiness: authentication, multi-user persistence, deployment, arbitrary 100 GB codec coverage, and observed producer adoption still need real operational evidence. The next loop is two producer sessions using real interviews, measuring time returned, verification rate, rework, export success, and repeat use before expanding the system.
