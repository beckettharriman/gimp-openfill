# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Concrete backend implementations."""

from .a1111 import A1111Backend
from .comfy import ComfyBackend

__all__ = ["A1111Backend", "ComfyBackend"]
