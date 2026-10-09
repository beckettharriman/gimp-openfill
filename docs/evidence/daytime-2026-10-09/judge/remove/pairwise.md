# Remove: pairwise, lama-big versus mat-places512

One line per case: the better result and why. Strips: `strips/<case>.jpg` (before | lama-big | mat-places512, then 2x zooms of the seam at the selection edges).

| Case | Group | Better | Why |
|---|---|---|---|
| architecture-remove-large-laundry | structured background | mat-places512 | Both fail; MAT keeps facade lines and grain, LaMa turns the hole into a blur. MAT's invented pillar is the lesser evil at viewing size. |
| architecture-remove-small-ac | structured background | lama-big | LaMa is soft but reads as a window; MAT invents new hardware. |
| clouds-remove-large-palm | textured or natural background | lama-big | MAT paints text-like glyphs into the clouds; LaMa only softens. |
| crowd-remove-large-monument | structured background | mat-places512 | MAT rebuilds the skyline at the base; LaMa leaves a blurred block. |
| crowd-remove-small-screen | textured or natural background | mat-places512 | MAT keeps the crowd grain; LaMa's patch is a visible soft block. |
| fabric-remove-tiny | textured or natural background | mat-places512 | MAT continues the weave; LaMa leaves a blur spot. |
| face-remove-large-shuttle | large object beside a person | mat-places512 | Both unusable; MAT's fill at least has no residue of the shuttle. |
| face-remove-small-patch | person: skin and clothing | lama-big | LaMa continues the existing pleats; MAT invents a fold. |
| food-remove-large-milk | textured or natural background | mat-places512 | Both leave a ghost of the glass base; MAT's weave is sharper. Narrow. |
| food-remove-small-fork | textured or natural background | mat-places512 | MAT keeps the weave grid; LaMa's diagonal smear is obvious. |
| hands-remove-large-bracelet | person: skin and clothing | lama-big | LaMa is clean; MAT adds a highlight blob and bends the wrist. |
| handwriting-remove-large-lines | text and signage | lama-big | MAT writes fake script; LaMa's smudges are less conspicuous. |
| handwriting-remove-small-stain | text and signage | lama-big | LaMa's ghost is fainter and the letters less damaged. |
| illustration-remove-large-baby | illustration (halftone print) | lama-big | MAT invents objects; LaMa is soft but empty. |
| illustration-remove-small-stamp | illustration (halftone print) | lama-big | LaMa's flat patch is fixable; MAT adds a new object. Narrow. |
| interior-remove-large-tv | structured background | lama-big | MAT leaves a TV ghost and adds a figure. |
| interior-remove-small-portrait | structured background | lama-big | Both fail; LaMa keeps the pattern rhythm, MAT turns it into glitter. Narrow. |
| landscape-remove-large-birch | textured or natural background | mat-places512 | MAT keeps grass texture across a full-height hole; LaMa's seam is visible at a glance. |
| landscape-remove-small-barn | textured or natural background | mat-places512 | MAT's horizon is clean; LaMa leaves a colour glitch and smear. |
| night-street-remove-large-car | structured background | mat-places512 | MAT reads as a road; LaMa reads as a smudge. |
| night-street-remove-small-light | structured background | lama-big | MAT draws a new lamp. |
| pet-remove-small-scar | textured or natural background | mat-places512 | MAT continues fur strokes; LaMa leaves a noisy block. |
| portrait-remove-large-shuttle | large object beside a person | lama-big | LaMa's fill would pass at viewing size; MAT leaves smears. |
| portrait-remove-small-badge | person: skin and clothing | lama-big | LaMa is clean; MAT adds scratches. |
| product-remove-large-cup | product on plain background | lama-big | Both fail; a ghost can be cleaned with a second pass, an invented building cannot. |
| product-remove-small-handle | product on plain background | lama-big | LaMa is clean; MAT leaves a wedge. |
| product2-remove-small-knob | product on plain background | lama-big | Both leave a remnant; LaMa's is smaller and plain. |
| signage-remove-large-sign | textured or natural background | mat-places512 | MAT keeps ground texture; LaMa's rectangle is visible. Narrow. |
| signage-remove-small-logo | text and signage | lama-big | MAT writes fake letters; LaMa's are faint. |
| snow-remove-small-sun | textured or natural background | mat-places512 | MAT continues the branch mesh; LaMa leaves noise. |
| text-remove-large-signs | text and signage | lama-big | MAT writes fake text on a flat panel. |
| text-remove-small-logo | text and signage | tie | Both perfect on a flat panel. |
| water-remove-small-plants | textured or natural background | lama-big | Both fail; MAT's white blob is more conspicuous. |

Tally: lama-big 19, mat-places512 13, tie 1.
