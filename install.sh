#!/bin/sh
# Stable Boy - generative fill for GIMP 3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Installs the plug-in into the per-user GIMP 3 profile (Linux, macOS, Flatpak)
# and writes a default config if none exists.
#
#   sh install.sh [--link] [--uninstall] [--gimp-version 3.2] [--comfy-dir ~/ComfyUI]
#
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$REPO/gimp-stable-boy"
NAME="gimp-stable-boy"
LINK=0
UNINSTALL=0
GIMP_VERSION=""
COMFY_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --link) LINK=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --gimp-version) shift; GIMP_VERSION="$1" ;;
    --comfy-dir) shift; COMFY_DIR="$1" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "${GIMP_CONFIG_DIR:-}" ]; then
  BASE="$GIMP_CONFIG_DIR"
elif [ "$(uname)" = "Darwin" ]; then
  BASE="$HOME/Library/Application Support/GIMP"
elif [ -d "$HOME/.var/app/org.gimp.GIMP/config/GIMP" ]; then
  BASE="$HOME/.var/app/org.gimp.GIMP/config/GIMP"
else
  BASE="${XDG_CONFIG_HOME:-$HOME/.config}/GIMP"
fi

if [ -z "$GIMP_VERSION" ]; then
  GIMP_VERSION="$(ls -d "$BASE"/3.* 2>/dev/null | sed 's#.*/##' | sort -V | tail -1 || true)"
  if [ -z "$GIMP_VERSION" ]; then
    echo "No GIMP 3.x profile found under $BASE. Start GIMP once, then re-run." >&2
    exit 1
  fi
fi

PROFILE="$BASE/$GIMP_VERSION"
TARGET="$PROFILE/plug-ins/$NAME"

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$TARGET"
  echo "Removed $TARGET"
  exit 0
fi

mkdir -p "$PROFILE/plug-ins"
rm -rf "$TARGET"
if [ "$LINK" = 1 ]; then
  ln -s "$SOURCE" "$TARGET"
  echo "Linked $TARGET -> $SOURCE"
else
  cp -R "$SOURCE" "$TARGET"
  find "$TARGET" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  echo "Copied plug-in to $TARGET"
fi
chmod +x "$TARGET/$NAME.py" "$SOURCE/$NAME.py"

CONFIG_DIR="$PROFILE/stable-boy"
CONFIG="$CONFIG_DIR/config.json"
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG" ]; then
  [ -n "$COMFY_DIR" ] || COMFY_DIR="$HOME/ComfyUI"
  cat > "$CONFIG" <<EOF
{
  "backend": "comfyui",
  "comfy_dir": "$COMFY_DIR",
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
echo "Done. Restart GIMP and look for Filters > AI > Generative Fill..."
