# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GIMP-free text and state logic for the dialogs, the progress window and
the Models tab: prompt history, plain status texts, error next steps and the
state of the per-model primary button. No ``gi`` imports, so it is unit
tested with any Python 3.10+.
"""

from __future__ import annotations

import json
import re

HISTORY_LIMIT = 20
SUGGESTED_SHORTCUT = "Shift+Ctrl+G"
SHORTCUT_HINT = (f"Tip: give it a key in Edit > Keyboard Shortcuts (search \"Generative Fill\"), "
                 f"for example {SUGGESTED_SHORTCUT}.")

FILL_PLACEHOLDER = "Describe what should appear here..."
EXPAND_PLACEHOLDER = "Describe what the new area should show (optional)..."
TXT2IMG_PLACEHOLDER = "Describe the image you want..."
REMOVE_EXPLANATION = ("Erases the selection and continues the background. No prompt needed: "
                      "just press Generate.")


# ------------------------------------------------------------ history ----

def parse_history(text: str | None) -> list[str]:
    """Read the stored history (a JSON list of strings); tolerate junk."""
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if isinstance(item, str) and item.strip()][:HISTORY_LIMIT]


def dump_history(history: list[str]) -> str:
    return json.dumps(list(history)[:HISTORY_LIMIT], ensure_ascii=False)


def remember_prompt(history: list[str], prompt: str, limit: int = HISTORY_LIMIT) -> list[str]:
    """Newest first, no duplicates (ignoring surrounding white space), at most ``limit``."""
    prompt = (prompt or "").strip()
    out = [p for p in history if p.strip() and p.strip() != prompt]
    if prompt:
        out.insert(0, prompt)
    return out[:limit]


def history_label(prompt: str, width: int = 60) -> str:
    """One line for a menu entry: white space collapsed, long prompts shortened."""
    text = " ".join((prompt or "").split())
    if len(text) <= width:
        return text
    return text[: max(1, width - 3)].rstrip() + "..."


def initial_prompt(config_prompt: str | None, history: list[str]) -> str:
    """The prompt a dialog starts with: the procedure's last value, else the newest history entry."""
    if config_prompt and config_prompt.strip():
        return config_prompt
    return history[0] if history else ""


# ------------------------------------------------------------ status -----

_STEP = re.compile(r"step\s+(\d+)\s*/\s*(\d+)", re.I)
_START = re.compile(r"Starting the AI backend\.\.\.\s*(\d+)\s*s", re.I)


def plain_step_text(text: str) -> str:
    """Translate backend progress texts into plain sentences for the progress window."""
    raw = (text or "").strip()
    if not raw:
        return raw
    m = _STEP.search(raw)
    if m:
        return f"Generating, step {m.group(1)} of {m.group(2)}"
    m = _START.search(raw)
    if m:
        return f"Starting the AI backend (first time takes about a minute), {m.group(1)} s"
    lowered = raw.lower()
    if lowered.startswith("starting the ai backend") or lowered.startswith("starting comfyui"):
        return "Starting the AI backend (first time takes about a minute)"
    if lowered.startswith("waiting for the ai backend"):
        return "Waiting for the AI backend"
    if lowered.startswith("uploading"):
        return "Sending the selection to the AI backend"
    if lowered.startswith("submitting"):
        return "Preparing the generation"
    if lowered.startswith("running node"):
        return "Loading the model and preparing (can take a while the first time)"
    if lowered.startswith("downloading result") or lowered == "done":
        return "Placing the result"
    return raw


def elapsed_text(elapsed: str, remaining: str | None = None) -> str:
    if remaining and remaining.strip("-: "):
        return f"Elapsed {elapsed}, about {remaining} left"
    return f"Elapsed {elapsed}"


def prompt_free_warning(model_name: str) -> str:
    short = (model_name or "The active model").split(" - ")[0]
    return (f"Note: the active model ({short}) only removes objects and ignores the prompt. "
            "Choose another model under Advanced to fill with a prompt.")


def selection_status(selection: tuple[int, int] | None, image: tuple[int, int] | None) -> str:
    """Status line of the Generative Fill dialog."""
    if image is None:
        return ""
    if selection is None:
        return (f"No selection: the whole image ({image[0]} x {image[1]} px) will be regenerated. "
                "Select an area first for a normal fill.")
    return f"Selection: {selection[0]} x {selection[1]} px in a {image[0]} x {image[1]} px image."


def expand_status(image: tuple[int, int] | None, left: int, top: int, right: int, bottom: int) -> str:
    if image is None:
        return ""
    width, height = image[0] + max(0, left) + max(0, right), image[1] + max(0, top) + max(0, bottom)
    if (width, height) == tuple(image):
        return "Add pixels on at least one side, otherwise nothing changes."
    return f"Canvas: {image[0]} x {image[1]} px, after expanding {width} x {height} px."


def txt2img_status(width: int, height: int, selection: tuple[int, int] | None,
                   default: tuple[int, int], target: str) -> str:
    if width > 0 and height > 0:
        size = f"{width} x {height} px"
    elif selection is not None and target == "layer":
        size = f"{selection[0]} x {selection[1]} px (the selection)"
    else:
        size = f"{default[0]} x {default[1]} px (the default from Settings)"
    where = "a new image" if target == "image" else "a new layer in this image"
    return f"Result: {size}, as {where}."


# ------------------------------------------------------------ windows ----

def clamp_position(x: int, y: int, width: int, height: int,
                   areas: list[tuple[int, int, int, int]], margin: int = 8) -> tuple[int, int]:
    """Keep a window of ``width`` x ``height`` at (x, y) fully inside one of
    the monitor work ``areas`` (x, y, w, h). A position on no monitor (for
    example remembered from a monitor that is gone) moves to the nearest
    area; a window larger than the area sticks to its top left corner."""
    if not areas:
        return x, y

    def distance(area):
        ax, ay, aw, ah = area
        dx = max(ax - x, 0, x - (ax + aw))
        dy = max(ay - y, 0, y - (ay + ah))
        return dx * dx + dy * dy

    ax, ay, aw, ah = min(areas, key=distance)
    nx = min(max(x, ax + margin), ax + aw - width - margin)
    ny = min(max(y, ay + margin), ay + ah - height - margin)
    return max(nx, ax), max(ny, ay)


# ------------------------------------------------------------ errors -----

_NEXT_STEPS = (
    ("was not found at", "Next step: open Filters > AI > Generative Fill Settings and choose the backend "
                         "folder with Browse."),
    ("auto-start is disabled", "Next step: turn on \"Start backend automatically\" in Filters > AI > "
                               "Generative Fill Settings, or start ComfyUI yourself."),
    ("did not come up", "Next step: try again (the first start can take a few minutes). If it keeps "
                        "failing, read comfyui.log in the stable-boy folder of your GIMP profile."),
    ("is not answering", ""),  # the A1111 message already says what to do
    ("ran out of memory", ""),  # describe_error already says what to do
    ("timed out", "Next step: try a smaller selection or fewer variations, or raise \"Generation time limit\" "
                  "in Settings > Connection and troubleshooting."),
    ("was cancelled", "Nothing in the image was changed."),
    ("rejected", "Next step: pick another model under Advanced, or turn on \"Verbose log\" in Settings "
                 "and try again."),
    ("press download", ""),
    ("download it from the models tab", ""),
    ("press install nodes", ""),
    ("model file is missing", "Next step: open Filters > AI > Generative Fill Settings > Models and download "
                              "or choose a model."),
    ("not available", "Next step: open Filters > AI > Generative Fill Settings and press Check backend."),
)


def next_step(message: str) -> str:
    lowered = (message or "").lower()
    for needle, step in _NEXT_STEPS:
        if needle in lowered:
            return step
    return ("Next step: try again. If it happens again, turn on \"Verbose log\" in Filters > AI > "
            "Generative Fill Settings and keep stable-boy.log for a bug report.")


def with_next_step(message: str) -> str:
    """``message`` followed by a plain next step (unless it already has one)."""
    message = (message or "").strip()
    if "next step" in message.lower():
        return message
    step = next_step(message)
    if not step:
        return message
    sep = "" if message.endswith((".", "!", "?")) else "."
    return f"{message}{sep} {step}" if message else step


def save_failed(path: str, detail: str) -> str:
    """Wording when the settings file cannot be written."""
    return (f"The settings could not be saved to {path}: {detail}. Next step: check that the folder is "
            "writable and the disk is not full, then open Filters > AI > Generative Fill Settings and "
            "press Save again.")


def unexpected_error(type_name: str, detail: str) -> str:
    """Wording for an error that is not a backend error (a bug or a GIMP failure)."""
    return with_next_step(f"Something went wrong: {type_name}: {detail}")


def health_text(ok: bool, detail: str, model_count: int, inpaint_nodes: bool) -> str:
    """Result line of the Settings > General "Check backend" button."""
    if ok:
        models = f"{model_count} model{'s' if model_count != 1 else ''}"
        nodes = "inpaint nodes installed" if inpaint_nodes else "inpaint nodes missing (SDXL quality fill needs them)"
        return f"Backend OK: {models}, {nodes}."
    reason = " ".join((detail or "no answer").split())
    if len(reason) > 220:
        reason = reason[:217].rstrip() + "..."
    step = next_step(reason)
    if not step or step.startswith("Next step: try again. If it happens"):
        step = ("Next step: check the backend folder above, keep \"Start backend automatically\" on, "
                "and press Check backend again.")
    return f"Could not reach the backend: {reason.rstrip('.')}. {step}"


# ------------------------------------------------------------ models -----

def primary_action(row: dict, current: dict | None, pending_ids: list[str] | None = None,
                   has_token: bool = True) -> tuple[str, str | None, bool]:
    """(label, action, sensitive) of the single primary button of a model row.

    Actions: "download", "cancel", "activate", "nodes", "token" (ask for a
    token first) or None (informational state).
    """
    current = current or {}
    pending_ids = pending_ids or []
    mid = row.get("id")
    if current.get("model_id") == mid:
        kind = current.get("type")
        if kind == "download":
            total = current.get("total") or 0
            pct = 100.0 * (current.get("done") or 0) / total if total else 0.0
            return f"Downloading {pct:.0f}% - Cancel", "cancel", True
        if kind == "install_nodes":
            return "Installing nodes...", None, False
        if kind == "remove":
            return "Removing...", None, False
        return "Working...", None, False
    if mid in pending_ids:
        return "Queued", None, False
    if not row.get("installed"):
        if row.get("gated") and not has_token:
            return "Download", "token", True
        return ("Resume download" if row.get("partial") else "Download"), "download", True
    if row.get("missing_models"):
        return "Download missing part", "download", True
    if row.get("missing_nodes"):
        return "Install nodes", "nodes", not bool(current)
    if not row.get("runnable"):
        return "Downloaded", None, False
    if row.get("active"):
        return "Active", None, False
    return "Set active", "activate", True


def model_sort_key(row: dict) -> tuple:
    """Active first, then installed, then the rest; stable by catalog order otherwise."""
    return (0 if row.get("active") else 1 if row.get("installed") else 2,)


def model_summary(row: dict) -> str:
    """Second line of a model row, in plain words."""
    caps = row.get("capabilities") or []
    names = {"fill": "fill", "expand": "expand", "txt2img": "text to image", "remove": "object removal",
             "edit": "edit"}
    uses = [names[c] for c in caps if c in names]
    if not row.get("runnable") or "patch" in caps:
        uses = ["helper file used by another model"]
    pieces = []
    if uses:
        text = ", ".join(uses)
        pieces.append(text[0].upper() + text[1:])
    if row.get("size"):
        pieces.append(str(row["size"]))
    vram = row.get("min_vram_gb")
    if vram:
        pieces.append(f"Needs {vram:g} GB of graphics memory")
    if row.get("gated"):
        pieces.append("Needs a free Hugging Face token")
    return ". ".join(pieces) + ("." if pieces else "")


def model_option_label(name: str, installed: bool, active: bool) -> str:
    """Label of an entry in the Model dropdown of the generation dialogs."""
    name = (name or "").split(" - ")[0].strip() or name
    if active:
        return f"{name} (active model)"
    if not installed:
        return f"{name} (not downloaded)"
    return name
