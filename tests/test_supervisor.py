# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The supervisor's command line (it runs detached, so a parse error is otherwise invisible)."""

import contextlib
import io
import unittest

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
