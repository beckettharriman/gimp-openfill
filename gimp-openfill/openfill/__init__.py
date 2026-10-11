# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""OpenFill: generative fill, expand and text-to-image for GIMP 3.

Everything in this package except ``gimp_io`` is plain Python with no GIMP or
GTK dependency, so it can be unit-tested and reused outside GIMP.
"""

import subprocess as _subprocess
import sys as _sys

__version__ = "2.0.0-beta.1"
__all__ = ["__version__"]


def _hide_child_consoles() -> None:
    """On Windows, start every child process without a console window.

    GIMP's Python and the supervisor run without a console, so a console
    program started from them (by us or by a library) would otherwise open a
    blank terminal window. Explicit creationflags are kept as given."""
    if _sys.platform != "win32" or getattr(_subprocess.Popen, "_openfill_hidden", False):
        return
    original = _subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, N807
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = _subprocess.CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    _subprocess.Popen.__init__ = __init__  # type: ignore[method-assign]
    _subprocess.Popen._openfill_hidden = True  # type: ignore[attr-defined]


_hide_child_consoles()
