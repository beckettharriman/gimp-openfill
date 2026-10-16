# Runs inside GIMP (python-fu-eval): fill and a large expand on a 4000x3000 image.
import json
import os
import time

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
os.makedirs(OUT, exist_ok=True)
image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(os.path.join(REPO, "tests/data/test-scene.png")))
image.scale(4000, 3000)
runs = []


def run(case, name, **args):
    proc = Gimp.get_pdb().lookup_procedure(name)
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_core_object_array("drawables", image.get_layers())
    for k, v in args.items():
        config.set_property(k, v)
    t0 = time.time()
    result = proc.run(config)
    err = result.index(1) if result.length() > 1 else None
    entry = {"case": case, "status": int(result.index(0)), "seconds": round(time.time() - t0, 1),
             "error": getattr(err, "message", None), "size": [image.get_width(), image.get_height()],
             "layers": [(lyr.get_name(), lyr.get_width(), lyr.get_height()) for lyr in image.get_layers()]}
    runs.append(entry)
    print(f"[mac-large] {json.dumps(entry)[:400]}", flush=True)
    copy = image.duplicate()
    copy.flatten()
    copy.scale(1024, int(1024 * copy.get_height() / copy.get_width()))
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, copy, Gio.File.new_for_path(os.path.join(OUT, f"{case}.png")))
    copy.delete()
    with open(os.path.join(OUT, "large-report.json"), "w") as fh:
        json.dump(runs, fh, indent=2)


image.select_rectangle(Gimp.ChannelOps.REPLACE, 1640, 1170, 1040, 800)  # the dark box, scaled
run("01-fill-4000x3000", "python-fu-openfill-generative-fill", prompt="a large grey boulder on grass, photo",
    negative="blurry", variations=1, strength=1.0, seed=11, model="active")
Gimp.Selection.none(image)
run("02-expand-right-1000", "python-fu-openfill-generative-expand", prompt="", negative="blurry", variations=1,
    left=0, top=0, right=1000, bottom=0, seed=12, model="active")
