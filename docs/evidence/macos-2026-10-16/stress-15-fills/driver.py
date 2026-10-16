# Runs inside GIMP (python-fu-eval): N consecutive fills (and removals) in one session; timing per run.
import json
import os
import random
import time

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
N = int(os.environ.get("OPENFILL_STRESS_N", "15"))
os.makedirs(OUT, exist_ok=True)
PROMPTS = ["a large grey boulder, photo", "a red wooden shed, photo", "a small pond with reeds, photo",
           "a white picket fence, photo", "a bicycle leaning on a post, photo"]
image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(os.path.join(REPO, "tests/data/test-scene.png")))
rng = random.Random(7)
runs = []
for i in range(N):
    w, h = rng.randint(96, 420), rng.randint(96, 320)
    x, y = rng.randint(0, image.get_width() - w), rng.randint(0, image.get_height() - h)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
    remove = i % 5 == 4
    proc = Gimp.get_pdb().lookup_procedure("python-fu-openfill-generative-fill")
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_core_object_array("drawables", image.get_layers())
    config.set_property("prompt", "" if remove else PROMPTS[i % len(PROMPTS)])
    config.set_property("variations", 1)
    config.set_property("strength", 1.0)
    config.set_property("seed", 1000 + i)
    config.set_property("model", "active")
    config.set_property("remove", remove)
    t0 = time.time()
    result = proc.run(config)
    err = result.index(1) if result.length() > 1 else None
    run = {"i": i, "rect": [x, y, w, h], "remove": remove, "status": int(result.index(0)),
           "seconds": round(time.time() - t0, 1), "error": getattr(err, "message", None), "layers": len(image.get_layers())}
    runs.append(run)
    print(f"[mac-stress] {json.dumps(run)}", flush=True)
    with open(os.path.join(OUT, "stress-report.json"), "w") as fh:
        json.dump(runs, fh, indent=2)
Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(os.path.join(OUT, "stress-final.png")))
