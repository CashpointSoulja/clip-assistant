import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline


def segs(n):
    return [{"start": float(i), "end": float(i + 1), "text": f"segment {i}"} for i in range(n)]


class AnalysisChecks(unittest.TestCase):
    def setUp(self):
        self.cache_dir = tempfile.TemporaryDirectory()
        self.cache_patch = patch.object(pipeline, "ANALYSIS_CACHE", Path(self.cache_dir.name))
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.addCleanup(self.cache_dir.cleanup)

    def _response(self, ids, title="clip"):
        return {"clips": [{"ranges": [{"start_id": ids[0], "end_id": ids[-1]}], "title": title, "reason": "supported editorial angle", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": ["needs review"]}]}

    def test_prompt_version_is_present_and_cache_is_reused(self):
        calls = []
        def fake(prompt, schema):
            calls.append(prompt)
            if "Audit candidate boundaries" in prompt:
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 0, "end_id": 2}], "title": "Stable", "reason": "supported editorial angle", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([0, 2], "Stable")
        with tempfile.TemporaryDirectory() as td, patch.object(pipeline, "ANALYSIS_CACHE", Path(td)), patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            first = pipeline.analyze(segs(5), "creators", 2, 20, "live")
            second = pipeline.analyze(segs(5), "creators", 2, 20, "live")
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 2)
        self.assertIn(pipeline.PROMPT_VERSION, calls[0])

    def test_another_take_bypasses_without_replacing_canonical_cache(self):
        calls = []
        def fake(prompt, schema):
            calls.append(prompt)
            if "Audit candidate boundaries" in prompt:
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 0, "end_id": 2}], "title": "Fresh", "reason": "supported editorial angle", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([0, 2], "Fresh")
        with tempfile.TemporaryDirectory() as td, patch.object(pipeline, "ANALYSIS_CACHE", Path(td)), patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            pipeline.analyze(segs(5), "creators", 2, 20, "live")
            cache_file = next(Path(td).glob("*.json")); before = cache_file.read_text()
            pipeline.analyze(segs(5), "creators", 2, 20, "live", {}, True)
            self.assertEqual(cache_file.read_text(), before)
        self.assertEqual(len(calls), 4)

    def test_batches_cover_long_transcript_global_ids_and_audit(self):
        prompts = []
        def fake(prompt, schema):
            prompts.append(prompt)
            if len(prompts) == 1: return self._response([0, 10])
            if len(prompts) == 2: return self._response([80, 90], "second batch")
            return {"clips": [{"id": "cand-ai-2", "ranges": [{"start_id": 80, "end_id": 90}], "title": "second batch", "reason": "supported editorial angle", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": ["check setup"]}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "MAX_ANALYSIS_CALLS": "40"}), patch("pipeline._openai_json", side_effect=fake):
            result = pipeline.analyze(segs(130), "creators", 2, 20, "live")
        discovery = prompts[:2]
        seen = set()
        for prompt in discovery:
            data = json.loads(prompt[prompt.index('{'):])
            seen.update(x["id"] for x in data["segments"])
        self.assertEqual(seen, set(range(130)))
        self.assertEqual(len(prompts), 3); self.assertEqual(result[0]["title"], "second batch")
        self.assertEqual(result[0]["ranges"], [{"start": 80.0, "end": 91.0}])

    def test_score_and_montage_ranges_are_mapped(self):
        def fake(prompt, schema):
            if "Audit" in prompt or "audit" in prompt: return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 1, "end_id": 3}, {"start_id": 6, "end_id": 8}], "title": "montage", "reason": "arc", "criteria": {"hook": 4, "specificity": 4, "payoff": 4, "audience_fit": 4, "coherence": 4}, "risks": []}]}
            return {"clips": [{"ranges": [{"start_id": 1, "end_id": 3}, {"start_id": 6, "end_id": 8}], "title": "montage", "reason": "arc", "criteria": {"hook": 4, "specificity": 4, "payoff": 4, "audience_fit": 4, "coherence": 4}, "risks": []}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            result = pipeline.analyze([{**s, "text": s["text"] + "."} for s in segs(10)], "creators", 2, 10, "live")
        self.assertEqual(result[0]["score"], 100)
        self.assertEqual(result[0]["ranges"], [{"start": 1.0, "end": 4.0}, {"start": 6.0, "end": 9.0}])

    def test_audit_receives_title_ranges_and_adjacent_context(self):
        audit_payload = {}
        def fake(prompt, schema):
            if "Audit candidate boundaries" in prompt:
                audit_payload.update(json.loads(prompt[prompt.index("{"):]))
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 4, "end_id": 8}], "title": "Repaired topic", "reason": "complete answer", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([5, 8], "What changed")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            pipeline.analyze(segs(20), "creators", 2, 20, "live")
        candidate = audit_payload["candidates"][0]
        self.assertEqual(candidate["title"], "What changed")
        self.assertEqual(candidate["ranges"], [{"start": 5.0, "end": 9.0}])
        self.assertEqual(candidate["context"][0]["start"], 0.0)
        self.assertEqual(candidate["context"][0]["end"], 1.0)
        self.assertEqual(candidate["context"][0]["id"], 0)
        self.assertEqual(candidate["context"][-1]["id"], 19)

    def test_audit_can_repair_ranges_across_batch_boundaries(self):
        transcript = [{"start": float(i * 3), "end": float((i + 1) * 3), "text": f"segment {i}"} for i in range(144)]
        prompts = []
        def fake(prompt, schema):
            prompts.append(prompt)
            if "Audit candidate boundaries" in prompt:
                data = json.loads(prompt[prompt.index("{"):])
                self.assertEqual(data["min_seconds"], 30)
                self.assertEqual(data["max_seconds"], 90)
                self.assertEqual(len(data["candidates"][0]["context"]), 144)
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 16, "end_id": 30}], "title": "Complete answer", "reason": "repair", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([20, 40], "Initial")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            result = pipeline.analyze(transcript, "creators", 30, 90, "live")
        self.assertEqual(result[0]["ranges"], [{"start": 48.0, "end": 93.0}])

    def test_audit_repair_cannot_use_unsupplied_long_transcript_ids(self):
        def fake(prompt, schema):
            if "Audit candidate boundaries" in prompt:
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 100, "end_id": 130}], "title": "fabricated context", "reason": "bad", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([0, 29], "Initial")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            result = pipeline.analyze(segs(201), "creators", 20, 40, "live")
        self.assertEqual(result, [])

    def test_boundary_checks_flag_continuation_and_cutoff_without_dropping_clip(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "the"},
            {"start": 1.0, "end": 2.0, "text": "So why should investors care?"},
            {"start": 2.0, "end": 3.0, "text": "I believe this matters"},
            {"start": 3.0, "end": 4.0, "text": "because the answer is clear."},
            {"start": 4.0, "end": 5.0, "text": "A complete opening."},
            {"start": 5.0, "end": 6.0, "text": "This may or"},
        ]
        clip = {"criteria": {"hook": 4, "specificity": 4, "payoff": 4, "audience_fit": 4, "coherence": 4}, "score": 100, "risks": [], "_range_ids": [[1, 2], [4, 5]]}
        pipeline._apply_boundary_checks(clip, segments)
        self.assertEqual(clip["criteria"]["coherence"], 4)
        self.assertEqual(clip["score"], 100)
        self.assertEqual(len(clip["risks"]), 2)

    def test_audit_invalid_id_and_budget_fail_before_calls(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "MAX_ANALYSIS_CALLS": "1"}), patch("pipeline._openai_json") as call:
            with self.assertRaises(RuntimeError): pipeline.analyze(segs(5000), "creators", 2, 20, "live")
            call.assert_not_called()
        def bad(prompt, schema):
            if "Audit" in prompt or "audit" in prompt: return {"clips": [{"id": "no-such-id", "ranges": [{"start_id": 0, "end_id": 2}], "title": "bad", "reason": "bad", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return self._response([0, 2])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test", "MAX_ANALYSIS_CALLS": "40"}), patch("pipeline._openai_json", side_effect=bad):
            with self.assertRaises(RuntimeError): pipeline.analyze(segs(10), "creators", 2, 20, "live")

    def test_invalid_candidate_is_skipped_and_order_is_required(self):
        def fake(prompt, schema):
            if "Audit" in prompt or "audit" in prompt:
                return {"clips": [{"id": "cand-ai-1", "ranges": [{"start_id": 1, "end_id": 3}], "title": "good", "reason": "usable", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
            return {"clips": [
                {"ranges": [{"start_id": 8, "end_id": 9}, {"start_id": 1, "end_id": 3}], "title": "backwards", "reason": "bad order", "criteria": {"hook": 4, "specificity": 4, "payoff": 4, "audience_fit": 4, "coherence": 4}, "risks": []},
                {"ranges": [{"start_id": 1, "end_id": 3}], "title": "good", "reason": "usable", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []},
            ]}
        metrics = {}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            result = pipeline.analyze(segs(10), "creators", 2, 20, "live", metrics)
        self.assertEqual([c["title"] for c in result], ["good"])
        self.assertEqual(metrics["rejected_candidates"], 1)

    def test_all_invalid_candidates_fail_with_rejection_count(self):
        def fake(prompt, schema):
            return {"clips": [{"ranges": [{"start_id": 8, "end_id": 9}, {"start_id": 1, "end_id": 3}], "title": "backwards", "reason": "bad order", "criteria": {"hook": 4, "specificity": 3, "payoff": 2, "audience_fit": 1, "coherence": 0}, "risks": []}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json", side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, r"no valid candidates; rejected 1"):
                pipeline.analyze(segs(10), "creators", 2, 20, "live")

    def test_local_never_calls_api_with_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("pipeline._openai_json") as call:
            result = pipeline.analyze(segs(10), "creators", 2, 20, "local")
        call.assert_not_called(); self.assertTrue(result); self.assertIsNone(result[0]["score"])

    def test_incomplete_checkpoint_resumes_at_saved_offset(self):
        with tempfile.TemporaryDirectory() as td:
            checkpoint = Path(td) / "transcript.json"
            checkpoint.write_text(json.dumps({"schema_version": 2, "complete": False, "next_start": 300, "raw_chunks": [{"start": 0, "end": 1, "text": "old"}]}))
            offsets = []
            with patch("pipeline.tool_ok", return_value=True), patch("pathlib.Path.is_file", return_value=True), patch("pipeline._run"), patch("pipeline._whisper_json", side_effect=lambda audio, offset, duration: offsets.append(offset) or [{"start": offset, "end": min(offset + 1, duration), "text": "new"}]):
                result = pipeline.transcribe(str(Path(td) / "x.mp4"), 320, checkpoint)
            self.assertEqual(offsets, [300]); self.assertTrue(json.loads(checkpoint.read_text())["complete"]); self.assertEqual(result[0]["start"], 0)


if __name__ == "__main__": unittest.main()
