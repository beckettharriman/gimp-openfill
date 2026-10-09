"""Ablation of the fill graph on a dumped crop: which step drops the prompt?"""
import io, json, sys, time, copy
sys.path.insert(0, r"C:\repos\gimp-stable-boy\gimp-stable-boy")
import numpy as np
from PIL import Image
from stable_boy.backend import InpaintRequest, ModelSpec, Sampling
from stable_boy.backends.comfy import ComfyBackend
dump = sys.argv[1]; out = sys.argv[2]; prompt = sys.argv[3] if len(sys.argv) > 3 else "red brick wall"
req_info = json.load(open(dump + "/request.json"))
img = open(dump + "/sent-image.png", "rb").read(); msk = open(dump + "/sent-mask.png", "rb").read()
W, H = Image.open(io.BytesIO(img)).size
ww, wh = req_info["work"]
be = ComfyBackend("http://127.0.0.1:8188")
mask = np.array(Image.open(io.BytesIO(msk))) > 128
src = np.array(Image.open(io.BytesIO(img)).convert("RGB")).astype(int)
variants = {
 "plugin": {},
 "no_colormatch": {"color_match": 0.0},
 "no_prefill": {"prefill": False},
 "neither": {"color_match": 0.0, "prefill": False},
 "border_prefill": {"prefill_style": "border"},
}
res = {}
for name, kw in variants.items():
    r = InpaintRequest(image_png=img, mask_png=msk, width=W, height=H, work_width=ww, work_height=wh,
                       prompt=prompt, negative="blurry", model=ModelSpec(checkpoint="sd-v1-5-inpainting.ckpt", arch="sd15"),
                       sampling=Sampling(steps=25, cfg=7.0, sampler="dpmpp_2m", scheduler="karras", denoise=1.0, seed=1234, batch=1),
                       grow=req_info["grow"], feather=req_info["feather"], prefill=kw.get("prefill", True),
                       prefill_style=kw.get("prefill_style", "blur"), color_match=kw.get("color_match", 1.0))
    t = time.time(); g = be.inpaint(r)
    a = np.array(Image.open(io.BytesIO(g.images[0])).convert("RGB")).astype(int)
    Image.fromarray(a.astype(np.uint8)).save(f"{out}/{name}.png")
    res[name] = {"mad_in_mask": round(float(np.abs(a - src)[mask].mean()), 2), "s": round(time.time() - t, 1)}
    print(name, res[name], flush=True)
json.dump(res, open(f"{out}/results.json", "w"), indent=1)
