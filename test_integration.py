"""Small real-media smoke test; run from clip-assistant with python3."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pipeline


ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / ".runtime" / "sample.mp4"


def probe_media(path: Path) -> tuple[float, int, int]:
    raw = subprocess.run(
        [pipeline.FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=width,height",
         "-of", "json", str(path)], check=True, capture_output=True, text=True
    )
    data = json.loads(raw.stdout)
    stream = next(s for s in data["streams"] if "width" in s)
    return float(data["format"]["duration"]), int(stream["width"]), int(stream["height"])


def main() -> None:
    assert SAMPLE.is_file(), "run scripts/make_sample.sh first"
    source_duration = pipeline.probe(str(SAMPLE))["duration"]
    assert 60 <= source_duration <= 100, source_duration
    with tempfile.TemporaryDirectory(prefix="clip-integration-") as td:
        temp = Path(td)
        checkpoint = temp / "transcription.json"
        segments = pipeline.transcribe(str(SAMPLE), source_duration, checkpoint)
        assert segments and checkpoint.is_file()
        assert all(0 <= s["start"] < s["end"] <= source_duration + .01 for s in segments)
        assert segments == sorted(segments, key=lambda s: (s["start"], s["end"]))
        keys = [(round(s["start"] * 10), " ".join(s["text"].lower().split())) for s in segments]
        assert len(keys) == len(set(keys)), "duplicate stitched segments"

        candidates = pipeline.analyze(segments, "interview viewers", 30, 90, "local")
        assert candidates and all(c["score"] is None and not c["approved"] for c in candidates)
        assert all(c["ranges"][0]["end"] - c["ranges"][0]["start"] >= 30 for c in candidates)

        output = temp / "merged-rough-cut.mp4"
        ranges = [{"start": 2, "end": 32}, {"start": 40, "end": 70}]
        pipeline.render(str(SAMPLE), output, ranges)
        duration, width, height = probe_media(output)
        assert abs(duration - 60) <= .2, duration
        assert height == 480 and width == 854, (width, height)
        # Exercise the 300 s chunk boundary with five local copies (>310 s).
        concat = temp / "concat.txt"
        concat.write_text("\n".join(f"file '{SAMPLE}'" for _ in range(5)))
        long_source = temp / "long.mp4"
        subprocess.run([pipeline.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(long_source)], check=True, capture_output=True)
        long_duration = pipeline.probe(str(long_source))["duration"]
        long_segments = pipeline.transcribe(str(long_source), long_duration, temp / "long-checkpoint.json")
        assert long_duration > 310
        assert all(long_segments[i]["end"] <= long_segments[i + 1]["start"] + .05 for i in range(len(long_segments) - 1)), "overlapping stitched segments at chunk boundary"
        print(json.dumps({"sample_duration": source_duration, "segments": len(segments),
                          "candidate_count": len(candidates), "export_duration": duration,
                          "export_resolution": [width, height], "ranges": ranges,
                          "long_duration": long_duration, "long_segments": len(long_segments)}))


if __name__ == "__main__":
    main()
