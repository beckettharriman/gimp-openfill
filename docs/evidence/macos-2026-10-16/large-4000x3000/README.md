# 4000 x 3000 image

`tests/data/test-scene.png` scaled to 4000 x 3000 inside GIMP, DreamShaper 8.

| case | result | seconds |
|---|---|---|
| fill 1040 x 800 selection (backend cold) | success | 862.8 |
| expand right by 1000 px (25%) | success, canvas 5000 x 3000, 1 round | 206.1 |

The fill is tiled: a layout pass at 936 x 832, then 4 tiles of 640 x 640 at
denoise 0.65, all in one ComfyUI job. Sampling took 804 s on the M3 (about
2 to 3 s per step per pass). The deadline moves with every progress message,
so the long job was never cut off.

Quality (`*.png`, downscaled to 1024 px): the boulder is good, but two
faint tile rectangles show in the flat sky above it. In the expand, the new
strip's sky is a slightly different shade at the old edge, and with the empty
prompt SD 1.5 drew a cartoon figure even though `EXPAND_NEGATIVE` names
"people". Neither is specific to macOS.
