# SDXL checkpoints: pairwise ranking per case

One line per case: the best of `juggernaut-xl-v9` (jxl), `realvisxl-v5` (rvxl), `sdxl-base` (base), and why. Totals are the sum of the six rubric scores (6 to 30). Strips: `strips/<case>.jpg`. The last two columns compare the best SDXL result with the best SD 1.5 result (`../sd15`) and, on removal cases, with the best of LaMa and MAT (`../remove`), decided by eye on side-by-side crops.

| Case | Group | jxl | rvxl | base | Best | Why | vs best SD 1.5 | vs best LaMa/MAT |
|---|---|---|---|---|---|---|---|---|
| architecture-remove-small-ac | remove | 23 PWN | 22 FAIL | 22 FAIL | jxl | Same idea; jxl's window is cleaner and has no blob on the rail. | SD 1.5 better | SDXL better |
| clouds-remove-large-palm | remove | 14 FAIL | 13 FAIL | 14 FAIL | jxl | Both fail by repainting the trunk; jxl at least only one. | SD 1.5 better | LaMa/MAT better |
| crowd-remove-large-monument | remove | 24 PWN | 23 FAIL | 14 FAIL | jxl | jxl and rvxl clean in the sky (rvxl adds a smudge); base builds a skyscraper. | SDXL better | SDXL better |
| face-remove-small-patch | remove | 19 FAIL | 26 PASS | 17 FAIL | rvxl | rvxl is clean; jxl invents glowing torches, base a gold buckle. | tie | SDXL better |
| food-remove-small-fork | remove | 17 FAIL | 17 FAIL | 17 FAIL | tie | Identical failure: flat stripes instead of woven napkin. | SD 1.5 better | LaMa/MAT better |
| handwriting-remove-large-lines | remove | 21 FAIL | 16 FAIL | 14 FAIL | jxl | jxl writes nothing; rvxl leaves ghost script. | SDXL better | SDXL better |
| illustration-remove-large-baby | remove | 22 FAIL | 25 PASS | 22 FAIL | rvxl | rvxl's chair matches the illustration; jxl's looks rendered. | SDXL better | SDXL better |
| interior-remove-small-portrait | remove | 15 FAIL | 15 FAIL | 15 FAIL | tie | Both repaint a picture where the picture was. | SD 1.5 better | LaMa/MAT better |
| landscape-remove-small-barn | remove | 17 FAIL | 15 FAIL | 12 FAIL | jxl | Both invent a hill; rvxl keeps a barn roof. | SD 1.5 better | LaMa/MAT better |
| night-street-remove-large-car | remove | 12 FAIL | 17 FAIL | 12 FAIL | rvxl | Both put a car back; rvxl's road is right and the car is one realistic car, not three toys. | SD 1.5 better | LaMa/MAT better |
| portrait-remove-large-shuttle | remove | 19 FAIL | 21 FAIL | 19 FAIL | rvxl | rvxl's blobs are fainter and read more like backdrop mottling. | SD 1.5 better | LaMa/MAT better |
| product-remove-large-cup | remove | 18 FAIL | 19 FAIL | 20 FAIL | base | All leave a green haze; base has no grass tuft. | SDXL better | tie |
| text-remove-small-logo | remove | 26 PASS | 26 PASS | 26 PASS | tie | Equivalent. | SD 1.5 better | LaMa/MAT better |
| face-replace-sunglasses | replace with a prompt | 23 FAIL | 25 PASS | 25 PASS | rvxl | Both draw good aviators; jxl erases the hair at the left temple. | SDXL better | - |
| food-replace-watermelon | replace with a prompt | 21 FAIL | 20 FAIL | 20 FAIL | jxl | jxl's slices sit more naturally; both clip at the selection edge. | SD 1.5 better | - |
| hands-replace-strawberry | replace with a prompt | 30 PASS | 30 PASS | 29 PASS | tie | Both flawless. | SDXL better | - |
| landscape-replace-balloon | replace with a prompt | 29 PASS | 29 PASS | 29 PASS | rvxl | Both pass; rvxl's envelope reads more natural. | SDXL better | - |
| night-street-replace-moon | replace with a prompt | 20 FAIL | 20 FAIL | 20 FAIL | tie | Equivalent. | SD 1.5 better | - |
| pet-replace-ladybug | replace with a prompt | 23 FAIL | 25 PASS | 23 FAIL | rvxl | rvxl's ladybug fits the selection; jxl's is clipped at the edge. | SDXL better | - |
| portrait-replace-earring | replace with a prompt | 21 FAIL | 17 FAIL | 25 PASS | base | Only base draws one small hoop on an ear, inside the selection; jxl doubles it, rvxl floats it. | SDXL better | - |
| product-replace-spoon | replace with a prompt | 25 PASS | 26 PASS | 26 PASS | rvxl | Both pass; rvxl's is a teaspoon. | SDXL better | - |
| signage-replace-text | replace with a prompt | 19 FAIL | 19 FAIL | 18 FAIL | jxl | Neither spells it; jxl gets 'Desert' and the right lettering style. | SDXL better | - |
| snow-replace-fox | replace with a prompt | 22 FAIL | 22 FAIL | 22 FAIL | jxl | Same quality; jxl's smooth patch is less visible. | SDXL better | - |
| text-replace-text-20h | replace with a prompt | 23 FAIL | 23 FAIL | 22 FAIL | tie | Both write nothing. | SD 1.5 better | - |
| water-replace-canoe | replace with a prompt | 25 PASS | 25 PASS | 25 PASS | jxl | Both pass; jxl's wake ties it into the water. | tie | - |
| architecture-material-roof-tiles | fill (material or damaged area) | 17 FAIL | 18 FAIL | 15 FAIL | rvxl | Neither tiles the whole awning; rvxl's tile row reads as tiles; base draws no tiles at all. | SDXL better | - |
| fabric-damaged-large | fill (material or damaged area) | 24 PWN | 22 FAIL | 22 FAIL | jxl | jxl's weave scale is closer to the surrounding fabric. | tie | - |
| product2-material-suede | fill (material or damaged area) | 18 FAIL | 19 FAIL | 14 FAIL | rvxl | Both turn a material change into a new product shot with blocks; rvxl's shoe sits, jxl's floats. | SD 1.5 better | - |
| texture-damaged-huge | fill (material or damaged area) | 10 FAIL | 10 FAIL | 10 FAIL | tie | Identical failure. | SD 1.5 better | - |
| face-expand-right | expand one side | 25 PWN | 25 PWN | 22 FAIL | tie | Plain backdrop; equivalent. | tie | - |
| interior-expand-left | expand one side | 21 FAIL | 20 FAIL | 19 FAIL | jxl | Only jxl carries the damask into the new strip, if at the wrong scale. | SD 1.5 better | - |
| landscape-expand-all | expand all sides | 11 FAIL | 13 FAIL | - | rvxl | Both fail; jxl also writes fake text. | SD 1.5 better | - |
| product-expand-all | expand all sides | 18 FAIL | 19 FAIL | 19 FAIL | rvxl | Both show the old frame as a step; jxl adds a grey line. | SD 1.5 better | - |

Wins: jxl 11, rvxl 12, base 2, ties 8. PWN = PASS-WITH-NOTES.
Cross-family: best SDXL better than best SD 1.5 in 13 cases, worse in 16, tie 4. Against LaMa/MAT on the 13 removal cases: SDXL better 5, worse 7, tie 1.
sdxl-base has no result for landscape-expand-all (the run ended with a backend timeout, `execution-error`); its 32 results were scored from the run's raw output because the benchmark index did not list them yet (see README).
