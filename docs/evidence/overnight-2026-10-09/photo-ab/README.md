# A/B of fill parameters on real photos (2026-10-09)

The photo-* cases (see ../photos-README.md) showed four plug-in-side problems.
Each change below was tried against the previous default on the same photo,
selection, seed (1234), model and step count; the better variant became the
default. The case reports of the A/B runs are in cases/ (report.json,
plugin-log.txt, batch-command.txt; images removed to save space, the
comparison crops below are taken from the full-size results). The spec is
ab-spec.json; ab1-*, ab2-* and ab3-* ids map to the photo-* case of the same
name.

All crops are 1:1 unless they would be wider than 1024 px.

## 1. MAT removal context (geometry.INPAINT_MODEL, geometry.fill_padding)

A (old): context = selection plus 1.0x its larger side on each side, up to
1024 px working size. B (new): working size at most 512 px and a 0.5x margin
for the prompt-free removal models.

Cause: the removal node in comfyui-inpaint-nodes always runs MAT on a 512 px
square. It pads the crop to a square and resizes it with nearest-neighbour
sampling, then scales the result back up bilinearly. A 1215 px context (face
patch, 312x405 selection) was shrunk 2.4x inside the node, so the fill came
back soft (detail ratio inside/outside 0.02 in report.json) and MAT, seeing
a mostly downsampled context, produced ghosts.

| Case | A (old) | B (new) | Files |
|---|---|---|---|
| face patch | soft, pale blob in the middle | sharper weave; two small dark stains | ab1-face-remove-A-vs-B.jpg |
| landscape barn | ghost of the barn wall behind the trees, hard vertical cut | barn gone, horizon and hedge continue | ab1-landscape-remove-A-vs-B.jpg |
| sign word "AUX" | two dark blobs left in the yellow | clean yellow | ab1-text-remove-A-vs-B.jpg |
| air conditioner | fragments of blinds and a blue box | still fragments, slightly cleaner | ab1-architecture-remove-A-vs-B.jpg |
| fabric fibres | smeared glassy fibres | fibres, one radial cluster | mat-fabric-remove-A-over-B.jpg (top A, bottom B) |
| cup foot ring | grey band, cup bottom flattened | cup bottom has a notch | mat-product-remove-A-over-B.jpg (top A, bottom B) |

Kept: B. Clear win on 3 of 6 (landscape, text, face texture). Architecture
fails both ways and product is a different flaw rather than a better result.

## 2. Pre-fill of prompted fills on the Quality tier (geometry.prefill_for)

A (old): neutral grey hole for every prompted fill at strength 1.0 (added in
the synthetic run so SD 1.5 follows the prompt). B (new): border fill
(navier-stokes, then the usual 65 px masked blur) for SDXL; SD 1.5 keeps the
neutral hole. C (tried, rejected): neutral hole whose edge fades into the
original over 63 working px.

With the flat grey rectangle, Juggernaut XL with the Fooocus patch paints a
separate picture into the selection: a framed photograph of a woman holding
a red scarf on the tweed, a balloon on its own blue-sky rectangle pasted into
the evening sky.

| Case | A neutral | B border | C soft neutral | Files |
|---|---|---|---|---|
| fabric, "red wool scarf" | framed photo inside the cloth (FAIL) | scarf lying on the tweed | framed photo again | ab1-fabric-replace-A-vs-B.jpg, ab3-fabric-before-B-C.jpg |
| sky, "hot air balloon" | balloon on a blue rectangle (FAIL) | balloon in the evening sky | balloon on a blue rectangle | ab1-landscape-replace-A-vs-B.jpg, ab3-landscape-before-B-C.jpg |
| sign word, "a blue arrow" | blue block filling the box, arrow-like right end | word removed, no arrow | garbled glyphs | ab1-text-replace-A-vs-B.jpg, ab3-text-before-B-C.jpg |
| wall, "open window with curtains" | flat green pane in a frame, fills the box | flat yellow-beige rectangle, no window | flat pane in a frame | ab1-architecture-replace-A-vs-B.jpg, ab3-architecture-before-B-C.jpg |
| eyes, "sunglasses" | silver aviators | gold aviators | aviators | ab1-face-replace-A-vs-B.jpg, ab3-face-before-B-C.jpg |
| saucer, "a lemon slice" | lemon slice | lemon slice | lemon slice | ab1-product-replace-A-vs-B.jpg, ab3-product-before-B-C.jpg |

(ab3 images show before | B | C.)

Kept: B. A and C produce an unusable framed picture on 2 of 6; B never does.
B loses the content on the sign and the wall (the model leaves the border
fill nearly unchanged, and on the wall the result is a visibly tinted flat
rectangle); that is recorded as an open issue in the quality ledger.

## 3. Colour match for prompted fills (geometry.color_match_strength)

A: INPAINT_ColorMatch at 1.0 (unchanged default). B: off for prompted fills.
Hypothesis from the synthetic ledger: colour matching flattens large fills
into tinted blocks (concern 3).

| Case | Result | Files |
|---|---|---|
| fabric SD 1.5 "red wool scarf" | no visible difference; both a soft, washed-out rectangle without scarf | ab2-fabric-replace-fast-A-vs-B.jpg |
| face SD 1.5 "sunglasses" | B slightly warmer skin, otherwise identical | ab2-face-replace-fast-A-vs-B.jpg |
| sky SD 1.5 / SDXL balloon, saucer, fabric SDXL | identical at normal view | ab2-*-A-vs-B.jpg |

Kept: A (1.0). Colour match is not what makes large SD 1.5 fills soft: the
fabric selection (672x587) is generated at 0.57x and upscaled, so the
rectangle is softer than the 1:1 weave around it. PROMPT_COLOR_MATCH stays as
a named constant.

## 4. Generative Expand context and uploads (geometry.plan_expand, workflow.probe_safe_png)

A (old): the context of a one-sided expansion was the generic selection
context (margin = the larger side of the strip), which for a 256 px strip
along a 1440 px edge is the whole canvas, sampled at 0.47x; the new strip was
a ~120 px band in the working image. Results: a flat lime bar (landscape), a
blurred yellow block (architecture), a flat pale field (sign). B (new): the
strip plus an old-image band twice as deep (at least the model's minimum
context, and at least half the edge length), over the full edge.

The first B run failed with "LoadImage: End of file" on every expansion:
ComfyUI 0.39 decodes uploads with PyAV, whose format probe scored the
deflated stream of the strip mask (identical rows) as MPEG-TS (score 100
against PNG 99). Fixed with a tEXt chunk of spaces after IHDR that fills the
2048-byte probe window (workflow.probe_safe_png, applied to every upload in
backends/comfy.py; verified with ComfyUI's own PyAV on 42 masks, pixels
unchanged).

| Case | A (whole canvas) | B (strip context) | File |
|---|---|---|---|
| landscape right | flat lime bar | trees and meadow; one bright fern-like branch | expand-landscape-A-vs-B.jpg |
| architecture right | blurred yellow block | windows with curtains continuing the facade | expand-architecture-A-vs-B.jpg |
| sign right | flat pale yellow | a path and grass beyond the frame | expand-text-A-vs-B.jpg |
| fabric right | blurred fibres, brown wooden edge | coarser, blurred fibres; visible seam | expand-fabric-A-vs-B.jpg |
| product right | white | white | expand-product-A-vs-B.jpg |

Kept: B. The face (2400x3000) got a dark panel with B before the minimum
aspect was added (864x3000 context sampled at 296x1024); see the quality
ledger for the re-run. All-sides expansion is unchanged (it still uses the
whole canvas) and remains a FAIL on the Quality tier.
