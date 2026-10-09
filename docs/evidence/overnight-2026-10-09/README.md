# Evidence index, overnight run 2026-10-09

Evidence for Stable Boy 2.0.0-beta.1, recorded in GIMP 3.2.6 on Windows 11
(RTX 4070 Laptop, 8 GB) with ComfyUI 0.39.0. Every case was run in a real
GIMP started with `--new-instance` and an isolated profile
(`GIMP3_DIRECTORY`), calling the registered procedures non-interactively.

## Where to start

- [quality-ledger.md](quality-ledger.md): the visual verdict of every
  generation case, one row each (seams, colour, blur, artifacts, mask edge,
  content, 1 to 5, plus a verdict). Synthetic matrix: 11 PASS,
  31 PASS-WITH-NOTES, 22 FAIL of 64; real photos (section "Real photos"):
  8 PASS, 10 PASS-WITH-NOTES, 10 FAIL of 28. It also separates model
  limitations from plug-in defects and lists what is still open.
- [photos-README.md](photos-README.md): the six photographs (source URLs,
  authors, licenses: five CC0, one public domain), selections and prompts.
- [photo-ab/README.md](photo-ab/README.md): A/B comparisons behind the
  real-photo fixes.
- [sd15-prompt-ablation/README.md](sd15-prompt-ablation/README.md): why SD 1.5
  ignores the prompt on flat regions (no graph step is responsible).

## Folders by prefix

| Prefix | Count | What it covers | Files per case |
|---|---|---|---|
| `sel-` | 24 | Selection shapes and positions: none, whole image, tiny (20 px), huge, feathered, Quick Mask, disjoint, at each edge and corner, on offset or grouped layers, with a channel or layer mask active; some repeated with other seeds or the Quality tier (`-seed7`, `-seed99`, `-quality`) | `before.png`, `after.png`, crops for small regions, `report.json`, `batch-command.txt`, `plugin-log.txt` |
| `img-` | 18 | Image types: sizes from 256 to 6000 px, extreme aspect ratios, grayscale, indexed (refused), 16-bit, 32-bit float, linear light, transparency, text layer, hidden layers, rotated layer, a path, an unsaved new image | as `sel-` |
| `prompt-` | 5 | Empty prompt, negative prompt only, quotes and backslashes, Unicode and emoji, a very long prompt | as `sel-` |
| `mode-` | 16 | Fill, Remove object, Generative Expand (each side and all sides), Text to Image into a layer and into a new image, 4 variations, fixed and random seeds, and every installed tier (SD 1.5, SDXL + Fooocus, Juggernaut XL, MAT) | as `sel-` |
| `err-` | 1 | `err-model-missing`: a model that is not downloaded | as `sel-` |
| `photo-` | 28 | Remove, replace and extend on six real photographs (face, fabric, landscape, architecture, text, product); `-fast` is SD 1.5, `-quality` is Juggernaut XL with an empty prompt | `before.jpg`, `after.jpg`, `region-1to1.jpg`, `report.json`, `batch-command.txt`, `plugin-log.txt` |
| `rob-` | 26 | Robustness: backend missing, config missing or corrupt, autostart off, port in use, extra server options, ComfyUI killed mid-job, external ComfyUI, model missing, out of VRAM, two GIMPs, Cancel in each phase and from ComfyUI, GIMP killed mid-generation, idle timeout, corrupt and offline downloads, fresh install | `report.json`, `process-snapshots.txt`, `before.png`, `after.png`, `batch-command.txt`, `plugin-log.txt` |
| `perf` | - | Performance measurements reported in [docs/performance.md](../../performance.md) | see that document |
| `sd15-prompt-ablation/` | - | The exact crop and mask sent for `sel-edge-top`, re-run against ComfyUI with graph steps removed | `README.md`, `sent-*.png`, `result-*.png`, the two scripts used |
| `photo-ab/` | - | Old against new parameters on the photos (MAT working size, Quality-tier pre-fill, colour match, expand context) | `README.md`, `ab-spec.json`, side-by-side `*-A-vs-B.jpg`, and `cases/<id>/` with `report.json`, `batch-command.txt`, `plugin-log.txt` (images removed to save space) |

`rob-fresh-install` has no `report.json`: it holds the transcripts of
`install.ps1` and `install.sh` (WSL Ubuntu and Git Bash, fake profiles) and a
file listing. The specs that produced the matrix and photo cases are
[matrix-spec.json](matrix-spec.json) and [photo-spec.json](photo-spec.json).

## What report.json contains

Matrix, photo and error cases (`sel-`, `img-`, `prompt-`, `mode-`, `err-`,
`photo-`):

- `id`, `spec` (image recipe, selection, procedure and its arguments) and
  `pass`;
- `checks`: mechanical checks such as `returns_success`, `layer_has_mask`,
  `mask_opaque_over_selection`, `content_changed_in_selection`,
  `outside_grown_mask_unchanged`, `not_a_flat_blob`, `selection_restored`;
- `metrics`: status and message, seconds, layer size and offset, mask
  coverage, mean change inside the selection, maximum change outside the
  grown mask, Laplacian variance inside and outside (detail ratio);
- `memory`, `gimp` (GIMP version, start time, per-run results),
  `evidence_files`, `analysis_error`; photo cases add `region_scale`.

`pass` only covers mechanics. `content_changed_in_selection` also passes when
an object was merely removed, so the visual verdict in the ledger is the one
that counts.

Robustness cases (`rob-`): `case`, `verdict` and `verdict_reason`, the
`acceptance_rule` (plain message with a next step, no hang, image untouched,
nothing left running), `status`, `user_message_verbatim` (what the user saw),
`seconds_in_procedure`, `checks` (traceback in the output, image untouched,
layers after, selection unchanged, processes alive 10 s after GIMP exited,
cleanup time), a timestamped `events` list, and the launcher, driver and
GIMP stderr output. `process-snapshots.txt` lists the GIMP, Python and
ComfyUI processes before, during and after the case.

## Re-running a case

`batch-command.txt` in each case folder records the exact environment and
command line. The launchers named on its last line lived outside the
repository and are not part of it; the in-repo entry points are the two GIMP
scripts, configured through environment variables that must be set before
GIMP starts.

Matrix and photo cases,
[tests/gimp_batch_matrix.py](../../../tests/gimp_batch_matrix.py):

```bat
set GIMP3_DIRECTORY=<isolated test profile with the plug-in linked in>
set SB_MATRIX_SPEC=<repo>\docs\evidence\overnight-2026-10-09\matrix-spec.json
set SB_MATRIX_OUT=<scratch output folder>
set SB_MATRIX_ONLY=sel-edge-top,mode-fill
gimp-console-3.2.exe --new-instance --no-splash --console-messages ^
    --batch-interpreter python-fu-eval ^
    -b "exec(open(r'<repo>\tests\gimp_batch_matrix.py').read())"
```

`SB_MATRIX_ONLY` is an optional comma-separated list of case ids, `SB_REPO`
the checkout (default `C:\repos\gimp-stable-boy`), and `SB_TEST_QUIT=0` keeps
GIMP open afterwards. The script writes `gimp-report.json` and raw pixel
buffers per case to `SB_MATRIX_OUT`; the pixel metrics in the curated
`report.json` and the downscaled images were computed from those buffers
afterwards. For the photo cases, download the photographs listed in
`photos-README.md` and point the `source` paths in `photo-spec.json` at them.

Robustness cases,
[tests/gimp_batch_robustness.py](../../../tests/gimp_batch_robustness.py):
one case per GIMP start, with `SB_ROB_CASE` (the case id) and `SB_ROB_OUT`
(its output folder). Optional: `SB_ROB_PROC`, `SB_ROB_W`, `SB_ROB_H`,
`SB_ROB_SEL` (x,y,w,h), `SB_ROB_VARIATIONS`, `SB_ROB_PROMPT`,
`SB_ROB_MODEL`, `SB_ROB_HOLD` (seconds to stay open, for the idle timeout),
`SB_ROB_WARMUP`, `SB_ROB_WAIT_GO`, and `SB_ROB_CANCEL_STEP` with
`SB_TEST_CANCEL_FILE` (press Cancel at a given progress text). The scenario
itself (a broken `config.json`, a listener on the port, a killed ComfyUI) is
set up by hand before or during the run, as described in the case's
`report.json` and `batch-command.txt`. Keep GIMP's stderr: in console mode
the messages the user would see go there. More detail:
[CONTRIBUTING.md](../../../CONTRIBUTING.md).

## Size

The folder is about 48 MB: synthetic cases about 23 MB, photo cases about
15 MB, robustness cases about 7 MB, `photo-ab/` 3 MB. Images are downscaled
to a longest side of 1024 px; photographic cases are stored as JPEG
(quality 85 to 90) because a 1024 px photo PNG is 2 to 3 MB. Full-size
originals were not committed.
