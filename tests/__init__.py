# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the GIMP-free parts of OpenFill.

Run with any Python 3.10+ from the repository root:

    python -m unittest discover -s tests -v
"""

import os
import sys

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gimp-openfill")
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)
