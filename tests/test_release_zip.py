# SPDX-License-Identifier: GPL-3.0-or-later
"""The release zip holds what a user needs and nothing else."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_release_zip  # noqa: E402


class ReleaseZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zip = make_release_zip.build(Path(self.tmp.name), "9.9.9")
        self.names = zipfile.ZipFile(self.zip).namelist()

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_top_folder_with_the_needed_files(self):
        self.assertEqual({n.split("/")[0] for n in self.names}, {"OpenFill-9.9.9"})
        for need in (
            "Install OpenFill.cmd",
            "install.ps1",
            "README.md",
            "COPYING",
            "models/catalog.json",
            "models/comfy_setup.json",
            "gimp-openfill/gimp-openfill.py",
            "gimp-openfill/openfill/comfy_setup.py",
        ):
            self.assertIn(f"OpenFill-9.9.9/{need}", self.names)

    def test_no_tests_evidence_or_caches(self):
        for n in self.names:
            self.assertNotRegex(n, r"/(tests|evidence|screenshots|__pycache__)/")
            self.assertFalse(n.endswith(".pyc"))
            self.assertNotIn("RESUME", n)

    def test_scripts_are_crlf(self):
        data = zipfile.ZipFile(self.zip).read("OpenFill-9.9.9/Install OpenFill.cmd")
        self.assertIn(b"\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_version_comes_from_the_package(self):
        self.assertRegex(make_release_zip.read_version(), r"^\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
