# Screenshots

Captured in GIMP 3.2.6 on Windows 11 with an isolated profile by
`tests/gimp_batch_ui_screenshots.py`. No generation, backend check or download
ran for them: the progress window and the variations picker are driven by
test hooks (scripted steps, tinted copies of the selection as stand-in
variations), so the preview and thumbnails show the test scene, not a result.

| File | Shows |
|---|---|
| `filters-ai-menu.png` | `Filters > OpenFill` with Generative Expand..., Generative Fill Settings..., Generative Fill..., Stop AI Backend and Text to Image... (GIMP sorts them alphabetically). |
| `fill-dialog.png` | Generative Fill in Fill with a prompt mode: the pre-filled prompt "a red door with brass handles", Recent prompts, the Enter / Shift+Enter hint, collapsed Advanced, "Selection: 260 x 200 px in a 1024 x 768 px image" and the shortcut tip. |
| `fill-dialog-advanced.png` | The same dialog with Advanced open: Model, Avoid, Variations, Change amount, Seed. |
| `fill-dialog-recent-prompts.png` | The Recent prompts menu. |
| `fill-dialog-remove.png` | Remove object mode: "Erases the selection and continues the background. No prompt needed: just press Generate." |
| `fill-dialog-removal-model-note.png` | The note shown when the active model only removes objects (MAT, LaMa). |
| `expand-dialog.png` | Generative Expand: optional prompt, margin boxes around "your image", Wider / Taller / All sides. |
| `text-to-image-dialog.png` | Text to Image: prompt, Size, Result as. |
| `progress-window-start.png` | Progress window at the first sampling step ("Generating, step 1 of 25", 9 %), before a remaining-time estimate exists. |
| `progress-window.png` | Progress window during sampling: "Generating, step 12 of 25", 48 %, "Elapsed 0:09, about 0:10 left", preview, Cancel. |
| `progress-window-cancel-clicked.png` | Progress window after Cancel was clicked. |
| `variations-picker.png` | "3 variations are ready": three thumbnails, Discard, Keep all, Keep selected. |
| `settings-general.png` | Settings, General tab: AI backend folder with Browse..., Start backend automatically, Idle timeout (minutes), Show the floating progress window, Check backend, and the collapsed Advanced generation and Connection and troubleshooting sections. |
| `settings-general-advanced.png` | The General tab with the collapsed sections open. |
| `settings-models.png` | Settings, Models tab: downloaded models first, the active model tagged, one primary button per row (Active, Set active, Downloaded), Open models folder. |
| `settings-models-token.png` | The Models tab scrolled to "AVAILABLE TO DOWNLOAD" with the gated FLUX.1 Fill GGUF entry, the Hugging Face token field, Save token and Get a token. |

Planned: `generative-fill.gif`, a screen recording of a complete fill (select,
prompt, progress, result layer). The README uses `fill-dialog.png` as its
hero image until the recording is committed.
