# GUI end-to-end run (2026-10-09)

Real generations in a GUI GIMP 3.2.6 (`gimp-3.2.exe --new-instance`, isolated
test profile, Windows 11, RTX 4070 Laptop, ComfyUI started hidden by the
plug-in's supervisor). Every operation went through the INTERACTIVE procedure
and its real dialog; only the user's input was scripted with the plug-in's
test hooks (`SB_TEST_UI_FILE`):

- `type` / `press`: the prompt is typed into the prompt box and Return is
  delivered through GTK's key handling (Enter = Generate).
- `values`: start values of the dialog fields (Variations, Model, Seed,
  Remove), as if set under Advanced. Needed because an INTERACTIVE run starts
  from GIMP's last-used values, not from the values a script puts in the config.
- `click: generate`: clicks the Generate button (Remove mode, see below).
- `picker_steps`: one step per second in the variations picker; a number
  clicks that thumbnail (`Gtk.Button.clicked`), `keep` / `discard` press the
  buttons.
- `settings_steps`: presses Check backend, switches to the Models tab, presses
  a row's primary button and dumps the label texts and model rows.

Driver: `gui_e2e_driver.py` (this folder), run as

    set GIMP3_DIRECTORY=C:\AI\overnight-scratch\gimp-profile-test
    set SB_TEST_UI_FILE=C:\AI\overnight-scratch\gui-e2e\ui-hooks.json
    set SB_E2E_OUT=C:\AI\overnight-scratch\gui-e2e\run5
    set SB_E2E_TASKS=undo-probe,fill,expand
    gimp-3.2.exe --new-instance --no-splash --batch-interpreter python-fu-eval ^
        -b "exec(open(r'...\gui-e2e\gui_e2e_driver.py').read())"

While a procedure runs, a PowerShell watcher enumerates every top-level window
of GIMP and its child processes every 0.5 s whose title starts with
"Stable Boy - " or "Choose a variation" and logs `IsWindowVisible`, `IsIconic`
and the rect per HWND (`windows.jsonl`); the first time a progress window is
visible its screen area is copied with `CopyFromScreen` (what is on the
monitor, not `PrintWindow`). Dialog and picker shots use the screenshot
driver's `PrintWindow` helper, which only finds visible windows. Edit > Undo
is the real menu: the image window is brought to the front (pid checked), then
Alt+E and U are typed. Composites (`before.png`, `after-*.png`) are flattened
exports downscaled to 1024 px.

Runs: run1 (before the fixes below), run2 (settings, remove), run5 (fill,
expand, undo). Raw output in `C:\AI\overnight-scratch\gui-e2e\run1..run5`.

## Results

| Task | Case folder | Result |
|---|---|---|
| 1. Fill, 4 variations, pick 2, undo | `fill-4-variations/` | pass |
| 2. Expand, Discard | `expand-discard/` | pass after the fix |
| 3. Settings: Check backend, Models, Set active | `settings/` | pass |
| 4. Remove object | `remove/` | pass |
| extra: Edit > Undo on a 1-variation fill | `undo-probe/` | pass |

### 1. Generative Fill with 4 variations (`fill-4-variations/`)

`landscape.jpg` (1920 x 1440), rectangle selection 480 x 300 at (420, 90) in
the sky. Dialog: Advanced open with Model Juggernaut XL v9, Variations 4,
Seed 1234 (`fill-dialog.png`, taken 1 s after opening, so the box still shows
the pre-selected last prompt "a small bird"); at 1.5 s "hot air balloon" was
typed and Return pressed. Log: `queued prompt ...
(timeout 316s, 25 steps x 4)`, sampling 35.2 s, `fill: done, seed=1234, 4
layer(s)`; 64 s for the whole call including a cold backend start (22 s).

- Progress window: HWND 7473006 "Stable Boy - Generative Fill",
  `IsWindowVisible` = True in all 80 samples from 05:16:38 to 05:17:29, not
  iconic, rect x 1782..2184, y 984..1441 growing to 1542 (the monitor is
  2560 x 1600). `progress-window-on-screen.png` is the screen copy: "Generative
  Fill with Juggernaut XL v9", "Starting the AI backend (first time takes about
  a minute), 0 s", Cancel. The plug-in log says `progress window: 25 preview
  frame(s) shown, closing after success (native window had to be shown
  explicitly)`, i.e. the d03efce workaround is what makes it visible.
- Picker: "Choose a variation - Generative Fill" appeared 0.6 s after the
  progress window closed, `IsWindowVisible` = True (16 samples). Text "4
  variations are ready. Click one to see it in the image." with Variation 1..4
  (`picker-opened.png`); after the click on thumbnail 2 the second thumbnail is
  selected (`picker-after-click-2.png`), then Keep selected.
- Layer tree after the pick: group "Generative Fill: hot air balloon" with
  "(1)" hidden, "(2)" visible, "(3)" hidden, "(4)" hidden, then "Background".
  Only variation 2 is visible (`after-pick-2.png`, `gimp-window-after-pick-2.png`).
- One Edit > Undo removes the whole operation: the tree is back to
  "Background" only and the composite is pixel-identical to `before.png`
  (`after-one-undo.png`). The picker's thumbnail previews left no undo steps of
  their own.
- The PDB has no undo procedure (only gimp-image-undo-group-start/-end,
  -freeze, -thaw, -enable, -disable, -is-enabled), hence the menu keys.

### 2. Generative Expand, then Discard (`expand-discard/`)

Same image (after the undo), right 256 px, prompt "meadow", 2 variations,
Juggernaut XL v9. Log: `expand: margins=(0, 0, 256, 0) canvas=2176x1440`,
`25 steps x 2`, `expand: done, seed=1234, 2 layer(s)`. The picker
("2 variations are ready.", `picker.png`) opened with the canvas at
2176 x 1440; the scripted step pressed Discard.

- After Discard: 1920 x 1440 and the tree is "Background" only, as before the
  expand; the composite is pixel-identical to `before.png` (`after-discard.png`,
  `gimp-window-after-discard.png`). `report.json`: `"restored": true`.
- One Edit > Undo after Discard brings the whole result back: 2176 x 1440 with
  the group "Generative Expand: meadow" ((1) visible, (2) hidden)
  (`gimp-window-after-undo-of-discard.png`).
- The fix below was in place for every run of this lane, so the old
  behaviour (canvas left enlarged after Discard until Edit > Undo twice, as
  noted in the UX notes) was not reproduced here.

### 3. Settings (`settings/`)

Settings opened INTERACTIVE with the backend already running (from task 2 of
the same GIMP session). Label texts read from the dialog (`settings-steps.jsonl`):

- before: "Press Check backend to see that the AI backend starts and answers.
  The first start can take about a minute."
- 3 s after pressing Check backend: "Backend OK: 3 models, inpaint nodes
  installed." (`2-after-check-backend.png`). "3 models" counts the checkpoint
  files ComfyUI lists (SD 1.5 inpainting, SDXL base, Juggernaut XL v9); MAT and
  the Fooocus patch live in other model folders.
- Models tab (`3-models-tab.png`), rows in list order under DOWNLOADED:
  MAT Places512 "Active" (insensitive) "Active: used by the Generative Fill
  dialogs.", SD 1.5 Inpainting "Set active", SDXL base "Set active", Fooocus
  Inpaint Patch "Downloaded" (insensitive, helper file), Juggernaut XL v9
  "Set active"; then AVAILABLE TO DOWNLOAD: flux1-fill-dev-gguf-q4 and
  flux1-fill-dev (both "Download", "Not downloaded. Needs a Hugging Face token
  (see below)."), qwen-image-edit-2511-gguf-q4 and lama-big ("Download", "Not
  downloaded.").
- Set active on SD 1.5 Inpainting: config.json `active_model` changed from
  mat-places512 to sd15-inpainting at 05:03:41 (file polled every 0.3 s); the
  row moved to the top with "Active", MAT shows "Set active", status line "Stable
  Diffusion 1.5 Inpainting is now the active model." (`4-...png`).
- Set active on MAT Places512: `active_model` = mat-places512 at 05:03:46; MAT
  back on top with "Active" (`5-...png`). Nothing was downloaded. The dialog
  was then closed with Cancel (autoclose); Set active is saved immediately, so
  config.json keeps the last choice.

### 4. Remove object (`remove/`)

`product.jpg` (1280 x 853) has no spoon; the cup handle was removed instead
(selection 215 x 185 at (155, 335)). Remove mode, Generate clicked
(`remove-dialog.png`). Log: `fill: Remove object -> using mat-places512`,
sampling 0.67 s, `fill: done, seed=1234, 1 layer(s)`; 9.3 s for the call. The
progress window "Stable Boy - Object Removal" was visible (True in all 7
samples). Layer "Object Removal" above "Background". Result
(`crop-before-after.png`): the handle is gone, the cup wall and saucer
continue plausibly; a slightly soft patch where the saucer rim meets the cup on
the left.

## Fixes made during this run

1. Expand Discard restores the canvas (`gimp-stable-boy.py`: `run_expand`,
   `_canvas_state`, `_canvas_restore`, `_after_insert`, `_pick_variation`).
   `run_expand` records the canvas size and the offsets of an existing layer
   before the expand and after it; `_canvas_restore` turns the difference into
   `image.resize(old_w, old_h, -dx, -dy)` arguments, which `_pick_variation`'s
   Discard applies inside the same undo group that removes the variations. One
   Discard leaves the image as it was; one Edit > Undo brings the whole expand
   back. Unit test: `tests/test_ui_text.py` `ExpandDiscardRestoreTests`.
2. The variations picker was not visible on screen (`ui_picker.py`:
   `_ensure_visible`, `VariationPicker._recheck_visible`). In run1 the picker
   window existed with `IsWindowVisible` = False in every sample
   (`expand-discard/before-fix-run-windows.jsonl`): the same GIMP 3.2.6 plug-in
   process problem d03efce fixed for the progress window. After `show_all()`
   (and again 200 ms later) the picker's native window is shown with
   `ShowWindow(SW_SHOW)` and brought to the front when it is not WS_VISIBLE.
   Run2 and run5: visible in every sample.
3. Test hooks for this run: `values` and `click` (generation dialog,
   `dialogs.run_generation_dialog`), `picker_steps` now also reach the picker
   after a real generation (`_after_insert`), `settings_steps` /
   `settings_out` (`dialogs._play_settings_step`).

## Observations, not fixed

- A scripted Return in Remove mode did not generate (run1: the dialog stayed
  open until autoclose); the prompt box is hidden in that mode and the key went
  to whichever widget had the focus. A real key press was not tried; the
  Generate button works.
- An INTERACTIVE run starts from the last-used values: after a Remove run the
  next Generative Fill opens in Remove mode.
- `Gimp.file_load` from a plug-in leaves the image's undo disabled (File > Open
  enables it). The driver enables undo after loading; without that Edit > Undo
  stays greyed out (runs 1 to 4).
- The progress window grows downward as the preview appears; at its tallest
  its rect ends at y 1601 on a 1600 px tall monitor (1 px).
- The progress window's first status reads "..., 0 s" while "Elapsed 0:02" is
  shown below it.
