# Real-photo test cases (photo-*)

Six photographs from Wikimedia Commons, used as the input images of the
photo-* matrix cases and of the A/B comparison in photo-ab/. The images
themselves are not stored in the repository; they are reproduced from the
URLs below. Every case loads the file at its native size (no scaling).

## Sources

All files were downloaded from Wikimedia Commons on 2026-10-09. The license was checked against the Commons file page metadata (LicenseShortName / License fields) for each file. Files larger than 3000 px on the long side were fetched as the 1920 px Commons thumbnail (the 2048 px thumbnail size is not served by upload.wikimedia.org; 1920 px is the closest standard step).

| File | Description | Source page | Direct file URL | Author | License | Dimensions |
|---|---|---|---|---|---|---|
| face.jpg | NASA official portrait of astronaut Michael A. Baker, S85-41895, October 1985 | https://commons.wikimedia.org/wiki/File:Official_Portrait_-_Astronaut_Michael_A._Baker.jpg | https://upload.wikimedia.org/wikipedia/commons/8/80/Official_Portrait_-_Astronaut_Michael_A._Baker.jpg | NASA | Public domain (US government work, NASA) | 2400 x 3000 |
| fabric.jpg | Harris Tweed cloth, macro photograph showing the wool weave | https://commons.wikimedia.org/wiki/File:Harris_Tweed_Macro_photography.jpg | https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Harris_Tweed_Macro_photography.jpg/1920px-Harris_Tweed_Macro_photography.jpg | No name (as stated on file page) | CC0 | 1920 x 1677 |
| landscape.jpg | Fields and large barn in the evening on Laaghalerveen, Netherlands, May 2012; sky and flat horizon | https://commons.wikimedia.org/wiki/File:Fields_and_large_barn_in_the_evening_set_on_Laaghalerveen,_landscape_Netherlands,_2012.jpg | https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Fields_and_large_barn_in_the_evening_set_on_Laaghalerveen%2C_landscape_Netherlands%2C_2012.jpg/1920px-Fields_and_large_barn_in_the_evening_set_on_Laaghalerveen%2C_landscape_Netherlands%2C_2012.jpg | Fons Heijnsbroek | CC0 | 1920 x 1440 |
| architecture.jpg | Building facade in Hong Kong with rows of windows, awnings and air conditioners | https://commons.wikimedia.org/wiki/File:Building_Facade_in_Hong_Kong.jpg | https://upload.wikimedia.org/wikipedia/commons/8/8b/Building_Facade_in_Hong_Kong.jpg | Wilfredor | CC0 | 2000 x 1273 |
| text.jpg | Paris road sign "Voie reservee aux cyclistes et aux pietons de 10H a 18H" (Sunday traffic restriction) | https://commons.wikimedia.org/wiki/File:Road_sign_sundays_Paris.jpg | https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Road_sign_sundays_Paris.jpg/1920px-Road_sign_sundays_Paris.jpg | Jebulon | CC0 | 1920 x 1429 |
| product.jpg | Cup of mint tea on a saucer, isolated on a white background | https://commons.wikimedia.org/wiki/File:Cup_of_tea_isolated_on_white_background_-_Petr_Kratochvil.jpg | https://upload.wikimedia.org/wikipedia/commons/9/92/Cup_of_tea_isolated_on_white_background_-_Petr_Kratochvil.jpg | Petr Kratochvil | CC0 | 1280 x 853 |

## Cases

Selections are rectangles in fractions of the image (x, y, w, h); the spec
is photo-spec.json in this folder, produced by the generator in the overnight
scratch area. Seed 1234, 1 variation, 20 steps (test profile setting),
negative prompt "blurry, lowres, watermark".

| Photo | Remove (MAT; Juggernaut for two) | Replace region and prompt | Extend |
|---|---|---|---|
| face | mission patch on the chest, [0.355, 0.555, 0.13, 0.135] | eyes, [0.50, 0.185, 0.15, 0.06], "sunglasses" | right 256 px |
| fabric | red fibre cluster, [0.46, 0.37, 0.10, 0.10] (the cloth has no seam or button) | [0.30, 0.30, 0.35, 0.35], "red wool scarf" | right 256 px |
| landscape | barn, [0.465, 0.315, 0.14, 0.09] | sky, [0.25, 0.03, 0.18, 0.20], "hot air balloon" | right 256 px, and all four sides 256 px |
| architecture | window air conditioner, [0.49, 0.33, 0.10, 0.17] | bare wall left of the facade, [0.005, 0.30, 0.085, 0.25], "open window with curtains" | right 256 px |
| text | the word "AUX", [0.105, 0.235, 0.20, 0.10] | the word "PIETONS", [0.495, 0.375, 0.42, 0.11], "a blue arrow" | right 256 px |
| product | foot ring and its shadow under the cup, [0.30, 0.61, 0.21, 0.08] | right part of the saucer, [0.47, 0.62, 0.13, 0.11], "a lemon slice" | right 256 px |

Case ids: photo-NAME-remove (MAT, prompt-free), photo-NAME-remove-quality
(Juggernaut XL v9 with an empty prompt, landscape and architecture only;
the Remove checkbox always switches to the installed LaMa/MAT model, so the
generation-model removal path is reached with an empty prompt),
photo-NAME-replace (Juggernaut XL v9, Quality tier), photo-NAME-replace-fast
(SD 1.5 inpainting, Fast tier), photo-NAME-extend (Juggernaut XL v9),
photo-landscape-extend-all.

## Evidence format

Photographic PNGs at 1024 px are 2 to 3 MB each, so the photo cases store
JPEG (quality 85 to 90) instead of PNG to stay inside the evidence budget:
before.jpg and after.jpg (longest side 1024 px), region-1to1.jpg (before |
after of the selection plus a margin, 1:1 unless the pair would be wider than
1600 px; the scale is in report.json under region_scale), plus
batch-command.txt, report.json and plugin-log.txt. For expand cases
region-1to1.jpg is the right-hand part of the result (last 512 old pixels
and the new strip) at 1:1, or the whole downscaled canvas for all-sides
expansion.
