import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import server


class ServerChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name)
        cls.old_jobs = server.pipeline.JOBS; server.pipeline.JOBS = cls.root / "jobs"; server.pipeline.JOBS.mkdir()
        cls.jid = "a" * 32; cls.media = cls.root / "source.mp4"; cls.media.write_bytes(b"0123456789")
        (server.pipeline.JOBS / f"{cls.jid}.json").write_text(json.dumps({"id": cls.jid, "status": "ready", "stage": "complete", "source_path": str(cls.media), "duration": 10, "segments": [], "clips": [], "exports": [], "metrics": {}}))
        cls.old_port = server.PORT
        cls.httpd = server.ThreadingHTTPServer((server.HOST, 0), server.Handler)
        server.PORT = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); server.pipeline.JOBS = cls.old_jobs; server.PORT = cls.old_port; cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection(server.HOST, server.PORT, timeout=3); headers = headers or {}
        if body is not None: headers.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
        c.request(method, path, body, headers); r = c.getresponse(); data = r.read(); c.close(); return r.status, r.getheaders(), data

    def test_bad_json_and_foreign_origin(self):
        status, _, _ = self.request("POST", "/api/jobs", b"not-json", {"Content-Type": "application/json", "Content-Length": "8"}); self.assertEqual(status, 400)
        status, _, _ = self.request("GET", "/api/health", headers={"Origin": "http://evil.example"}); self.assertEqual(status, 403)

    def test_media_range_suffix_and_static_traversal(self):
        status, headers, body = self.request("GET", f"/api/jobs/{self.jid}/media", headers={"Range": "bytes=-3"}); self.assertEqual(status, 206); self.assertEqual(body, b"789"); self.assertIn(("Accept-Ranges", "bytes"), headers)
        status, _, _ = self.request("GET", "/assets/../.env"); self.assertEqual(status, 404)

    def test_concurrent_retries_claim_one_worker(self):
        failed = {"id": self.jid, "status": "failed", "stage": "error", "source_path": str(self.media), "duration": 10, "exports": [], "metrics": {}}
        (server.pipeline.JOBS / f"{self.jid}.json").write_text(json.dumps(failed))
        calls = []; gate = threading.Lock()
        original = server.work
        def fake_work(job):
            with gate: calls.append(job["id"])
        server.work = fake_work
        try:
            results = []
            threads = [threading.Thread(target=lambda: results.append(self.request("POST", f"/api/jobs/{self.jid}/retry", b"{}", {"Content-Type": "application/json"}))) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertEqual(sorted(result[0] for result in results), [202, 409])
            self.assertEqual(calls, [self.jid])
        finally:
            server.work = original

    def test_competing_exports_preserve_persisted_state(self):
        job = {"id": self.jid, "status": "ready", "stage": "complete", "source_path": str(self.media), "duration": 10,
               "clips": [{"id": "cand-1", "ranges": [{"start": 0, "end": 2}], "approved": False}], "exports": [], "metrics": {}}
        (server.pipeline.JOBS / f"{self.jid}.json").write_text(json.dumps(job))
        started = threading.Event(); release = threading.Event(); original = server.pipeline.render
        def fake_render(source, output, ranges):
            started.set(); release.wait(3); output.write_bytes(b"clip")
        server.pipeline.render = fake_render
        try:
            body = json.dumps({"clip_id": "cand-1", "ranges": [{"start": 0, "end": 2}]}).encode()
            first = threading.Thread(target=lambda: setattr(self, "first_export", self.request("POST", f"/api/jobs/{self.jid}/export", body)))
            first.start(); self.assertTrue(started.wait(2))
            second = self.request("POST", f"/api/jobs/{self.jid}/export", body)
            self.assertEqual(second[0], 409)
            release.set(); first.join(3)
            saved = {}
            for _ in range(30):
                status, _, data = self.request("GET", f"/api/jobs/{self.jid}")
                saved = json.loads(data)
                if saved.get("exports"): break
                time.sleep(.02)
            self.assertEqual(self.first_export[0], 202); self.assertEqual(status, 200)
            self.assertEqual(len(saved["exports"]), 1); self.assertTrue(saved["clips"][0]["approved"])
        finally:
            server.pipeline.render = original


if __name__ == "__main__": unittest.main()
