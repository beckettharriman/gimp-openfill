# FLUX Fill: hard mask and no DifferentialDiffusion on the four flat-field failures

Question: do the flat discs and slabs in the FLUX results come from the graph (soft model mask plus DifferentialDiffusion)? Experiment: the same four cases (fabric-damaged-large, texture-damaged-huge, product-remove-large-cup, architecture-remove-small-ac), the same seed, the same selection and settings, with the model mask kept hard (grown, not blurred, as for LaMa and SD 1.5 fills) and the DifferentialDiffusion node removed from the FLUX graph. The removal cases were forced to FLUX for the experiment only (the plug-in normally sends them to LaMa). The debug request dump of the run confirms the graph had no DifferentialDiffusion node.

Result: pairwise against the old results (sheet.jpg, left old, right new): 4 same, 0 better, 0 worse. The tweed is still a flat salmon disc, the brick a flat grey slab, the cup a grey-brown blob, the AC unit a pink box; the pixels differ only in grain. Times: 72 to 106 s warm (205 s cold for the first case).

Verdict: the graph change is not adopted and was reverted. The flat fields come from the model and the Q4 quantisation with the guidance setting, not from the mask or the weighting. FLUX stays opt-in.

Also checked: the plug-in's FLUX timeout estimate in these runs was 322 to 343 s warm and 600 s cold (model-file load time included), and the new 240 s floor covers small requests.
