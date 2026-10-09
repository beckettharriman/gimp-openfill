# Model benchmark, 2026-10-09 (daytime)

Every inpaint, removal and outpaint model this machine (RTX 4070 Laptop, 8 GB VRAM, 32 GB RAM) can run, driven through the plug-in itself in `gimp-console-3.2.exe` (non-interactive Generative Fill and Generative Expand procedures, plug-in defaults: 25 steps, CFG 7, dpmpp_2m karras, seed 1234), over 100 cases on real CC0 or public-domain photos. Images are not scored here; separate judge lanes score them from `index.json`.

Generated 2026-10-09 17:48 from `index.json` (305 model/case results).

## Models

| Model | Family | Files on disk | Cases run (ok / total applicable) | VRAM peak (MiB, whole GPU) | Median s/case: remove / replace / fill / expand 1 side / expand all | First case (cold) s | Offloading | Fits 8 GB without offloading |
|---|---|---|---|---|---|---|---|---|
| `lama-big` | inpaint_model | 0.2 GB | 33 / 33 | 1292 | 2.8 (n=32) / - / - / - / - | 40.0 | not detected | yes |
| `mat-places512` | inpaint_model | 0.1 GB | 33 / 33 | 2638 | 3.1 (n=32) / - / - / - / - | 31.5 | not detected | yes |
| `sd15-inpainting` | sd15 | 4.3 GB | 33 / 100 | 4538 | 11.1 (n=12) / 8.3 (n=14) / 9.5 (n=2) / 14.6 (n=2) / 14.2 (n=2) | 56.1 | not detected | yes |
| `realistic-vision-v6-inpainting` | sd15 | 2.1 GB | 33 / 100 | 4828 | 11.2 (n=12) / 8.5 (n=14) / 9.5 (n=2) / 14.0 (n=2) / 14.1 (n=2) | 48.8 | not detected | yes |
| `dreamshaper-8-inpainting` | sd15 | 2.1 GB | 33 / 100 | 4444 | 10.6 (n=12) / 7.6 (n=14) / 9.0 (n=2) / 13.7 (n=2) / 14.0 (n=2) | 38.8 | not detected | yes |
| `sdxl-base` | sdxl | 8.3 GB | 32 / 100 | 7767 | 26.9 (n=12) / 25.9 (n=14) / 30.4 (n=2) / 33.5 (n=2) / 28.1 (n=1) | 33.8 | not detected | yes, near the limit |
| `juggernaut-xl-v9` | sdxl | 8.4 GB | 33 / 100 | 7852 | 25.5 (n=12) / 23.1 (n=14) / 32.5 (n=2) / 27.9 (n=2) / 30.5 (n=2) | 104.7 | not detected | yes, near the limit |
| `realvisxl-v5` | sdxl | 8.3 GB | 33 / 100 | 7802 | 29.1 (n=11) / 26.5 (n=14) / 35.5 (n=2) / 32.0 (n=2) / 31.5 (n=2) | 89.8, 120.8 | not detected | yes, near the limit |
| `flux1-fill-dev-gguf-q4` | flux | 10.8 GB | 28 / 100 | 7858 | 110.4 (n=8) / 108.0 (n=11) / 128.1 (n=2) / 133.7 (n=2) / 128.3 (n=2) | 129.5, 122.0, 151.3 | yes (logged) | no |
| `qwen-image-edit-2511-gguf-q4` | qwen_image | 22.9 GB | 0 / 100 | 7845 | - / - / - / - / - | - | unknown (no case finished) | no case finished |

VRAM peak is the highest `nvidia-smi` memory.used sample (1 s interval) while the case ran, for the whole GPU (the desktop holds about 0.8 to 1.0 GB). Seconds are the wall time of the plug-in procedure call (upload, sampling, download, layer creation). Medians exclude the first case of each GIMP process, which includes loading the model into ComfyUI (listed separately as cold). The expand code of the plug-in was being changed by another lane while this benchmark ran, so expand timings and results depend on the code version: each case's `plugin-log.txt` shows the path taken (one pass, or one side at a time) and `report.json` carries `plugin_code_sha256_12`, short hashes of the plug-in modules when the case ran (null for cases run before 13:15).

Offloading: ComfyUI 0.39 loads weights dynamically and prints 'loaded partially; ... MB offloaded' only when the model being run does not fit (its 'Unloaded partially' lines are evictions of other models and are not counted). The column is judged from evidence: 'yes (logged)' when ComfyUI printed an offload line, 'yes (model N MB > 8 GB)' when one model's staged weights alone exceed the card, 'likely' when the whole-GPU peak came within 300 MiB of 8188 MiB, otherwise 'not detected'. 'Fits 8 GB' is the inverse; 'near the limit' marks peaks within 600 MiB of the total.

### Failures and errors

- `sdxl-base` / `landscape-expand-all`: execution-error - The AI backend is not available: GET /history/a9afed4b-d453-4302-a4f4-1cf477e70746 failed: <urlopen error [WinError 10060] A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to re
- `flux1-fill-dev-gguf-q4` / `face-remove-small-patch`: execution-error - The request timed out (no result after 153 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `flux1-fill-dev-gguf-q4` / `landscape-replace-balloon`: execution-error - The request timed out (no result after 138 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `flux1-fill-dev-gguf-q4` / `signage-replace-text`: execution-error - The request timed out (no result after 135 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `face-replace-sunglasses`: execution-error - The request timed out (no result after 142 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `food-replace-watermelon`: execution-error - The request timed out (no result after 145 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `interior-expand-left`: execution-error - The request timed out (no result after 166 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `interior-remove-small-portrait`: execution-error - The request timed out (no result after 141 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `landscape-replace-balloon`: execution-error - The request timed out (no result after 138 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `product2-material-suede`: execution-error - The request timed out (no result after 149 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `text-replace-text-20h`: execution-error - The request timed out (no result after 145 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `qwen-image-edit-2511-gguf-q4` / `water-replace-canoe`: execution-error - The request timed out (no result after 139 s). Try a smaller selection or fewer variations, or raise "Generation time limit" in Filters > AI > Generative Fill Settings > Connection and troubleshooting (0 means it is estimated per request).
- `flux1-fill-dev-gguf-q4` / `clouds-remove-large-palm`: excluded from the table; the plug-in at 60636cc routed this empty-prompt fill to `lama-big`.
- `flux1-fill-dev-gguf-q4` / `illustration-remove-large-baby`: excluded from the table; the plug-in at 60636cc routed this empty-prompt fill to `lama-big`.

## Cases

| Case | Image | Operation | Selection (px, x y w h) | Size class | Feather | Prompt |
|---|---|---|---|---|---|---|
| `face-remove-small-patch` | face.jpg | remove-small | 816 1485 324 210 | small | 0 | (empty: remove) |
| `face-remove-large-shuttle` | face.jpg | remove-large | 0 900 720 2040 | large | 12 | (empty: remove) |
| `face-replace-sunglasses` | face.jpg | replace-object | 1104 570 600 180 | small | 0 | dark aviator sunglasses |
| `face-material-red-leather` | face.jpg | material | 1488 1200 792 1350 | large | 24 | red leather jacket sleeve |
| `face-damaged-tiny-hair` | face.jpg | damaged | 1272 300 72 75 | tiny | 0 | short dark brown hair |
| `face-expand-right` | face.jpg | expand-side | margins L0 T0 R384 B0 | - | - | studio portrait of an astronaut in a blue flight suit, dark grey backdrop, photo |
| `landscape-remove-small-barn` | landscape.jpg | remove-small | 893 454 269 130 | small | 0 | (empty: remove) |
| `landscape-remove-large-birch` | landscape.jpg | remove-large | 1517 0 403 1440 | large | 0 | (empty: remove) |
| `landscape-replace-balloon` | landscape.jpg | replace-into-empty | 480 43 346 288 | medium | 0 | a colorful hot air balloon |
| `landscape-replace-horse` | landscape.jpg | replace-into-empty | 576 749 346 317 | medium | 16 | a brown horse grazing |
| `landscape-damaged-tiny-grass` | landscape.jpg | damaged | 960 1152 38 43 | tiny | 0 | green grass |
| `landscape-expand-all` | landscape.jpg | expand-all | margins L256 T256 R256 B256 | - | - | green meadow and evening sky with trees, photo |
| `architecture-remove-small-ac` | architecture.jpg | remove-small | 990 426 180 191 | small | 0 | (empty: remove) |
| `architecture-remove-large-laundry` | architecture.jpg | remove-large | 400 573 540 318 | medium | 0 | (empty: remove) |
| `architecture-replace-flowerbox` | architecture.jpg | replace-object | 180 458 200 140 | small | 0 | a window box with red geraniums |
| `architecture-material-roof-tiles` | architecture.jpg | material | 160 51 1620 89 | medium | 0 | red clay roof tiles |
| `architecture-expand-top` | architecture.jpg | expand-side | margins L0 T256 R0 B0 | - | - | old apartment building facade with windows and laundry, photo |
| `text-remove-small-logo` | text.jpg | remove-small | 58 1215 672 86 | medium | 0 | (empty: remove) |
| `text-remove-large-signs` | text.jpg | remove-large | 326 929 1267 243 | large | 0 | (empty: remove) |
| `text-replace-text-20h` | text.jpg | replace-object | 1363 743 346 143 | small | 0 | the text 20H in bold black italic letters |
| `text-damaged-tiny-yellow` | text.jpg | damaged | 960 307 58 43 | tiny | 0 | plain yellow painted metal |
| `text-expand-bottom` | text.jpg | expand-side | margins L0 T0 R0 B256 | - | - | yellow road sign with black lettering in a metal frame, on a city street |
| `product-remove-small-handle` | product.jpg | remove-small | 154 324 154 188 | medium | 8 | (empty: remove) |
| `product-remove-large-cup` | product.jpg | remove-large | 115 119 794 614 | huge | 0 | (empty: remove) |
| `product-replace-spoon` | product.jpg | replace-into-empty | 922 384 256 256 | medium | 0 | a silver teaspoon |
| `product-material-coffee` | product.jpg | material | 282 179 461 205 | large | 0 | black coffee with milk foam |
| `product-expand-all` | product.jpg | expand-all | margins L192 T192 R192 B192 | - | - | white tea cup on a saucer, plain white background, product photo |
| `fabric-damaged-large` | fabric.jpg | damaged | 576 503 672 587 | large | 0 | close-up of tweed wool fabric weave |
| `fabric-damaged-huge` | fabric.jpg | damaged | 154 134 1613 1409 | huge | 32 | close-up of tweed wool fabric weave |
| `fabric-replace-button` | fabric.jpg | replace-into-empty | 864 755 192 168 | small | 0 | a round brass button |
| `fabric-remove-tiny` | fabric.jpg | remove-small | 960 838 29 25 | tiny | 0 | (empty: remove) |
| `fabric-expand-right` | fabric.jpg | expand-side | margins L0 T0 R256 B0 | - | - | close-up of tweed wool fabric weave |
| `portrait-remove-small-badge` | portrait.jpg | remove-small | 826 1716 326 322 | medium | 0 | (empty: remove) |
| `portrait-remove-large-shuttle` | portrait.jpg | remove-large | 77 912 614 1555 | large | 12 | (empty: remove) |
| `portrait-replace-earring` | portrait.jpg | replace-object | 1248 1072 77 94 | tiny | 0 | a small gold hoop earring |
| `portrait-material-velvet` | portrait.jpg | material | 1190 1662 691 885 | large | 24 | green velvet fabric |
| `portrait-expand-all` | portrait.jpg | expand-all | margins L256 T256 R256 B256 | - | - | studio portrait of a smiling woman astronaut in a blue flight suit, grey backdrop, photo |
| `hands-replace-strawberry` | hands.jpg | replace-object | 730 1267 557 490 | medium | 0 | a ripe red strawberry |
| `hands-remove-large-bracelet` | hands.jpg | remove-large | 710 1584 864 576 | large | 0 | (empty: remove) |
| `hands-damaged-tiny-thumbnail` | hands.jpg | damaged | 1075 893 115 115 | small | 0 | fingertip with a clean fingernail |
| `hands-expand-left` | hands.jpg | expand-side | margins L384 T0 R0 B0 | - | - | a hand holding a red pepper, blurred green garden background, photo |
| `pet-remove-small-scar` | pet.jpg | remove-small | 1075 794 77 102 | small | 0 | (empty: remove) |
| `pet-replace-ladybug` | pet.jpg | replace-into-empty | 1651 960 192 192 | small | 0 | a red ladybug on a blade of grass |
| `pet-material-tabby` | pet.jpg | material | 0 192 576 640 | large | 24 | orange tabby cat fur |
| `pet-expand-top` | pet.jpg | expand-side | margins L0 T256 R0 B0 | - | - | a grey cat lying on green grass, photo |
| `food-remove-small-fork` | food.jpg | remove-small | 442 644 115 372 | small | 0 | (empty: remove) |
| `food-remove-large-milk` | food.jpg | remove-large | 1306 372 288 372 | medium | 0 | (empty: remove) |
| `food-replace-watermelon` | food.jpg | replace-object | 806 582 384 161 | medium | 0 | a slice of watermelon |
| `food-replace-vase` | food.jpg | replace-into-empty | 192 99 288 434 | medium | 0 | a small glass vase with a red rose |
| `food-material-checkered` | food.jpg | material | 154 1016 1613 124 | large | 0 | a blue and white checkered cloth placemat |
| `interior-remove-small-portrait` | interior.jpg | remove-small | 893 512 163 256 | small | 0 | (empty: remove) |
| `interior-remove-large-tv` | interior.jpg | remove-large | 1498 742 422 243 | medium | 0 | (empty: remove) |
| `interior-replace-fire` | interior.jpg | replace-object | 346 960 269 230 | medium | 0 | a crackling log fire in the fireplace |
| `interior-material-marble` | interior.jpg | material | 902 1050 346 102 | small | 0 | a white marble table top |
| `interior-expand-left` | interior.jpg | expand-side | margins L384 T0 R0 B0 | - | - | elegant drawing room with blue damask walls, gold molding and red chairs, photo |
| `night-street-remove-small-light` | night-street.jpg | remove-small | 922 114 154 216 | small | 0 | (empty: remove) |
| `night-street-remove-large-car` | night-street.jpg | remove-large | 192 913 806 355 | large | 0 | (empty: remove) |
| `night-street-replace-moon` | night-street.jpg | replace-into-empty | 384 38 230 228 | medium | 0 | a full moon in the night sky |
| `night-street-replace-neon` | night-street.jpg | replace-object | 422 456 326 76 | small | 0 | a glowing white neon sign that says BOOKS |
| `night-street-expand-top` | night-street.jpg | expand-side | margins L0 T256 R0 B0 | - | - | city street at night under a dark sky, photo |
| `water-remove-small-plants` | water.jpg | remove-small | 806 1088 384 192 | medium | 0 | (empty: remove) |
| `water-replace-canoe` | water.jpg | replace-into-empty | 576 704 384 102 | small | 0 | a red canoe on the calm lake |
| `water-damaged-large` | water.jpg | damaged | 96 640 768 384 | large | 32 | calm lake water reflecting white clouds |
| `water-expand-all` | water.jpg | expand-all | margins L256 T256 R256 B256 | - | - | mountain lake with reflections of clouds and dark forest, photo |
| `snow-remove-small-sun` | snow.jpg | remove-small | 1267 230 173 166 | small | 0 | (empty: remove) |
| `snow-replace-fox` | snow.jpg | replace-into-empty | 384 1022 422 217 | medium | 0 | a red fox walking on the snow |
| `snow-damaged-tiny` | snow.jpg | damaged | 576 1150 38 38 | tiny | 0 | fresh white snow |
| `snow-expand-bottom` | snow.jpg | expand-side | margins L0 T0 R0 B256 | - | - | snow covered ground with blue tree shadows on a sunny winter day, photo |
| `crowd-remove-small-screen` | crowd.jpg | remove-small | 634 986 173 102 | small | 0 | (empty: remove) |
| `crowd-remove-large-monument` | crowd.jpg | remove-large | 1190 51 96 768 | medium | 0 | (empty: remove) |
| `crowd-replace-birds` | crowd.jpg | replace-into-empty | 192 64 576 320 | medium | 0 | a large flock of birds flying |
| `crowd-damaged-people` | crowd.jpg | damaged | 768 1088 384 154 | medium | 8 | a dense crowd of people in winter coats |
| `crowd-expand-left` | crowd.jpg | expand-side | margins L256 T0 R0 B0 | - | - | huge crowd on the National Mall in winter, city skyline, photo |
| `product2-remove-small-knob` | product2.jpg | remove-small | 173 289 115 130 | small | 0 | (empty: remove) |
| `product2-replace-wallet` | product2.jpg | replace-into-empty | 1190 72 576 289 | medium | 0 | a brown leather wallet |
| `product2-material-suede` | product2.jpg | material | 96 289 1690 866 | huge | 16 | a brown suede leather shoe |
| `product2-expand-all` | product2.jpg | expand-all | margins L192 T192 R192 B192 | - | - | a black leather shoe on a plain white background, product photo |
| `handwriting-remove-small-stain` | handwriting.jpg | remove-small | 231 38 84 64 | small | 0 | (empty: remove) |
| `handwriting-remove-large-lines` | handwriting.jpg | remove-large | 53 602 947 154 | large | 0 | (empty: remove) |
| `handwriting-replace-word` | handwriting.jpg | replace-object | 736 51 263 90 | small | 0 | the handwritten word Second in brown ink cursive |
| `handwriting-damaged-edge` | handwriting.jpg | damaged | 0 768 63 384 | small | 0 | aged yellowed paper |
| `signage-remove-small-logo` | signage.jpg | remove-small | 1210 460 115 192 | small | 0 | (empty: remove) |
| `signage-remove-large-sign` | signage.jpg | remove-large | 557 383 826 805 | large | 0 | (empty: remove) |
| `signage-replace-text` | signage.jpg | replace-object | 653 690 518 77 | small | 0 | white text that says Desert Museum |
| `signage-replace-cactus` | signage.jpg | replace-into-empty | 1498 843 230 319 | medium | 0 | a saguaro cactus |
| `signage-expand-right` | signage.jpg | expand-side | margins L0 T0 R384 B0 | - | - | desert road at sunset with mountains, photo |
| `texture-damaged-medium` | texture.jpg | damaged | 768 576 288 216 | medium | 0 | red brick wall |
| `texture-damaged-huge` | texture.jpg | damaged | 96 72 1728 1296 | huge | 32 | red brick wall |
| `texture-replace-window` | texture.jpg | replace-into-empty | 672 432 480 432 | medium | 0 | a small square window with a white frame |
| `texture-material-stone` | texture.jpg | material | 1152 288 576 864 | large | 16 | grey stone wall |
| `texture-expand-all` | texture.jpg | expand-all | margins L256 T256 R256 B256 | - | - | red brick wall |
| `illustration-remove-large-baby` | illustration.jpg | remove-large | 1267 1238 461 659 | medium | 0 | (empty: remove) |
| `illustration-remove-small-stamp` | illustration.jpg | remove-small | 1382 817 211 158 | small | 0 | (empty: remove) |
| `illustration-replace-top-hat` | illustration.jpg | replace-object | 1056 790 250 184 | small | 0 | a black top hat |
| `illustration-replace-caption` | illustration.jpg | replace-object | 730 2503 461 79 | small | 0 | the text MAMAS PET in small serif capital letters |
| `illustration-expand-bottom` | illustration.jpg | expand-side | margins L0 T0 R0 B256 | - | - | vintage color lithograph cartoon on cream paper |
| `clouds-remove-large-palm` | clouds.jpg | remove-large | 1118 0 271 1027 | large | 0 | (empty: remove) |
| `clouds-replace-airplane` | clouds.jpg | replace-into-empty | 1353 181 216 121 | small | 0 | a small airplane flying |
| `clouds-damaged-cloud` | clouds.jpg | damaged | 451 302 541 302 | medium | 24 | towering cumulus cloud lit by the sun |
| `clouds-expand-top` | clouds.jpg | expand-side | margins L0 T256 R0 B0 | - | - | deep blue sky with scattered clouds |

## Downloads, gating and what was skipped

- **FLUX.1 VAE (`vae/ae.safetensors`).** The catalog points at
  `black-forest-labs/FLUX.1-schnell`, which is gated on Hugging Face
  ("auto" approval: the user must log in and accept the terms; an
  anonymous request returns HTTP 401). The identical file (same size
  335,304,388 bytes and the same SHA-256 `afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38` as published
  in the LFS metadata) is served ungated and Apache-2.0 by the ComfyUI
  project at
  `https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors`.
  It was downloaded from there and verified against the catalog checksum,
  so the FLUX.1 Fill GGUF entry could be benchmarked without a token.
  Without that mirror a user would have to visit
  https://huggingface.co/black-forest-labs/FLUX.1-schnell, log in, accept
  the license, create a read token at
  https://huggingface.co/settings/tokens and paste it into Settings >
  Models (the token field appears for gated models).
- **First-party FLUX.1 Fill [dev] (`flux1-fill-dev`, 29.3 GB, gated,
  16 GB VRAM minimum)** was not downloaded: the diffusion model is gated
  at https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev (accept the
  license there, then a read token as above) and the GGUF Q4 entry covers
  the same model on this card.
- **Qwen-Image-Edit-2511 GGUF Q4** files are ungated (unsloth and Comfy-Org
  repositories, Apache-2.0).
- **Community checkpoints added to the catalog:** Realistic Vision V6.0 B1
  inpainting fp16 (SG161222, CreativeML OpenRAIL-M), DreamShaper 8
  inpainting (Lykon, CreativeML OpenRAIL-M per the author's
  `Lykon/dreamshaper-8-inpainting` model card; the single-file checkpoint
  comes from the author's `Lykon/DreamShaper` repository, whose card tag
  is "other"), RealVisXL V5.0 fp16 (SG161222, openrail++). No Turbo or
  Lightning variant was used (the Fooocus patch needs regular SDXL).

## Coverage, and what was not run

- LaMa and MAT ran all 33 remove cases. sd15-inpainting,
  realistic-vision-v6, dreamshaper-8, juggernaut-xl-v9, realvisxl-v5,
  sdxl-base and FLUX GGUF Q4 ran the 33 core cases (`"core": true` in the
  spec). Qwen ran a mini set of 8 core cases. The 67 non-core cases were
  not run for any model: the orchestrator stopped them at 16:30 to save
  time, and they can run later on the final pipeline.
- **Plug-in version.** The plug-in folder is a junction into the
  repository, which other lanes changed during the run. Each index entry
  carries `plugin_commit` (repository HEAD when the case started, from
  the git reflog) and `plugin_code_sha256_12` (hashes of the plug-in
  modules at process start, from 13:15; these also catch uncommitted
  edits). Commits were 0e3c67a (LaMa, MAT, 4 SD 1.5 cases), 4438ce3 and
  f310330 (SD 1.5 family, Juggernaut, RealVisXL, first FLUX), 095af15
  (sdxl-base, Qwen first batch, FLUX), 8176966 (most Qwen and late FLUX
  cases) and 60636cc (the merged pipeline: border pre-fill, minimum
  working scale with tiling, empty prompts routed to LaMa, grain
  matching, longer cold-load timeout) for the last 2 FLUX cases. The
  Qwen cases and the late FLUX cases therefore ran on newer pipeline
  code than the SD 1.5 and SDXL cases. On 60636cc the two FLUX
  empty-prompt remove cases (clouds-remove-large-palm,
  illustration-remove-large-baby) were routed to LaMa. They are excluded
  from the FLUX numbers.
- Remove cases on generative models use an empty prompt with
  `remove=false`. That is the plug-in's "empty prompt" removal path. Mode
  "Remove object" (`remove=true`) always switches to MAT or LaMa when one
  is installed, so it cannot test a generative model.
- GPU time was shared with two other lanes (25-minute lock slices).
  Benchmark wall time 12:37 to about 17:30.

## Findings for the plug-in

- **The time limit is too short for FLUX and Qwen on 8 GB.** With
  `request_timeout` 0, the plug-in estimates a time limit per request
  (138 to 153 s here). It does not allow for loading the model.
  - FLUX: the first case of each cold GIMP process failed with "The
    request timed out (no result after 153 s)". Warm FLUX cases took 96
    to 144 s, so they fit.
  - Qwen-Image-Edit-2511 Q4: every case runs past the limit. The plug-in
    then interrupts the ComfyUI job, so it cannot complete from the
    plug-in with default settings.
  - One Qwen job (text-replace-text-20h) that ComfyUI finished after the
    test GIMP was stopped took 663.8 s for 25 steps. Whole-GPU peak was
    7734 MiB. See
    `qwen-image-edit-2511-gguf-q4/text-replace-text-20h/NOTE.txt`.
  - Suggested change (not made; owned by other lanes): add a model-load
    allowance per architecture to the estimate (FLUX and Qwen at least
    +120 s for the first request after a model switch), or start the
    clock at the first progress event.
- **FLUX offloads on this card.** ComfyUI logs "loaded partially; ...
  959.42 MB offloaded" in the FLUX cases. The Qwen model files (13.2 GB
  GGUF plus a 9.4 GB text encoder) cannot be resident in 8 GB. The
  per-case ComfyUI log slices of the Qwen cases were empty (the log had
  not been flushed when the plug-in timed out), so no offload line was
  captured for Qwen. The SDXL models peak at 7.8 GB whole-GPU without an
  offload line.

## Files

- `index.json`: one entry per (model, case) with status, seconds, working size, VRAM, staged model sizes, offload and OOM flags and paths.
- `<model>/<case>/`: `before.jpg`, `after.jpg` (longest side 1024), `crop.jpg` (1:1 crop of the edited region of the result, at most 1024 px), `crop-before.jpg` (same crop of the input, fills only), `compare.jpg` (before | after | crop), `report.json`, `plugin-log.txt`, `comfy-log.txt`.
- `benchmark-spec.json`: the cases. Photo sources and licenses: `photos-SOURCES.md`.
- Harness: `tests/gimp_batch_benchmark.py` (inside GIMP); the launcher, sampler and full-size results are kept in the scratch folder.
