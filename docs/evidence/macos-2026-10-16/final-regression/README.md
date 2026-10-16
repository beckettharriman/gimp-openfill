# Final regression

The eight cases of `e2e-with-opencv/` (same driver) rerun at the end of the
stress run, with every fix in this branch installed via `sh install.sh`:

| case | result | seconds |
|---|---|---|
| fill with a prompt (backend cold start) | success | 84.2 |
| fill again (warm) | success | 57.4 |
| remove object (LaMa) | success | 5.1 |
| 3 variations | success | 209.7 |
| expand right by 256 px | success | 148.5 |
| text to image (layer) | success | 75.6 |
| 24 px selection | success | 47.0 |
| fill without a selection | refused, message without "try again" | 1.1 |

The supervisor stopped ComfyUI as soon as GIMP quit.
