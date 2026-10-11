#!/bin/sh
# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Installs the plug-in into the per-user GIMP 3 profile (Linux, Flatpak, macOS)
# and writes a default config if none exists.
#
#   sh install.sh [--link] [--gimp-version 3.2] [--profile-dir DIR] [--comfy-dir ~/ComfyUI]
#   sh install.sh --uninstall [--remove-config] [--profile-dir DIR]
#
# Profile folders searched (newest 3.x wins):
#   $GIMP3_DIRECTORY                                   (if set: the profile folder itself)
#   Linux:   ${XDG_CONFIG_HOME:-~/.config}/GIMP/3.x
#   Flatpak: ~/.var/app/org.gimp.GIMP/config/GIMP/3.x
#   macOS:   ~/Library/Application Support/GIMP/3.x
#
# --link        symlink the repository folder instead of copying (development). Not
#               recommended for Flatpak: the sandbox may not see the repository.
# --uninstall   remove the plug-in (folder or symlink). The settings folder
#               <profile>/openfill (config.json with the Hugging Face token, logs)
#               is kept unless --remove-config is given.
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
SOURCE="$REPO/gimp-openfill"
NAME="gimp-openfill"
LINK=0
UNINSTALL=0
REMOVE_CONFIG=0
GIMP_VERSION=""
PROFILE=""
COMFY_DIR=""

usage() {
  sed -n '8,9p' "$0" | sed 's/^# \{0,1\}//'
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --link) LINK=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --remove-config) REMOVE_CONFIG=1 ;;
    --gimp-version) [ $# -ge 2 ] || die "--gimp-version needs a value"; shift; GIMP_VERSION=$1 ;;
    --profile-dir) [ $# -ge 2 ] || die "--profile-dir needs a value"; shift; PROFILE=$1 ;;
    --comfy-dir) [ $# -ge 2 ] || die "--comfy-dir needs a value"; shift; COMFY_DIR=$1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# Newest 3.x folder name under $1 (empty when none).
newest_3x() {
  for dir in "$1"/3.*; do
    [ -d "$dir" ] || continue
    name=${dir##*/}
    case "$name" in 3.*[!0-9]*|3.) continue ;; esac
    echo "$name"
  done | sort -t. -k2,2n | tail -n 1
}

FLATPAK=0
if [ -z "$PROFILE" ] && [ -n "${GIMP3_DIRECTORY:-}" ]; then
  PROFILE=$GIMP3_DIRECTORY
fi
if [ -z "$PROFILE" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    CANDIDATES="$HOME/Library/Application Support/GIMP"
  else
    CANDIDATES="${XDG_CONFIG_HOME:-$HOME/.config}/GIMP
$HOME/.var/app/org.gimp.GIMP/config/GIMP"
  fi
  BASE=""
  # Newline-separated list; paths may contain spaces, so split on newlines only.
  OLD_IFS=$IFS
  IFS='
'
  for candidate in $CANDIDATES; do
    if [ -n "$GIMP_VERSION" ] && [ -d "$candidate/$GIMP_VERSION" ]; then BASE=$candidate; break; fi
    if [ -z "$GIMP_VERSION" ] && [ -n "$(newest_3x "$candidate")" ]; then BASE=$candidate; break; fi
  done
  IFS=$OLD_IFS
  if [ -z "$BASE" ]; then
    if [ "$UNINSTALL" = 1 ]; then
      echo "No GIMP 3.x profile found; nothing to uninstall."
      exit 0
    fi
    if command -v gimp >/dev/null 2>&1 || command -v gimp-3.0 >/dev/null 2>&1 \
        || { command -v flatpak >/dev/null 2>&1 && flatpak info org.gimp.GIMP >/dev/null 2>&1; } \
        || [ -d "/Applications/GIMP.app" ]; then
      die "GIMP is installed but has no 3.x profile yet. Start GIMP 3 once, close it, then re-run."
    fi
    die "GIMP 3 does not seem to be installed (no 3.x profile found). Install it from https://www.gimp.org/downloads/, start it once, then re-run."
  fi
  [ -n "$GIMP_VERSION" ] || GIMP_VERSION=$(newest_3x "$BASE")
  PROFILE="$BASE/$GIMP_VERSION"
  case "$BASE" in */.var/app/org.gimp.GIMP/*) FLATPAK=1 ;; esac
fi

TARGET="$PROFILE/plug-ins/$NAME"
CONFIG_DIR="$PROFILE/openfill"
CONFIG="$CONFIG_DIR/config.json"
echo "GIMP profile: $PROFILE"

remove_target() {
  if [ -L "$TARGET" ]; then
    rm -f "$TARGET"          # the link only, never the repository behind it
    echo "Removed plug-in symlink $TARGET"
  elif [ -e "$TARGET" ]; then
    rm -rf "$TARGET"
    echo "Removed plug-in folder $TARGET"
  else
    return 1
  fi
}

if [ "$UNINSTALL" = 1 ]; then
  remove_target || echo "No plug-in installed at $TARGET"
  if [ "$REMOVE_CONFIG" = 1 ]; then
    if [ -d "$CONFIG_DIR" ]; then
      rm -rf "$CONFIG_DIR"
      echo "Removed settings folder $CONFIG_DIR (config.json, logs, task queue)"
    fi
  elif [ -d "$CONFIG_DIR" ]; then
    echo "Kept settings folder $CONFIG_DIR (holds config.json and the Hugging Face token; use --remove-config to delete it)"
  fi
  echo "Done. Restart GIMP; the Filters > OpenFill entries are gone. Models in the ComfyUI folder are not touched."
  exit 0
fi

[ -f "$SOURCE/$NAME.py" ] || die "plug-in source not found at $SOURCE"

# GIMP runs Python plug-ins with python3 from PATH on Linux (Flatpak and macOS bundle their own).
if [ "$FLATPAK" = 0 ] && [ "$(uname -s)" != "Darwin" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      echo "warning: the python3 on PATH does not run or is older than 3.10; OpenFill needs Python 3.10 or newer" >&2
    fi
  else
    echo "warning: python3 not found on PATH; GIMP needs it to run Python plug-ins" >&2
  fi
fi

mkdir -p "$PROFILE/plug-ins"
if remove_target >/dev/null; then
  echo "Replaced the existing plug-in at $TARGET"
fi
if [ "$LINK" = 1 ]; then
  if [ "$FLATPAK" = 1 ]; then
    echo "warning: the Flatpak sandbox may not be able to follow a symlink into $REPO; use a copy if the menu entries do not appear" >&2
  fi
  ln -s "$SOURCE" "$TARGET"
  echo "Linked $TARGET -> $SOURCE"
else
  cp -R "$SOURCE" "$TARGET"
  find "$TARGET" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  mkdir -p "$TARGET/models"
  cp "$REPO/models/catalog.json" "$TARGET/models/catalog.json"
  chmod +x "$TARGET/$NAME.py"
  echo "Copied plug-in (with models/catalog.json) to $TARGET"
fi

mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG" ]; then
  [ -n "$COMFY_DIR" ] || COMFY_DIR="$HOME/ComfyUI"
  # JSON-escape backslashes and double quotes in the path.
  ESCAPED=$(printf '%s' "$COMFY_DIR" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
  umask 077  # config.json will hold the Hugging Face token
  cat > "$CONFIG" <<EOF
{
  "backend": "comfyui",
  "comfy_dir": "$ESCAPED",
  "url": "http://127.0.0.1:8188",
  "autostart": true,
  "idle_timeout_minutes": 20,
  "checkpoint": "sd-v1-5-inpainting.ckpt",
  "sdxl_checkpoint": "sd_xl_base_1.0.safetensors",
  "fooocus_head": "fooocus_inpaint_head.pth",
  "fooocus_patch": "inpaint_v26.fooocus.patch",
  "quality": "fast"
}
EOF
  echo "Wrote default config to $CONFIG"
else
  echo "Keeping existing config at $CONFIG"
fi

if [ -n "$COMFY_DIR" ] && [ ! -f "$COMFY_DIR/main.py" ] && [ ! -f "$COMFY_DIR/ComfyUI/main.py" ]; then
  echo "warning: ComfyUI not found at $COMFY_DIR. See docs/models.md for the backend setup." >&2
fi
echo ""
echo "Next steps:"
echo "  1. Restart GIMP (plug-ins are registered at start-up)."
echo "  2. Open Filters > OpenFill > Generative Fill Settings... and check the ComfyUI folder."
echo "  3. In the Models tab, download a model (SD 1.5 inpainting is the small default) and press Set active."
echo "  4. Select an area of an image and run Filters > OpenFill > Generative Fill..."
echo "To remove the plug-in later: sh install.sh --uninstall (add --remove-config to delete the settings too)."
