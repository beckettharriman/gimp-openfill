# SPDX-License-Identifier: GPL-3.0-or-later
"""Resumable download logic against a local HTTP server that honours Range."""

import hashlib
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from stable_boy import downloads

PAYLOAD = bytes(range(256)) * 4096  # 1 MiB, deterministic
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class State:
    requests: list[dict] = []
    gated = False
    ignore_range = False
    drop_after: int | None = None   # close connection after N bytes (simulates a cut)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        State.requests.append(dict(self.headers))
        if State.gated and self.headers.get("Authorization") != "Bearer secret":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        rng = self.headers.get("Range")
        start = 0
        status = 200
        if rng and not State.ignore_range:
            start = int(rng.split("=")[1].rstrip("-"))
            if start >= len(PAYLOAD):
                self.send_response(416)
                self.end_headers()
                return
            status = 206
        body = PAYLOAD[start:]
        if State.drop_after is not None:
            body = body[:State.drop_after]
        self.send_response(status)
        self.send_header("Content-Length", str(len(PAYLOAD) - start))  # full length even when we cut
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        self.end_headers()
        self.wfile.write(body)


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/file.bin"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        State.requests = []
        State.gated = False
        State.ignore_range = False
        State.drop_after = None
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "models" / "inpaint" / "file.bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_download_verified_and_atomic(self):
        events = []
        r = downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA, progress=lambda d, t, s: events.append((d, t)))
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)
        self.assertFalse(downloads.part_path(self.dest).exists())
        self.assertEqual(r.sha256, SHA)
        self.assertEqual(r.resumed_from, 0)
        self.assertEqual(events[-1], (len(PAYLOAD), len(PAYLOAD)))
        self.assertNotIn("Range", State.requests[0])

    def test_resume_sends_range_and_appends(self):
        part = downloads.part_path(self.dest)
        part.parent.mkdir(parents=True)
        part.write_bytes(PAYLOAD[:300_000])
        r = downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(State.requests[0].get("Range"), "bytes=300000-")
        self.assertEqual(r.resumed_from, 300_000)
        self.assertEqual(r.bytes_written, len(PAYLOAD) - 300_000)
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)

    def test_server_ignoring_range_restarts_from_zero(self):
        State.ignore_range = True
        part = downloads.part_path(self.dest)
        part.parent.mkdir(parents=True)
        part.write_bytes(b"garbage" * 1000)
        r = downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(r.resumed_from, 0)
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)

    def test_cut_connection_keeps_part_for_resume(self):
        State.drop_after = 100_000
        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(ctx.exception.code, "size")
        self.assertEqual(downloads.part_path(self.dest).stat().st_size, 100_000)
        State.drop_after = None
        downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)

    def test_hash_mismatch_deletes_file(self):
        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file(self.url, self.dest, len(PAYLOAD), "0" * 64)
        self.assertEqual(ctx.exception.code, "hash")
        self.assertFalse(self.dest.exists())
        self.assertFalse(downloads.part_path(self.dest).exists())

    def test_gated_without_token_and_with_token(self):
        State.gated = True
        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(ctx.exception.code, "auth")
        downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA, token="secret")
        self.assertTrue(self.dest.exists())

    def test_not_found(self):
        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file(self.url.replace("file.bin", "missing"), self.dest)
        self.assertEqual(ctx.exception.code, "notfound")

    def test_existing_good_file_is_skipped(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(PAYLOAD)
        r = downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertTrue(r.skipped)
        self.assertEqual(State.requests, [])

    def test_existing_wrong_size_is_replaced(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(b"old")
        downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA)
        self.assertEqual(self.dest.read_bytes(), PAYLOAD)

    def test_cancel(self):
        calls = {"n": 0}

        def cancel():
            calls["n"] += 1
            return calls["n"] > 1

        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file(self.url, self.dest, len(PAYLOAD), SHA, cancel=cancel)
        self.assertEqual(ctx.exception.code, "cancelled")
        self.assertFalse(self.dest.exists())

    def test_unreachable(self):
        with self.assertRaises(downloads.DownloadError) as ctx:
            downloads.download_file("http://127.0.0.1:1/x", self.dest)
        self.assertEqual(ctx.exception.code, "network")


class NodeInstallTests(unittest.TestCase):
    def test_install_runs_clone_checkout_pip(self):
        calls = []

        class R:
            returncode = 0
            stdout = stderr = ""

        def runner(cmd, **kw):
            calls.append(cmd)
            if cmd[1] == "clone":
                target = Path(cmd[-1])
                (target / ".git").mkdir(parents=True)
                (target / "requirements.txt").write_text("gguf\n")
            return R()

        with tempfile.TemporaryDirectory() as tmp:
            target = downloads.install_custom_node("https://example/repo", "Repo", "abc1234", Path(tmp),
                                                   Path("py.exe"), runner=runner)
            self.assertEqual(target, Path(tmp) / "Repo")
            self.assertEqual(calls[0][1], "clone")
            self.assertIn("checkout", calls[2])
            self.assertEqual(calls[2][-1], "abc1234")
            self.assertEqual(calls[3][:4], ["py.exe", "-s", "-m", "pip"])
            # second run: no clone
            calls.clear()
            downloads.install_custom_node("https://example/repo", "Repo", "abc1234", Path(tmp),
                                          Path("py.exe"), runner=runner)
            self.assertNotEqual(calls[0][1], "clone")

    def test_failure_raises(self):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                downloads.install_custom_node("https://example/repo", "Repo", "abc1234", Path(tmp),
                                              Path("py.exe"), runner=lambda *a, **k: R())


if __name__ == "__main__":
    unittest.main()
