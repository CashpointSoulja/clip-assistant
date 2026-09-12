from __future__ import annotations

import json
import mimetypes
import os
import platform
import subprocess
import threading
import urllib.parse
import re
import math
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pipeline

HOST, PORT = "127.0.0.1", 8765
ROOT = Path(__file__).resolve().parent
_heavy = threading.Semaphore(1)
_export_heavy = threading.Semaphore(1)
_job_locks: dict[str, threading.Lock] = {}
_job_locks_guard = threading.Lock()


def public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "source_path"}


def job_lock(jid: str) -> threading.Lock:
    with _job_locks_guard:
        return _job_locks.setdefault(jid, threading.Lock())


def update_job(jid: str, update) -> dict | None:
    with job_lock(jid):
        job = pipeline.load_job(jid)
        if not job:
            return None
        update(job)
        pipeline.save_job(job)
        return job


def work(job: dict) -> None:
    with _heavy:
        jid = job["id"]
        started = time.monotonic()
        try:
            update_job(jid, lambda current: current.update({"status": "processing", "stage": "probe", "error": None}))
            cp = pipeline.JOBS / f"{jid}.transcript.json"
            update_job(jid, lambda current: current.update({"stage": "transcribing"}))
            # pipeline.transcribe owns checkpoint recovery, including partial files.
            segments = pipeline.transcribe(job["source_path"], job["duration"], cp)
            numbered = [{"id": i, **s} for i, s in enumerate(segments)]
            update_job(jid, lambda current: current.update({"segments": numbered, "stage": "analysing"}))
            clips = pipeline.analyze(segments, job["audience"], job["min_seconds"], job["max_seconds"], job["mode"], {})
            update_job(jid, lambda current: current.update({"clips": clips, "status": "ready", "stage": "complete"}))
        except Exception as exc:
            update_job(jid, lambda current: current.update({"status": "failed", "stage": "error", "error": str(exc)[:500]}))
        update_job(jid, lambda current: current.setdefault("metrics", {}).update({"elapsed_seconds": round(time.monotonic() - started, 3)}))


def recover() -> None:
    pipeline.JOBS.mkdir(parents=True, exist_ok=True)
    for p in pipeline.JOBS.glob("*.json"):
        try:
            job = json.loads(p.read_text())
            if job.get("status") in {"queued", "processing", "exporting"}:
                job["status"], job["stage"], job["error"] = "failed", "restart", "Interrupted by server restart; retry by creating the job again."
                p.write_text(json.dumps(job, indent=2))
        except (OSError, ValueError):
            continue


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipAssistant/1.0"

    def _send(self, status: int, value: object, content_type: str = "application/json") -> None:
        data = json.dumps(value).encode() if content_type == "application/json" else value
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def _json(self, limit: int = 64 * 1024) -> dict:
        if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "-1"))
        if length < 0 or length > limit: raise ValueError("request body too large")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict): raise ValueError("JSON object required")
        return value

    def _allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        origin = self.headers.get("Origin")
        parsed = urllib.parse.urlparse(origin) if origin else None
        return host in {"127.0.0.1", "localhost"} and (not origin or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"})

    def do_GET(self) -> None:
        if not self._allowed(): return self._send(403, {"error": "local origin required"})
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health": return self._send(200, pipeline.health())
        if path == "/api/jobs":
            jobs = []
            for p in sorted(pipeline.JOBS.glob("*.json"), key=lambda item: item.stat().st_mtime_ns, reverse=True):
                if "." not in p.stem:
                    with job_lock(p.stem):
                        job = pipeline.load_job(p.stem)
                        if job:
                            jobs.append(public_job(job))
            return self._send(200, jobs)
        if path.startswith("/api/jobs/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and re.fullmatch(r"[0-9a-f]{32}", parts[2]):
                with job_lock(parts[2]):
                    job = pipeline.load_job(parts[2])
                    if not job:
                        snapshot = None
                        target = None
                    else:
                        snapshot = public_job(job) if len(parts) == 3 else None
                        target = next((Path(e["path"]) for e in job.get("exports", []) if e.get("filename") == parts[4]), None) if len(parts) == 5 and parts[3] == "exports" else Path(job["source_path"]) if len(parts) == 4 and parts[3] == "media" else None
                if snapshot is None and target is None and not job: return self._send(404, {"error": "job not found"})
                if len(parts) == 3: return self._send(200, snapshot)
                if len(parts) == 5 and parts[3] == "exports": return self._file(target, allow_range=True)
                if len(parts) == 4 and parts[3] == "media": return self._file(target, allow_range=True)
        if path == "/PLAN.md": return self._file(ROOT / "PLAN.md")
        if path == "/" or path.startswith("/assets/") or path in {"/app.js", "/style.css"}:
            target = (ROOT / "web" / ("index.html" if path == "/" else path.removeprefix("/"))).resolve()
            webroot = (ROOT / "web").resolve()
            if target.is_file() and (target == webroot or webroot in target.parents): return self._file(target)
        self._send(404, {"error": "not found"})

    def _file(self, target: Path | None, allow_range: bool = False) -> None:
        if not target or not target.is_file(): return self._send(404, {"error": "file not found"})
        target = target.resolve()
        if allow_range and target.suffix.lower() not in pipeline.EXTENSIONS: return self._send(403, {"error": "unsupported media"})
        size = target.stat().st_size; start, end = 0, size - 1
        range_header = self.headers.get("Range") if allow_range else None
        if range_header:
            try:
                spec = range_header.removeprefix("bytes="); a, b = spec.split("-", 1)
                if not a and not b: raise ValueError
                if not a:
                    length = int(b); start = max(0, size - length); end = size - 1
                else:
                    start = int(a); end = int(b) if b else size - 1
                if start < 0 or start > end or start >= size or end >= size: raise ValueError
            except ValueError: return self._send(416, {"error": "invalid byte range"})
            self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else: self.send_response(200)
        if allow_range: self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream"); self.send_header("Content-Length", str(end-start+1)); self.end_headers()
        try:
            with target.open("rb") as f:
                f.seek(start); remaining = end-start+1
                while remaining:
                    block = f.read(min(1024 * 1024, remaining))
                    if not block: break
                    self.wfile.write(block); remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            return
        

    def do_POST(self) -> None:
        if not self._allowed(): return self._send(403, {"error": "local origin required"})
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/pick":
                self._json()
                if platform.system() != "Darwin": raise ValueError("native file picker is only available on macOS")
                picked = subprocess.run(["osascript", "-e", 'POSIX path of (choose file of type {"public.movie"})'], capture_output=True, text=True, timeout=120, check=True).stdout.strip()
                return self._send(200, {"path": picked})
            body = self._json()
            if path == "/api/jobs":
                source = Path(str(body.get("path", ""))).expanduser().resolve(); minimum, maximum = int(body.get("min_seconds", 30)), int(body.get("max_seconds", 90)); mode = body.get("mode", "local")
                if source.suffix.lower() not in pipeline.EXTENSIONS or not source.is_file() or minimum < 1 or maximum < minimum or maximum > 600 or mode not in {"local", "live"}: raise ValueError("invalid job parameters")
                job = pipeline.new_job(str(source), str(body.get("audience", "general audience"))[:200], minimum, maximum, mode); threading.Thread(target=work, args=(job,), daemon=True).start(); return self._send(202, public_job(job))
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[0:2] == ["api", "jobs"] and re.fullmatch(r"[0-9a-f]{32}", parts[2]) and parts[3] == "retry":
                with job_lock(parts[2]):
                    job = pipeline.load_job(parts[2])
                    if not job:
                        retry_error = (404, "job not found")
                    elif job.get("status") not in {"failed", "error"}:
                        retry_error = (409, "only failed jobs can be retried")
                    else:
                        retry_error = None
                        job.update({"status": "queued", "stage": "queued", "error": None}); pipeline.save_job(job)
                if retry_error: return self._send(retry_error[0], {"error": retry_error[1]})
                threading.Thread(target=work, args=(job,), daemon=True).start()
                return self._send(202, public_job(job))
            if len(parts) == 4 and parts[0:2] == ["api", "jobs"] and re.fullmatch(r"[0-9a-f]{32}", parts[2]) and parts[3] == "export":
                if not _export_heavy.acquire(blocking=False): return self._send(409, {"error": "another export is already running"})
                try:
                    with job_lock(parts[2]):
                        job = pipeline.load_job(parts[2])
                        if not job: raise FileNotFoundError("job not found")
                        clip_id = body.get("clip_id"); clip = next((c for c in job.get("clips", []) if c.get("id") == clip_id), None); ranges = body.get("ranges")
                        if job.get("status") != "ready": raise RuntimeError("job is not ready for export")
                        if not clip or not isinstance(ranges, list) or not ranges or len(ranges) > 8: raise ValueError("clip and 1-8 ranges required")
                        for r in ranges:
                            if not isinstance(r, dict): raise ValueError("invalid range")
                            start, end = float(r.get("start", -1)), float(r.get("end", -1))
                            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= job["duration"] + .01): raise ValueError("range outside source bounds")
                        export_dir = pipeline.JOBS / job["id"]; export_dir.mkdir(parents=True, exist_ok=True)
                        index = len(job.get("exports", [])) + 1
                        out = export_dir / f"{re.sub(r'[^A-Za-z0-9_-]', '-', str(clip_id))}-{index}.mp4"; job["status"], job["stage"] = "exporting", "rendering"; pipeline.save_job(job)
                except FileNotFoundError:
                    _export_heavy.release()
                    return self._send(404, {"error": "job not found"})
                except RuntimeError as exc:
                    _export_heavy.release()
                    return self._send(409, {"error": str(exc)})
                except Exception:
                    _export_heavy.release()
                    raise
                def export() -> None:
                    try:
                        pipeline.render(job["source_path"], out, ranges); clip["approved"] = True; job.setdefault("exports", []).append({"id": clip_id, "filename": out.name, "path": str(out), "ranges": ranges}); job["status"], job["stage"] = "ready", "complete"
                        update_job(job["id"], lambda current: (next((c for c in current.get("clips", []) if c.get("id") == clip_id), {}).update({"approved": True}), current.setdefault("exports", []).append({"id": clip_id, "filename": out.name, "path": str(out), "ranges": ranges}), current.update({"status": "ready", "stage": "complete"})))
                    except Exception as exc: update_job(job["id"], lambda current: current.update({"status": "failed", "stage": "error", "error": str(exc)[:500]}))
                    finally:
                        _export_heavy.release()
                threading.Thread(target=export, daemon=True).start(); return self._send(202, public_job(job))
            self._send(404, {"error": "not found"})
        except (ValueError, TypeError, OverflowError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc: self._send(400, {"error": str(exc)[:300]})

    def log_message(self, *_: object) -> None: pass


if __name__ == "__main__":
    recover(); print(f"Clip assistant listening on http://{HOST}:{PORT}"); ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
