# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The supervisor's command line (it runs detached, so a parse error is otherwise invisible)."""

import contextlib
import io
import os
import unittest
from pathlib import Path

from stable_boy import supervisor
from stable_boy.supervisor import build_parser


class ParserTests(unittest.TestCase):
    def parse(self, *argv):
        return build_parser().parse_args(["--base", "base-dir", *argv])

    def test_extra_args_with_leading_dash_as_one_item(self):
        self.assertEqual(self.parse("--extra-args=--cpu --verbose INFO").extra_args, "--cpu --verbose INFO")
        self.assertEqual(self.parse("--extra-args=--cpu").extra_args, "--cpu")

    def test_extra_args_given_alone(self):
        args = build_parser().parse_args(["--extra-args=--cpu --verbose INFO", "--base", "b"])
        self.assertEqual(args.extra_args, "--cpu --verbose INFO")

    def test_separate_dash_value_is_what_used_to_break(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse("--extra-args", "--cpu")

    def test_defaults(self):
        args = self.parse()
        self.assertEqual((args.mode, args.host, args.port, args.extra_args), ("backend", "127.0.0.1", 8188, ""))
        self.assertEqual(args.idle_minutes, 20.0)

    def test_full_backend_command(self):
        args = self.parse(
            "--mode", "backend", "--python", "py.exe", "--main", "main.py", "--cwd", "c",
            "--port", "8190", "--watch-pid", "42", "--idle-minutes", "0",
        )  # fmt: skip
        self.assertEqual((args.python, args.port, args.watch_pid, args.idle_minutes), ("py.exe", 8190, 42, 0.0))


if __name__ == "__main__":
    unittest.main()


class StartLockAndWatcherTests(unittest.TestCase):
    """rob-two-requests-first-gimp-exits: one supervisor per profile, kept alive by every GIMP using it."""

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lock_is_exclusive_and_released(self):
        lock = self.base / supervisor.START_LOCK_FILENAME
        self.assertTrue(supervisor.acquire_start_lock(lock))
        self.assertEqual(lock.read_text(encoding="utf-8"), str(os.getpid()))
        supervisor.release_start_lock(lock)
        self.assertFalse(lock.exists())

    def test_lock_held_by_a_live_python_is_respected(self):
        import subprocess
        import sys

        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            lock = self.base / supervisor.START_LOCK_FILENAME
            lock.write_text(str(holder.pid), encoding="utf-8")
            self.assertFalse(supervisor.acquire_start_lock(lock))
            supervisor.release_start_lock(lock)  # not ours: stays
            self.assertTrue(lock.exists())
        finally:
            holder.kill()
            holder.wait()

    def test_stale_lock_is_taken_over(self):
        lock = self.base / supervisor.START_LOCK_FILENAME
        lock.write_text("999999", encoding="utf-8")  # no such process
        self.assertTrue(supervisor.acquire_start_lock(lock))
        self.assertEqual(lock.read_text(encoding="utf-8"), str(os.getpid()))

    def test_live_watchers(self):
        folder = self.base / supervisor.WATCHERS_DIRNAME
        folder.mkdir()
        (folder / str(os.getpid())).touch()
        (folder / "999999").touch()
        (folder / "junk").touch()
        self.assertEqual(supervisor.live_watchers(self.base, names=("python",)), [os.getpid()])
        self.assertFalse((folder / "999999").exists())  # dead entry removed
        self.assertEqual(supervisor.live_watchers(self.base), [])  # this process is not a GIMP
        self.assertFalse((folder / str(os.getpid())).exists())
