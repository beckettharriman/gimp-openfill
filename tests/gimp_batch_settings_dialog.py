# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inside GIMP: open the Settings dialog on the Models tab (auto-closes) so an
external screen capture can record it, then quit."""

import os
import time

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp

OUT = os.environ.get("SB_TEST_OUT", r"C:\repos\gimp-stable-boy\docs\evidence\models")
os.makedirs(OUT, exist_ok=True)
os.environ["SB_SETTINGS_TAB"] = os.environ.get("SB_SETTINGS_TAB", "models")
os.environ.setdefault("SB_TEST_AUTOCLOSE", "12")
with open(os.path.join(OUT, "dialog-open.marker"), "w") as fh:
    fh.write(str(time.time()))
proc = Gimp.get_pdb().lookup_procedure("python-fu-stable-boy-settings")
config = proc.create_config()
config.set_property("run-mode", Gimp.RunMode.INTERACTIVE)
res = proc.run(config)
print("settings-dialog status", res.index(0))
if os.environ.get("SB_TEST_QUIT", "1") == "1":
    q = Gimp.get_pdb().lookup_procedure("gimp-quit")
    cfg = q.create_config()
    cfg.set_property("force", True)
    q.run(cfg)
