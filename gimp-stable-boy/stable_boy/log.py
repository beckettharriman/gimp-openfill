# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""File logging shared by the plug-in process and the supervisor."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-5s [%(process)d %(name)s] %(message)s"


def get_logger(path: Path, name: str = "stable-boy", debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    wanted = str(Path(path))
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == wanted:
            return logger
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(wanted, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
