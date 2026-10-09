# Overnight hardening report, 2026-10-09

Branch `gimp3-port`, 00:03 to about 06:30 local time. Nothing was pushed; every
change is a local commit on top of `55742fe`. Unit tests: 111 at the start,
233 at the end, all green at every commit. Ruff check and format are clean
tree-wide. No attribution lines, tool names or emojis in commits, code or docs
(checked with grep over the whole tree and `git log --format=%B`).

## Verdict in one paragraph

The plug-in is in much better shape than last night: every reproducible defect found tonight (about 30) is fixed and verified in a real GIMP 3.2.6, the dialogs are
redesigned and screenshot-verified, 25 of 25 robustness scenarios pass with
plain-words messages, performance is measured and improved, and the README,
changelog, CONTRIBUTING, security notes and CI workflow are release quality.
It is ready to push as **2.0.0-beta.1** with one caveat that the README and
CHANGELOG already state: the Fast tier (SD 1.5 inpainting) often ignores the
prompt on featureless regions and small selections, and some Quality-tier
results on structured backgrounds come back flat. Those are model limits plus
a few open plug-in weaknesses listed below, not crashes or data loss. My
judgment: push it as a beta today; do not call it 2.0.0 final until the Fast
tier either gets a better default model (LaMa or a stronger SD 1.5 inpaint
checkpoint) or the dialog steers prompted fills to the Quality tier.

## Things only you can decide or resolve

1. **Your own GIMP instance (pid 13040, started 2026-10-08 15:40) ended
   between 00:04 and 00:34.** No lane issued a kill against it (I searched
   every lane transcript for Stop-Process, taskkill and the pid). All lanes
   used `--new-instance` and isolated profiles. If you closed it before going
   to sleep, ignore this. If not, check whether it crashed (GIMP 3.2.6 crashed
   twice in a fresh test profile right after its online update check; setting
   `(check-updates no)` in gimprc stopped that).
2. **Two `python.exe` processes (pids 38560 and 20388, started 04:29 under a
   `cmd.exe`) belong to another user account** (owner and command line not
   readable from this session). They are not from any lane and were left
   alone.
3. **Evidence size.** `docs/evidence/overnight-2026-10-09` is about 72 MB
   (photographic JPEGs, 64 synthetic cases, GUI run captures). The `.git`
   directory is about 85 MB. If you want a lighter public repo, squash or drop the evidence
   folders before the first push; the quality ledger and the READMEs are the
   part worth keeping. Nothing is pushed yet, so history can still be
   rewritten.
4. **SECURITY.md points to GitHub private vulnerability reporting**, which
   only works after you enable it in the repository settings.
5. **FLUX and Qwen weights were not downloaded** (as instructed). Those tiers
   are described as unverified in the docs.

## What was tested

### Synthetic edge-case matrix (64 cases, `tests/gimp_batch_matrix.py`)

Every case ran in `gimp-console-3.2.exe` with `RunMode.NONINTERACTIVE`,
isolated profile, evidence per case (batch command, report.json, before and
after PNG, crops, plug-in log). Visual scores are in
`docs/evidence/overnight-2026-10-09/quality-ledger.md`.

| Pass | Score (seams, colour, blur, artifacts, mask edge, content; 1 to 5) |
|---|---|
| 00:51, before fixes, 55 cases | 5 PASS, 27 PASS-WITH-NOTES, 23 FAIL |
| 02:05, after the first fix round, 64 cases | 11 PASS, 31 PASS-WITH-NOTES, 22 FAIL |
| 04:40, after the A/B re-runs | 11 PASS, 33 PASS-WITH-NOTES, 20 FAIL |

The 20 remaining FAILs split as follows.

- Model behaviour (14): SD 1.5 inpainting ignores "red brick wall" on flat
  synthetic sky, on 20 px selections and at some seeds (img-1024, img-256,
  img-aspect-tall, img-unsaved-new, sel-corner-topleft, sel-edge-right,
  sel-edge-top, sel-edge-left seeds 7 and 99, sel-multi-disjoint,
  sel-tiny-20px and its seeds 7 and 99, sel-tiny-20px-quality). The Quality
  tier (SDXL + Fooocus, Juggernaut) draws the brick at the same positions; the
  ablation in `sd15-prompt-ablation/` shows no graph step is to blame.
- Plug-in weaknesses still open (6): sel-edge-bottom, sel-feathered,
  sel-layer-offset, sel-layer-in-group, img-rotated-layer (washed-out fine
  mosaic on offset or grouped layers), img-aspect-wide (a 16:1 strip yields a
  768x240 working image that SD 1.5 extends as a dark slab).

Everything structural passes: nothing changes outside the selection in any
case, layer offsets and sizes are right, hidden layers do not leak, fixed seeds
are pixel-deterministic, random seeds differ, and the three error cases
(no selection, indexed image, missing model) leave the image untouched with a
plain message.

### Real photos (28 cases, six CC0 or public-domain photos)

Sources and licenses: `docs/evidence/overnight-2026-10-09/photos-README.md`
(five Wikimedia Commons CC0 photos, one NASA portrait). Remove, replace and
extend on each; both tiers for replace.

| Verdict | Cases |
|---|---|
| PASS (8) | text-remove, face-replace, landscape-replace, product-replace, face-replace-fast, landscape-replace-fast, product-replace-fast, product-extend |
| PASS-WITH-NOTES (10) | face-remove, fabric-remove, landscape-remove, architecture-remove-quality, fabric-replace, face-extend, landscape-extend, architecture-extend, text-extend, landscape-extend-all-fast |
| FAIL (10) | architecture-remove (MAT cannot rebuild a facade), product-remove (step at the cup bottom), landscape-remove-quality (Juggernaut invents a shed), architecture-replace and architecture-replace-fast (flat tinted rectangle, no window), text-replace and text-replace-fast (word removed, no arrow or garbage letters), fabric-replace-fast (soft rectangle), fabric-extend (visible seam), landscape-extend-all (content now generated on all sides after the fix, but the left strip keeps a hard seam) |

### Robustness (26 scenarios, `tests/gimp_batch_robustness.py`)

All pass with a plain message that names a next step, the image untouched and
no process left behind: backend folder missing, config missing, config corrupt
(moved aside to `config.json.corrupt-<time>`), auto-start off, port in use
(8188 and a second port, HTTP-500 and silent dummies), extra server argument
starting with `-`, backend crash mid-job, ComfyUI already running externally
(used and not stopped), missing model file (backend stopped and running), out
of VRAM (could not be forced on this card even with 6.5 GiB held by another
process: ComfyUI offloads; the message path is unit-tested), two GIMP
instances at once and the first one exiting, cancel while starting, uploading,
sampling and downloading, interrupt from outside GIMP, GIMP killed
mid-generation (ComfyUI gone in 1.8 s), idle timeout (shutdown 60 s after the
last use), corrupt `.part` download (retried from zero), network off for a
download, fresh profile install and uninstall with `install.ps1` and
`install.sh` (Windows, Git Bash and WSL). Disk-nearly-full is unit-tested only
(no free-space override exists in the code).

### UX

The Fill, Expand and Text to Image dialogs are now plain GTK dialogs: mode
switch "Fill with a prompt" / "Remove object", large multi-line prompt box with
placeholder, Recent prompts (last 20, persisted), one blue Generate button
(Enter generates, Shift+Enter newline, Escape cancels), a collapsed Advanced
section (model, avoid, variations, change amount, seed), a status line with
the selection size, and the shortcut hint (Edit > Keyboard Shortcuts, search
"Generative Fill", suggested Shift+Ctrl+G). A variations picker shows
thumbnails after a multi-variation run (click to keep one, Keep all, Discard
in one undo step). Settings has a short General tab with Browse, Start backend
automatically, idle timeout, progress window, a Check backend button whose
result shows inside the dialog, and the technical options in collapsed
sections; the Models tab lists downloaded models first with one state button
per row and shows the token field only for gated models. Every error ends
with a next step. 17 screenshots in `docs/screenshots/` were inspected by the
lane that took them and re-verified in a second GUI run after the review
edits (20 scripted dialog cases, all clean). The performance lane found that
the progress window had been created but never marked visible by Windows
inside a GUI GIMP session; that is fixed and the README GIF shows it live.

### Performance (`docs/performance.md`, raw data in `evidence/.../perf/`)

| Measurement (RTX 4070 Laptop 8 GB, 20 steps, 2048 px photo) | Value |
|---|---|
| Cold start, ComfyUI launch to ready | 31 to 38 s (first result at 45 to 55 s) |
| Warm fill, SD 1.5, 512 / 1024 / 2048 px | 8.4 to 8.7 / 10.8 to 10.9 / 10.8 to 10.9 s |
| Warm fill, SDXL + Fooocus, 512 / 1024 / 2048 px | 20.6 to 22.1 / 24.4 to 28.1 / 22.3 to 23.9 s |
| Warm fill, Juggernaut XL v9, 512 / 1024 / 2048 px | 22.8 to 23.2 / 25.1 to 25.3 / 24.6 to 24.7 s |
| Remove, MAT, 512 / 1024 / 2048 px | 2.9 to 3.3 / 5.1 to 5.7 / 5.0 to 5.5 s |
| 20 consecutive SD 1.5 fills | GIMP 355 MB flat, ComfyUI 6656 to 6663 MB, VRAM flat at 2292 MiB; wall time 11.1 to 11.9 s (GPU at 77 C) |
| GIMP main loop during a fill | longest stall 44 to 60 ms (limit 100 ms); 499 of 499 window pings answered |
| After optimizations, whole call at 1024 px | SD 1.5 10.8 to 9.1 s; Juggernaut 25.2 to 19.5 s |

## What was fixed (commit hashes on gimp3-port)

- `1409ecc` line endings normalized (`.gitattributes`); the 44 "modified"
  files at the start were CRLF noise.
- `db99bb5`, `3a6692b`, `10111d5`, `f837afa`, `41ebab6`, `36da380`, `b29add4`
  the dialog redesign, variations picker, Settings and Models tab, progress
  window focus and placement, error wording (merged from `ux-redesign`).
- `1b15b2c` security and installers: token sent only to https huggingface.co
  and never on redirects; catalog paths must be plain names; node installs
  validate URL, folder and full commit; supervisor tasks validated against the
  catalog; pid reuse checks; log redaction; owner-only config on POSIX;
  resumable downloads reject bad offsets; lama-big sha256; `install.ps1`
  -ProfileDir/-RemoveConfig; `install.sh` for Linux, Flatpak and macOS with
  --uninstall; pyproject ruff config; GitHub Actions CI (file only);
  CONTRIBUTING.md; SECURITY.md; docs/security.md.
- `b3637b0` corrupt config moved aside and reported; port probe before
  launching ComfyUI; real elapsed time in start failures; ANSI stripped from
  log tails; `--extra-args=` as one argument; supervisor stderr kept; every
  error class ends with a next step.
- `a4619c3` matrix findings: no-selection refusal (it used to regenerate the
  whole image), Text to Image layer size and new-image target in batch,
  indexed images refused, transparent pixels no longer sent as black, visible
  channels no longer baked into the crop, neutral pre-fill and tighter context
  for prompted SD 1.5 fills, colour matching skipped without reference pixels,
  layer-mask grow limited to the feather, missing ComfyUI folder reported
  before any model check, non-interactive runs never open the progress window.
- `6f45f45` robustness: crash-mid-job message, one supervisor per profile with
  multi-GIMP watchers, cancel at every phase (3.5 s instead of 23 s while
  starting), corrupt `.part` retry, network and disk messages.
- `b0251ad`, `fea5625` picker is one undo step, GLib timer cleanup, Models tab
  shows errors, docstrings and type hints, docs corrections.
- `2df1fe8` real photos: MAT works at 512 px (no ghosting), SDXL tiers use the
  border pre-fill (no framed pictures painted into the selection), one-sided
  expand uses a local context band, uploaded PNGs padded so ComfyUI 0.39's
  PyAV loader stops failing on small masks, model display names in messages.
- `d03efce`, `39f3dcc`, `7061967` performance: zlib level 1 PNG encode,
  content-named uploads (re-rolls skip preparation), 0.5 s port probe, the
  progress window actually shown, timing lines in the log, README GIF and
  numbers.
- `d4bb49d` SD 1.5 large-context working size 640 px (brick texture returns
  on img-3000 and img-6000); sequential all-sides expand for SDXL tiers.
- `d94b27b` Discard after Expand restores the canvas; the variations picker
  is shown explicitly; scripted dialog test hooks.
- `fab0c07`, `be74bc2`, `ffebd4d`, `047b358`, `3bb8ed2`, `3e1cc42` docs,
  changelog 2.0.0-beta.1, version bump, ledger updates, evidence index.

## Still open

- Fast tier prompt adherence on featureless regions and tiny selections
  (model behaviour; documented in README Known limitations and CHANGELOG).
- Six plug-in-side synthetic failures listed above (offset or grouped layer
  texture, 16:1 strips, feathered and bottom-edge selections at seed 1234).
- Quality tier: flat tinted rectangle on the facade and nothing on the sign
  with the border pre-fill; all-sides expand on SDXL tiers now generates
  content but the first (left) strip keeps a hard seam; if a sequential expand
  pass fails, earlier passes stay applied.
- MAT cannot rebuild structured backgrounds; empty-prompt removal on a
  generation model can invent objects.
- Out of VRAM and disk nearly full are covered by unit tests only.
- Not run live: A1111 backend, FLUX, Qwen, LaMa (downloaded for the corrupt
  `.part` test and removed again), Linux or macOS installs on a real GIMP.

## GUI end-to-end lane (real generation in a GUI GIMP, 04:44 to 05:22)

Evidence: `docs/evidence/overnight-2026-10-09/gui-e2e/`.

| Task | Result |
|---|---|
| Fill with 4 variations (Juggernaut, "hot air balloon") | pass: progress window visible on screen in all 80 samples (IsWindowVisible), picker appeared, clicking thumbnail 2 left only variation 2 visible, one Edit > Undo removed the whole group and the image was pixel-identical to before |
| Expand right 256 px, 2 variations, then Discard | pass after a fix: the canvas returns to 1920x1440 with the original layer only, pixel-identical; one Undo brings the expansion back |
| Settings: Check backend, Models tab, Set active | pass: "Backend OK: 3 models, inpaint nodes installed." appeared in the dialog after 3 s; installed models listed first with Active / Set active / Downloaded / Download buttons; Set active updated config.json and reordered rows; nothing downloaded |
| Remove object on a product photo (cup handle, MAT) | pass: 9.3 s, "Object Removal" layer, handle gone, cup wall and saucer continue, slightly soft patch at the rim |

Fixed in `d94b27b`: Discard after Generative Expand now resizes the canvas
back inside the same undo group (it used to leave the canvas enlarged); the
variations picker window had the same Windows visibility problem as the
progress window and is now shown explicitly. Small observations left open: a
scripted Return in Remove mode does not generate (clicking Generate does); the
Fill dialog reopens in the mode last used; the progress window's first status
line says "0 s" while the elapsed counter below already shows 2 s.

## Processes and cleanup

- All GIMP instances, supervisors and ComfyUI processes started by the lanes
  have exited; port 8188 is closed; VRAM is at its 11 MiB idle level; the GPU
  lock file is gone. Confirmed again at the end of the run.
- Scratch is at `C:\AI\overnight-scratch` (test profiles, runs, photos,
  frames, about a few GB); safe to delete.
- Your real GIMP profile (`%APPDATA%\GIMP\3.2`) and its `stable-boy` folder
  were not touched; every lane used `GIMP3_DIRECTORY` profiles under scratch.
  The plug-in junction in your profile still points at the checkout, so the
  next GIMP start loads the new code and the new dialogs.

## Next steps for you

1. Open GIMP, Filters > AI > Generative Fill on a photo, and try Fill, Remove
   and Expand with the new dialogs; Settings > Check backend; Models tab.
2. Read `docs/reports/overnight-2026-10-09.md` (this file), the README and
   the quality ledger's "Failures and concerns" and "Real photos" sections.
3. Decide about the evidence size (see above) and whether to keep the
   `ux-redesign` branch (merged; safe to delete).
4. When you are happy: `git push -u origin gimp3-port`, then enable private
   vulnerability reporting in the repository settings, and watch the first CI
   run (`.github/workflows/ci.yml`, Python 3.10 and 3.12, ruff plus unittest).
5. Optional before the final 2.0.0: download LaMa (`install.ps1 -Model
   lama-big`) and make it the default removal model, and consider steering
   prompted fills to the Quality tier by default when an SDXL checkpoint is
   installed.
