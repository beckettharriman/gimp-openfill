# Dialogs: simpler Generative Fill, visual Generative Expand (2026-10-09, daytime)

Status: code and unit tests only. No GIMP was started and no screenshot was
taken while this was written (the owner was at the screen). Everything under
"What to verify visually" is still open and must be checked by the
screenshot run (`tests/gimp_batch_ui_screenshots.py`, see below).

## What changed

### Generative Fill

- Always visible: mode switch, prompt (fixed height of 4 text lines),
  Recent prompts, Avoid (negative prompt), Model, Variations.
- Advanced holds only Change amount and Seed.
- The hint lines under every field were removed; each field has a one-line
  tooltip instead. The remaining lines are one short line each: key hint,
  selection size (or the no-selection warning in orange), the removal-model
  note (orange, only when the active model only removes objects) and the
  shortcut hint.
- The prompt box keeps its height when Advanced opens or closes and when
  Remove object is chosen (the removal text is shown in the same space).
  Closing Advanced shrinks the window back to its content height; the width
  stays 640 px and the top edge does not move.
- An empty prompt in Fill mode shows "Type a prompt, or choose Remove object."
  in the warning line instead of generating.

Layout (Fill mode, Advanced open):

```
+-- Generative Fill -------------------------------------------+
| [Fill with a prompt][Remove object]                          |
| +----------------------------------------------------------+ |
| | a red door with brass handles                            | |
| |                                                          | |  4 lines, fixed
| |                                                          | |
| |                                                          | |
| +----------------------------------------------------------+ |
| [Recent prompts]          Enter generates, Shift+Enter adds a line
|      Avoid [blurry, low quality, watermark, text          ]  |
|      Model [SD 1.5 Inpainting (active model)  v] Variations [1 -+]
| Selection: 260 x 200 px                                      |
| v Advanced                                                   |
|   Change amount [===================o] 1.00                  |
|            Seed [x] Random [0 -+]                            |
| Shortcut: Edit > Keyboard Shortcuts, search "Generative Fill" (e.g. Shift+Ctrl+G)
|                                        [Cancel] [Generate]   |
+--------------------------------------------------------------+
```

Remove object mode: the prompt area shows "Erases the selection and continues
the background. No prompt needed." and "An installed LaMa or MAT model is used
when there is one."; Recent prompts is disabled. Without a selection the
selection line becomes the orange "No selection: the whole image (W x H px)
will be regenerated."

### Generative Expand

- The four pixel boxes are no longer the main control. A canvas editor
  (`stable_boy/ui_expand.py`, a `Gtk.DrawingArea`) shows a thumbnail of the
  image (fits 360 px) inside a dashed frame for the new canvas. Dragging any
  of the eight handles (or anywhere along an edge) outward adds space; the new
  area is shaded blue and labelled with its size ("+256"); the pixel boxes and
  the readout update while dragging. During a drag the scale is frozen so the
  image stays under the pointer; on release the view fits the new canvas.
  Drags snap to 8 px; the boxes take any value.
- Ratio presets: Original, 1:1, 4:5, 5:4, 3:2, 2:3, 16:9, 9:16, Custom. A
  preset makes the smallest canvas with that ratio that contains the image
  (when the image already has the ratio, as with Original, each axis grows by
  25 %). The 3x3 "Image at" grid places the image in the new canvas (like
  Canvas Size in Photoshop); changing it keeps the added width and height.
- The four pixel boxes (Left, Right, Top, Bottom) are bound both ways to the
  editor. Typing values that match a preset selects that preset; any other
  change selects Custom.
- Readout: "New size: 2432 x 1440 px (+256 right)"; with nothing added:
  "New size: 1024 x 768 px. Drag an edge outward to add space." Generate with
  nothing added shows that line as a warning instead of closing.
- Prompt is optional: placeholder "Leave empty to continue the scene". The
  dialog no longer pre-fills the newest Fill prompt from the history (only the
  last Expand prompt GIMP remembers for the procedure). Avoid, Model and
  Variations are visible; Advanced holds only Seed.
- The procedure arguments are unchanged (left, top, right, bottom in pixels,
  0 to 4096), so NONINTERACTIVE calls behave as before.

Layout:

```
+-- Generative Expand -----------------------------------------+
| +----------------------------------------------------------+ |
| | Leave empty to continue the scene                        | |  4 lines, fixed
| +----------------------------------------------------------+ |
| [Recent prompts]          Enter generates, Shift+Enter adds a line
|      Avoid [....................................]            |
|      Model [active model v]          Variations [1 -+]       |
| +----------------------------------------------------------+ |
| |        - - - - - - - - - - - - - - - - - - - -            | |
| |       |+256 |   [ image thumbnail ]   | +256 |           | |  editor 560 x 340
| |        - - - - - - - - - - - - - - - - - - - -            | |  (handles on frame)
| +----------------------------------------------------------+ |
| Ratio [Original][1:1][4:5][5:4][3:2][2:3][16:9][9:16][Custom]|
| Image at [][][]    Left [256 -+]  Right  [256 -+]            |
|          [][][]    Top  [  0 -+]  Bottom [  0 -+]            |
|          [][][]                                              |
| New size: 1536 x 768 px (+256 left, +256 right)              |
| > Advanced                       (Seed)                      |
|                                        [Cancel] [Generate]   |
+--------------------------------------------------------------+
```

### Text to Image

Same pattern: prompt, Avoid, Model, Variations, Size, Result as visible;
Advanced holds only Seed.

### Texts

Every text the generation dialogs, the Settings window, the variations picker
and the progress window show now comes from `stable_boy/ui_text.py`
(the Settings field tables `GENERAL_FIELDS`, `ADVANCED_FIELDS`,
`CONNECTION_FIELDS` moved there; `dialogs.py` keeps the old names as
aliases). Window titles are unchanged, so the screenshot script still finds
the windows. Tests in `tests/test_ui_text.py` check that every dialog text is
a single line of at most 100 characters, does not start with "Tip" or
"Note:", and that the generation-dialog texts contain none of: cfg, sampler,
scheduler, denoise, node, workflow, checkpoint, latent, vae, comfy.

## Pure functions and tests

`stable_boy/ui_expand.py` (no `gi` needed for these; `tests/test_ui_expand.py`,
27 tests):

| Function | Does |
|---|---|
| `Margins` (`from_dict`, `as_dict`, `canvas`, `is_empty`, `replace`) | the four margins, clamped to 0..4096 |
| `clamp_margin`, `clamp_margins`, `snap` | limits and 8 px snapping (halves round up) |
| `split`, `anchor_margins`, `reanchor`, `anchor_of` | 3x3 anchor math |
| `preset_ratio`, `target_canvas`, `preset_margins`, `matching_preset` | ratio presets |
| `fit_view`, `view_at`, `handle_points` | thumbnail and frame on screen |
| `hit_test` | which handle (corners before edges) is under the pointer |
| `drag_margins` | margins after dragging a handle by (dx, dy) screen px |
| `ExpandState` | margins, preset and anchor kept consistent; one listener |

`stable_boy/ui_text.py`: `selection_status`, `expand_status`,
`txt2img_status`, `prompt_free_warning`, `anchor_tip`, `picker_heading`
(tests in `tests/test_ui_text.py`).

## Test hooks (SB_TEST_UI_FILE JSON keys)

Existing keys keep working (`autoclose`, `advanced`, `mode`, `values`,
`type`, `press`, `click`, `open_recent`, `dry_run`, `fake_variations`,
`progress_demo`, `picker_steps`, `settings_*`). New:

- `expand`: `{"margins": {...}, "preset": "16:9", "anchor": "left",
  "drag": [["right", 60, 0], ["bottom-left", -40, 30]], "hover": "top-right"}`,
  played 0.5 s after the dialog opens, in that order. `drag` goes through the
  same code as a mouse drag (screen pixels, frozen scale, snapping).
- `advanced_steps`: `[[1.6, true], [3.1, false]]` opens and closes Advanced.
- `dialog_dump` + `dialog_out`: seconds at which the dialog appends its window
  size and position, the prompt box rectangle, Advanced, the status and
  warning texts and (Expand) margins, preset, anchor, canvas, spin values and
  editor size to a JSON lines file.
- `prompt_free`: an active model name; the dialog behaves as if that model
  only removed objects (removal-model note).

## What to verify visually (screenshot run)

`tests/gimp_batch_ui_screenshots.py` has new cases (all with `dry_run`, so
nothing is generated even if Generate were answered). Its report
(`ui-screenshots-report.json`) includes `dialog_state` with the dumps.

1. `fill-advanced-toggle` (`fill-dialog-toggle.png`, `-toggle-advanced.png`,
   `-toggle-closed.png`): prompt box height and window width identical in all
   three dumps; window `position` y identical; the window is taller only in
   the middle one; Advanced shows only Change amount and Seed; the closed one
   is as short as the first.
2. `fill` / `fill-advanced` / `fill-remove`: one line per text, nothing
   wrapped, no field hints; the Remove object page has the same height as the
   prompt box; Recent prompts disabled there.
3. `fill-removal-note`: one orange line naming MAT.
4. `fill-no-selection`: orange no-selection line.
5. `fill-empty-prompt`: orange "Type a prompt, or choose Remove object.";
   dialog still open.
6. `expand-default`: thumbnail of the test scene, dashed frame, shaded side
   bands with "+256", eight white handles, preset Custom, anchor centre,
   readout "New size: 1536 x 768 px (+256 left, +256 right)" (test scene
   1024 x 768), placeholder visible in the empty prompt.
7. `expand-zero`: frame on the image border, readout ends with "Drag an edge
   outward to add space."
8. `expand-16-9-left`: preset 16:9 and anchor middle-left highlighted, only a
   right band (+342), readout "New size: 1366 x 768 px (+342 right)".
9. `expand-9-16-center`, `expand-1-1-bottom-right`, `expand-original`: preset
   and anchor buttons highlighted as named, bands where expected.
10. `expand-drag`: from zero; at the expected view scale (360 / 1024 =
    0.35 for the 1024 x 768 test scene) the right drag gives +168 and the
    corner drag +112 left and +88 bottom (all snapped to 8 px); the spins and
    readout equal the dump.
11. `expand-hover`: top-right handle drawn blue.
12. `expand-huge` (4096 left and right): view zoomed out, the whole frame
    inside the editor, the image small in the middle.
13. `expand-advanced-toggle`: as 1, for Expand; Advanced shows only Seed.
14. `expand-generate-zero`: orange "Drag an edge outward to add space.";
    dialog still open.
15. All dialogs: window width 640 px (no widening from the Ratio row or the
    Model row); the anchor buttons readable in GIMP's dark theme (checked one
    blue).

Also to try by hand once (not scriptable here): real mouse drags on every
handle, the resize cursors, and typing into a pixel box then pressing Enter.

## Not verified

- No GTK code was executed: the system Python has no `gi`, so the GTK smoke
  test was skipped. Only the GTK method names used were confirmed to exist in
  GIMP's bundled Python (attribute lookups, no window). A smoke script that
  builds the dialogs without showing them is in
  `C:\AI\overnight-scratch\day\dialogs\gtk_smoke.py` (not run).
- Font metrics: the 4-line prompt height is computed from the theme font at
  construction; whether it shows exactly four lines in GIMP's theme needs
  the screenshot.
