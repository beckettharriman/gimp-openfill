# SD 1.5 inpainting checkpoints: pairwise ranking per case

One line per case: the best of `sd15-inpainting` (sd15), `realistic-vision-v6-inpainting` (rv6) and `dreamshaper-8-inpainting` (ds8), and why. Totals are the sum of the six rubric scores (6 to 30). Strips: `strips/<case>.jpg`.

| Case | Group | sd15 | rv6 | ds8 | Best | Why |
|---|---|---|---|---|---|---|
| architecture-remove-small-ac | remove | 15 FAIL | 17 FAIL | 25 PASS | ds8 | Only ds8 removes without inventing an object (statue, cushion). |
| clouds-remove-large-palm | remove | 23 PWN | 22 FAIL | 23 PWN | ds8 | All similar; ds8 cloud rim reads most natural, rv6 shows a sky band. |
| crowd-remove-large-monument | remove | 18 FAIL | 20 FAIL | 18 FAIL | rv6 | All invent a dome; rv6's is the least conspicuous. |
| face-remove-small-patch | remove | 26 PASS | 24 PWN | 24 PWN | sd15 | sd15 keeps the cuff fold and fabric grain; rv6 and ds8 flatten it. |
| food-remove-small-fork | remove | 24 PWN | 15 FAIL | 20 FAIL | sd15 | sd15 removes cleanly; rv6 redraws a fork, ds8 smears. |
| handwriting-remove-large-lines | remove | 14 FAIL | 15 FAIL | 15 FAIL | rv6 | All write fake script; rv6's is faintest. Narrow. |
| illustration-remove-large-baby | remove | 16 FAIL | 22 FAIL | 24 PWN | ds8 | ds8's chair fits the print style; sd15 leaves a blob. |
| interior-remove-small-portrait | remove | 18 FAIL | 21 FAIL | 23 PWN | ds8 | ds8 cleanest; sd15 invents a figure. |
| landscape-remove-small-barn | remove | 25 PASS | 14 FAIL | 25 PASS | ds8 | ds8 and sd15 both pass; ds8 has no puddle; rv6 builds a new house. |
| night-street-remove-large-car | remove | 18 FAIL | 16 FAIL | 24 PWN | ds8 | ds8 reads as road; rv6 swaps the car for another car. |
| portrait-remove-large-shuttle | remove | 26 PASS | 22 FAIL | 25 PWN | sd15 | sd15 has no visible panel. |
| product-remove-large-cup | remove | 18 FAIL | 18 FAIL | 18 FAIL | sd15 | All invent an object; sd15's is smallest. All unusable. |
| text-remove-small-logo | remove | 30 PASS | 30 PASS | 30 PASS | tie | Flat panel; all perfect. |
| face-replace-sunglasses | replace with a prompt | 18 FAIL | 25 PASS | 25 PASS | rv6 | rv6 and ds8 both pass; rv6's frame is the truer aviator; sd15 draws goggles with ear pads. |
| food-replace-watermelon | replace with a prompt | 17 FAIL | 20 FAIL | 25 PASS | ds8 | Only ds8 produces a convincing slice. |
| hands-replace-strawberry | replace with a prompt | 18 FAIL | 18 FAIL | 16 FAIL | rv6 | All draw a strawberry and all show a frame; rv6's berry sits best in the scene, ds8's frame is worst. |
| landscape-replace-balloon | replace with a prompt | 25 PASS | 19 FAIL | 12 FAIL | sd15 | sd15 integrates; rv6 clips at the edge; ds8 pastes a blue panel. |
| night-street-replace-moon | replace with a prompt | 27 PASS | 26 PASS | 25 PWN | sd15 | All succeed; sd15's scale is the most believable. |
| pet-replace-ladybug | replace with a prompt | 24 PWN | 26 PASS | 22 FAIL | rv6 | rv6 matches the focus and puts it on a blade as asked. |
| portrait-replace-earring | replace with a prompt | 23 PWN | 21 FAIL | 24 PASS | ds8 | Only ds8 draws a hoop. |
| product-replace-spoon | replace with a prompt | 18 FAIL | 20 FAIL | 12 FAIL | rv6 | rv6 has a real teaspoon, if in an unrequested bowl; ds8 pastes a black panel. |
| signage-replace-text | replace with a prompt | 12 FAIL | 14 FAIL | 14 FAIL | ds8 | None writes the text; ds8's banner is the tidiest. |
| snow-replace-fox | replace with a prompt | 19 FAIL | 19 FAIL | 21 FAIL | ds8 | ds8's fox is best; all smooth the snow. |
| text-replace-text-20h | replace with a prompt | 20 FAIL | 14 FAIL | 14 FAIL | sd15 | sd15 at least writes 20 in a matching font. |
| water-replace-canoe | replace with a prompt | 22 FAIL | 22 FAIL | 25 PASS | ds8 | ds8 is the only convincing canoe; sd15 ignores the prompt. |
| architecture-material-roof-tiles | fill (material or damaged area) | 10 FAIL | 15 FAIL | 15 FAIL | rv6 | All fail the prompt; rv6 at least hints at red tiles, sd15 adds a yellow box. |
| fabric-damaged-large | fill (material or damaged area) | 23 PWN | 17 FAIL | 17 FAIL | sd15 | sd15 matches the weave scale and colours; rv6 and ds8 paste a different fabric. |
| product2-material-suede | fill (material or damaged area) | 21 FAIL | 17 FAIL | 19 FAIL | sd15 | sd15 keeps the shoe and the cleanest background. |
| texture-damaged-huge | fill (material or damaged area) | 17 FAIL | 18 FAIL | 11 FAIL | rv6 | rv6 is still a brick wall; the others build a recess. |
| face-expand-right | expand one side | 25 PWN | 25 PWN | 25 PWN | tie | Plain backdrop; all three equivalent. |
| interior-expand-left | expand one side | 19 FAIL | 23 PWN | 18 FAIL | rv6 | rv6 continues the damask and chairs; the others paint plain walls. |
| landscape-expand-all | expand all sides | 23 PWN | 22 FAIL | 23 PWN | ds8 | ds8 composes best (crown completes the birch) without rv6's sky colour shift. |
| product-expand-all | expand all sides | 29 PASS | 30 PASS | 26 PWN | rv6 | rv6 and sd15 seamless; ds8 shifts the white. |

Wins: sd15 9, rv6 10, ds8 12, ties 2. PWN = PASS-WITH-NOTES.
