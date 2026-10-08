# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann (original Stable Boy for GIMP 2.10)
# Copyright (C) 2026 Stable Boy contributors (GIMP 3 port and redesign)
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
"""Stable Boy: generative fill, expand and text-to-image for GIMP 3.

Everything in this package except ``gimp_io`` is plain Python with no GIMP or
GTK dependency, so it can be unit-tested and reused outside GIMP.
"""

__version__ = "2.0.0-alpha.1"
__all__ = ["__version__"]
