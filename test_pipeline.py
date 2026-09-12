import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline


class PipelineChecks(unittest.TestCase):
    def test_token_timestamps_are_grouped_into_words(self):
        tokens = [
            {"text": " Rel", "offsets": {"from": 100, "to": 200}},
            {"text": "iable", "offsets": {"from": 200, "to": 400}},
            {"text": " systems", "offsets": {"from": 450, "to": 700}},
            {"text": ".", "offsets": {"from": 700, "to": 700}},
        ]
        words = pipeline.normalize_words(tokens)
        self.assertEqual(words, [{"start": 0.1, "end": 0.4, "text": "Reliable"}, {"start": 0.45, "end": 0.7, "text": "systems."}])

    def test_ranges_snap_to_word_edges_and_fallback_without_words(self):
        segments = [{"start": 0, "end": 5, "text": "Hello world", "words": [{"start": 0.2, "end": 0.8, "text": "Hello"}, {"start": 1.0, "end": 1.6, "text": "world"}]}]
        self.assertEqual(pipeline.snap_ranges_to_words([{"start": 0, "end": 2}], segments), [{"start": 0.2, "end": 1.6}])
        original = [{"start": 0, "end": 2}]
        self.assertEqual(pipeline.snap_ranges_to_words(original, [{"start": 0, "end": 2, "text": "No words"}]), original)

    def test_transcription_cancellation_is_cooperative(self):
        with tempfile.TemporaryDirectory() as td:
            model = Path(td) / "model.bin"; model.write_bytes(b"test")
            with patch("pipeline.MODEL", model), patch("pipeline.tool_ok", return_value=True):
                with self.assertRaises(pipeline.CancelledError):
                    pipeline.transcribe(str(Path(td) / "x.mp4"), 601, should_cancel=lambda: True)

    def test_probe_rejects_video_without_audio(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "silent.mp4"; src.write_bytes(b"x")
            result = {"format": {"duration": "2.5"}, "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264"}]}
            with patch("pipeline._run", return_value=type("Completed", (), {"stdout": json.dumps(result)})()):
                with self.assertRaisesRegex(ValueError, "no audio stream"):
                    pipeline.probe(str(src))

    def test_probe_rejects_non_finite_duration(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "broken.mp4"; src.write_bytes(b"x")
            result = {"format": {"duration": "nan"}, "streams": [{"index": 0, "codec_type": "audio", "codec_name": "aac"}]}
            with patch("pipeline._run", return_value=type("Completed", (), {"stdout": json.dumps(result)})()):
                with self.assertRaisesRegex(ValueError, "usable duration"):
                    pipeline.probe(str(src))

    def test_checkpoint_replace_failure_preserves_previous_json_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as td:
            checkpoint = Path(td) / "transcript.json"
            model = Path(td) / "model.bin"; model.write_bytes(b"test")
            previous = {"schema_version": 2, "complete": False, "next_start": 0, "raw_chunks": []}
            checkpoint.write_text(json.dumps(previous))
            with patch("pipeline.MODEL", model), patch("pipeline.tool_ok", return_value=True), patch("pipeline._run"), patch("pipeline._whisper_json", return_value=[]), patch("pipeline.os.replace", side_effect=OSError("simulated crash")):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    pipeline.transcribe(str(Path(td) / "x.mp4"), 1, checkpoint)
            self.assertEqual(json.loads(checkpoint.read_text()), previous)
            self.assertEqual(list(Path(td).glob(".transcript.json.*.tmp")), [])

    def test_timestamp_normalization_and_bounds(self):
        got = pipeline.normalize_segments({"transcription": [{"offsets": {"from": 1200, "to": 3450}, "text": " hello  world "}]}, duration=4)
        self.assertEqual(got[0]["start"], 1.2); self.assertEqual(got[0]["end"], 3.45); self.assertEqual(got[0]["text"], "hello  world")

    def test_bad_ranges_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "x.mp4"; src.write_bytes(b"x")
            with patch("pipeline.probe", return_value={"duration": 10}):
                with self.assertRaises(ValueError): pipeline.render(str(src), Path(td) / "out.mp4", [{"start": 2, "end": 11}])

    def test_no_key_is_labelled_local(self):
        with patch.dict("os.environ", {}, clear=False):
            with patch("pipeline.os.getenv", side_effect=lambda k, d=None: None if k == "OPENAI_API_KEY" else d):
                clips = pipeline.analyze([{"start": 0, "end": 40, "text": "A useful story."}], "creators", 30, 90, "local")
        self.assertIsNone(clips[0]["score"]); self.assertIn("LOCAL", clips[0]["reason"])


if __name__ == "__main__": unittest.main()
