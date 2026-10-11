# UI verification (GUI GIMP, isolated profile, no generation)

Captured with tests/gimp_batch_ui_screenshots.py against the ui-fixes tree.

| Request | Status | Screenshot |
| --- | --- | --- |
| 1 Expand editor (drag handles, ratio presets, anchor grid, pixel boxes) | Works as designed: handles and drag, all ratio presets, anchor grid, margin boxes and live size line | expand-editor-sheet.png, expand-presets-sheet.png, expand-extremes-sheet.png |
| 3 Fill dialog layout (prompt, Recent prompts, Avoid, Model, Variations visible; change amount and seed under Advanced) | Works | fill-dialog-sheet.png |
| 4 Clutter removed (warning, selection size, removal-model note, shortcut hint) | Works; wording is tight | fill-dialog-sheet.png, fill-modes-sheet.png |
| 5 Models tab flat list, no hover highlight | Works (hover itself is not capturable in a still) | models-picker-settings-sheet.png |
| 6 Prompt box fixed at 4 lines, dialog grows down only | Confirmed by measured window geometry: prompt box and window position identical with Advanced open and closed, window height only grows | fill-dialog-sheet.png |
| Variations picker, Settings dialog | Look right | models-picker-settings-sheet.png |

Notes: a few captures in a harness run come out black or time out (screenshot
timing, not the dialogs); those cases were re-run and are included. A 4096 px
margin per side is still accepted by the editor (9216 px wide result).
