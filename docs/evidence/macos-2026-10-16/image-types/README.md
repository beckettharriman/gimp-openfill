# Image types and selection shapes

One Generative Fill per case on `tests/data/test-scene.png`, DreamShaper 8.

| case | result | seconds |
|---|---|---|
| grayscale | success, stays grayscale | 96.2 |
| indexed, 64 colours | refused with the "indexed colors" message | 1.3 |
| 16-bit (U16 non-linear) | success, precision kept | 61.9 |
| RGBA, selection over a transparent corner | success, see below | 87.4 |
| layer group selected (plus a 60% overlay layer) | success, new layer above the group | 71.1 |
| feathered ellipse (40 px) | success | 97.1 |
| selection in the top-left corner | success | 58.1 |
| two separate areas, Remove object | success, both removed | 5.3 |

Over the transparent corner, the transparent pixels are flattened over the
mean visible colour before upload (`gimp_io.flatten_over_mean`, so the
model doesn't see black). SD 1.5 then left a flat greenish patch instead of
the boulder, which is the "flat areas" limit the README lists.

The two refusals (indexed image, nothing selected) used to end with "Next
step: try again. If it happens again, turn on Verbose log ... for a bug
report", which is wrong for a refusal that will repeat every time. Fixed in
`ui_text._NEXT_STEPS`.
