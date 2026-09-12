import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline


class ProvenanceChecks(unittest.TestCase):
    def test_checkpoint_rejects_changed_source_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / "source.mp4"; model = root / "model.bin"; checkpoint = root / "checkpoint.json"
            source.write_bytes(b"source-v1"); model.write_bytes(b"model")
            source_meta = pipeline.file_identity(source)
            checkpoint.write_text(json.dumps({"schema_version": 2, "complete": False, "next_start": 0, "raw_chunks": [], "source_identity": source_meta, "whisper_identity": pipeline.file_identity(model)}))
            source.write_bytes(b"source-v2"); os.utime(source, (source.stat().st_atime, source.stat().st_mtime + 1))
            with patch.object(pipeline, "MODEL", model), patch.object(pipeline, "tool_ok", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "source changed"):
                    pipeline.transcribe(str(source), 1, checkpoint, source_meta=pipeline.file_identity(source), whisper_meta=pipeline.file_identity(model))

    def test_reasoning_effort_changes_analysis_cache_key(self):
        segments = [{"start": 0, "end": 1, "text": "A"}]
        with patch.dict(os.environ, {"OPENAI_REASONING_EFFORT": "low"}):
            low = pipeline.analysis_cache_path(segments, "general", 1, 10)
        with patch.dict(os.environ, {"OPENAI_REASONING_EFFORT": "medium"}):
            medium = pipeline.analysis_cache_path(segments, "general", 1, 10)
        self.assertNotEqual(low, medium)

    def test_analysis_cancellation_stops_before_next_batch(self):
        segments = [{"start": float(i), "end": float(i + 1), "text": f"segment {i}."} for i in range(160)]
        calls = []
        def fake_openai(prompt, schema):
            calls.append(prompt)
            start = 80 if len(calls) == 2 else 0
            return {"clips": [{"ranges": [{"start_id": start, "end_id": start + 2}], "title": "A stable clip", "reason": "supported", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 3, "coherence": 4}, "risks": []}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch.object(pipeline, "_openai_json", side_effect=fake_openai):
            with self.assertRaises(pipeline.CancelledError):
                pipeline.analyze(segments, "general", 2, 20, "live", should_cancel=lambda: len(calls) > 0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
