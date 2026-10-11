# Expand re-benchmark: SD 1.5 inpainting vs DreamShaper 8 vs RealVisXL V5

Setup: four photos (landscape, interior, portrait, product2 shoe) x three models x 25 % and 60 % of the photo's width (left and right) and height (top and bottom), all four sides at once, empty prompt ("continue the scene"), seed 1234, one variation, default settings, headless GIMP. 24 runs, all succeeded. RealVisXL was run without the SDXL-to-SD 1.5 expand redirect (benchmark switch, not in the code). Spec: expand-spec.json; sheets: sheet-25.jpg and sheet-60.jpg (rows landscape, interior, portrait, product2; columns SD 1.5, DreamShaper 8, RealVisXL); script: make_sheets.py. Judging is pairwise on the sheets: best of three per case.

| Case | SD 1.5 inpainting | DreamShaper 8 | RealVisXL V5 | Best |
|---|---|---|---|---|
| landscape 25 % | continues field, sky, tree; clean | faint pale patch top left | blurred green foreground, vignette, band seams | SD 1.5 |
| interior 25 % | floating painting on the right wall | clean continuation of wall and floor | invents a wooden doorway frame | DreamShaper |
| portrait 25 % | backdrop continues naturally | plain extension, dark band left | invents a room with a window | SD 1.5 |
| product2 25 % | faint tonal band | stepped seams at the old edge | clean | RealVisXL |
| landscape 60 % | plausible field and sky, slight smear | dark vignette, boxy seam | lush green boxes, large visible rectangle | SD 1.5 |
| interior 60 % | glowing artifact on the right | plausible room, darker | invents curtains and wood panelling | DreamShaper |
| portrait 60 % | smoky, continuous, odd | two-tone hallway with seams | invents a hallway | SD 1.5 |
| product2 60 % | clean white | visible grey rectangle around the old frame | faint box | SD 1.5 |

Wins: SD 1.5 5, DreamShaper 8 2, RealVisXL 1. Times (s, SD 1.5 / DreamShaper / RealVisXL): 25 % 14 to 42 / 27 to 58 / 14 to 49; 60 % 48 to 74 / 81 to 113 / 46 to 77. Above 25 % per side every model degrades (hallways, boxes, vignettes), so large expansions stay weak.

Choice: SD 1.5 inpainting is the expand default for both tiers, DreamShaper 8 the fallback. RealVisXL is the worst expand model: it invents scenery instead of continuing it. An SDXL model picked for Expand is handed to SD 1.5 (existing redirect), now to SD 1.5 first. Single judge, four photos: the ranking of SD 1.5 over DreamShaper is a modest margin.
