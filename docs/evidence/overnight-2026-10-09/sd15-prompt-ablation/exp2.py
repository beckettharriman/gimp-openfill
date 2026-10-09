import sys, io, json
sys.path.insert(0, r"C:\repos\gimp-stable-boy\gimp-stable-boy")
from stable_boy import workflow
orig = workflow.build_fill
mode = sys.argv.pop(4)
def patched(req, *a, **k):
    g = orig(req, *a, **k)
    if mode == "nodiff":
        g["sampler"]["inputs"]["model"] = ["ckpt", 0]; g.pop("diff")
    if mode == "nonoisemask":
        g["encode"]["inputs"]["noise_mask"] = False
    if mode == "both":
        g["sampler"]["inputs"]["model"] = ["ckpt", 0]; g.pop("diff"); g["encode"]["inputs"]["noise_mask"] = False
    return g
workflow.build_fill = patched
exec(open("exp_fill.py").read().replace('variants = {', 'variants = {"%s": {"color_match": 0.0}} or {' % mode))
