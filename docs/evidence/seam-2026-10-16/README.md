# Seam correction and the Generative Expand negative (2026-10-16)

Follow-up to the macOS run (`../macos-2026-10-16/`), which reported faint
rectangles around a fill in flat sky and an invented figure in an empty-prompt
expand. Reproduced and measured on Linux: GIMP 3.2.6 Flatpak, ComfyUI 0.40,
RTX 2070 Max-Q (8 GB), isolated profiles, `gimp-console-3.2 --batch-interpreter python-fu-eval`.

## The faint rectangle is colour drift, not tile seams

The 4000 x 3000 fill from the macOS evidence shows the same box with RealVisXL
in a single pass (no tiles): the generated sky inside the selection comes back
about +7 green and +6 blue against the original, a step that a smooth gradient
shows and texture hides. Generative Expand has the same drift at the old edge
(beside the Porsche: about 8 levels in R, G and B).

`quality.seam_field` measures the layer against the original where the two
should agree (just outside the selection; for an expand, where the new area
overlaps the old image), ignores textured cells and differences over 24 levels
(content, not drift), and spreads the measured offsets over the layer.

`before-after.jpg`: left, `seam_correction: false`; right, the default. Same
seeds, same backend.

| Case | Step at the edge, off | on |
|---|---|---|
| Fill 1040 x 800 in a 4000 x 3000 sky, DreamShaper 8 | 5.3 levels | 0.4 |
| Same, RealVisXL V5 | 5.1 | 0.1 |
| Expand left and right 300 px, Porsche photo, DreamShaper 8 | about 8 (145/194/243 to 153/201/251) | none (flat 153/201/251) |
| Expand right 1000 px, cartoon test scene, DreamShaper 8 | 35 in red | unchanged: over the 24-level limit, treated as content |

Time: 1 to 3 s per layer, 8 s on a 5000 x 3000 canvas.

## Naming subjects in the expand negative does not help

`expand-negative-ab.jpg`: the current `EXPAND_NEGATIVE` (left) against the
same with "person, animal, creature, character" added (right), 16 runs each:
DreamShaper 8 and RealVisXL V5, seeds 1234 and 7, on the Porsche photo (sides
300, top and bottom 270), a Wikimedia Commons landscape (Fronalpstock, by
Hannes Röst, CC BY-SA 3.0, https://commons.wikimedia.org/wiki/File:Fronalpstock_big.jpg; top and bottom 192) and the 4000 x 3000
cartoon test scene (right 1000). Neither variant invented a subject on the
photos. On the cartoon scene both invent objects (a palm tree, a post with
speakers) at seed 7; the extra words only change which object. The negative is
unchanged. The invented figure on the Mac came from the flat cartoon test
scene, where an inpainting model has nothing to continue.
