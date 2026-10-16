# Runs inside GIMP (python-fu-eval): Generative Fill on different image types and selection shapes.
import json
import os
import time
import traceback

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
SRC = os.path.join(REPO, "tests/data/test-scene.png")
os.makedirs(OUT, exist_ok=True)
runs = []


def load():
    return Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(SRC))


def fill(case, image, drawables=None, remove=False):
    proc = Gimp.get_pdb().lookup_procedure("python-fu-openfill-generative-fill")
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_core_object_array("drawables", drawables or image.get_selected_drawables() or image.get_layers())
    config.set_property("prompt", "" if remove else "a large grey boulder on grass, photo")
    config.set_property("variations", 1)
    config.set_property("strength", 1.0)
    config.set_property("seed", 21)
    config.set_property("model", "active")
    config.set_property("remove", remove)
    t0 = time.time()
    try:
        result = proc.run(config)
        err = result.index(1) if result.length() > 1 else None
        status, msg = int(result.index(0)), getattr(err, "message", None)
    except Exception as exc:  # noqa: BLE001
        status, msg = -1, traceback.format_exc()[-600:]
    entry = {"case": case, "status": status, "seconds": round(time.time() - t0, 1), "error": msg,
             "base_type": str(image.get_base_type()), "precision": str(image.get_precision()),
             "layers": [lyr.get_name() for lyr in image.get_layers()]}
    runs.append(entry)
    print(f"[mac-types] {json.dumps(entry)[:500]}", flush=True)
    try:
        copy = image.duplicate()
        copy.flatten()
        if copy.get_base_type() != Gimp.ImageBaseType.RGB:
            copy.convert_rgb()
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, copy, Gio.File.new_for_path(os.path.join(OUT, f"{case}.png")))
        copy.delete()
    except Exception:  # noqa: BLE001
        print(f"[mac-types] {case}: could not export", flush=True)
    with open(os.path.join(OUT, "types-report.json"), "w") as fh:
        json.dump(runs, fh, indent=2)


SEL = (420, 300, 260, 200)

img = load()
img.convert_grayscale()
img.select_rectangle(Gimp.ChannelOps.REPLACE, *SEL)
fill("01-grayscale", img)

img = load()
img.convert_indexed(Gimp.ConvertDitherType.NONE, Gimp.ConvertPaletteType.GENERATE, 64, False, False, "")
img.select_rectangle(Gimp.ChannelOps.REPLACE, *SEL)
fill("02-indexed-64", img)

img = load()
img.convert_precision(Gimp.Precision.U16_NON_LINEAR)
img.select_rectangle(Gimp.ChannelOps.REPLACE, *SEL)
fill("03-16bit", img)

img = load()
layer = img.get_layers()[0]
layer.add_alpha()
img.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 300, 200)
layer.edit_clear()  # transparent corner inside the next selection's context
img.select_rectangle(Gimp.ChannelOps.REPLACE, 150, 100, 300, 250)
fill("04-rgba-transparent-area", img)

img = load()
top = Gimp.Layer.new(img, "overlay", img.get_width(), img.get_height(), Gimp.ImageType.RGBA_IMAGE, 60.0,
                     Gimp.LayerMode.NORMAL)
img.insert_layer(top, None, 0)
group = Gimp.GroupLayer.new(img, "group")
img.insert_layer(group, None, 0)
inner = Gimp.Layer.new(img, "inner", 200, 200, Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
img.insert_layer(inner, group, 0)
img.set_selected_layers([group])
img.select_rectangle(Gimp.ChannelOps.REPLACE, *SEL)
fill("05-group-layer-selected", img, drawables=[group])

img = load()
img.select_ellipse(Gimp.ChannelOps.REPLACE, 400, 280, 300, 240)
Gimp.Selection.feather(img, 40)
fill("06-feathered-ellipse", img)

img = load()
img.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 220, 180)
fill("07-selection-at-corner", img)

img = load()
img.select_rectangle(Gimp.ChannelOps.REPLACE, 100, 500, 120, 120)
img.select_rectangle(Gimp.ChannelOps.ADD, 800, 100, 120, 120)
fill("08-two-separate-areas", img, remove=True)
