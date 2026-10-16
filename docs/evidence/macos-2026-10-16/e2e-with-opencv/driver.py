# Runs inside GIMP (python-fu-eval): every OpenFill operation on macOS, non-interactively.
import json
import os
import sys
import time
import traceback

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
IMAGE = os.path.join(REPO, "tests", "data", "test-scene.png")
os.makedirs(OUT, exist_ok=True)
report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "gimp_pid": os.getppid(), "cases": []}


def save_report():
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)


def layers(image):
    out = []
    for layer in image.get_layers():
        out.append({"name": layer.get_name(), "mask": layer.get_mask() is not None, "group": layer.is_group_layer()})
        if layer.is_group_layer():
            out += [{"name": "  " + c.get_name()} for c in layer.get_children()]
    return out


def run(case, name, image, **args):
    proc = Gimp.get_pdb().lookup_procedure(name)
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_core_object_array("drawables", image.get_layers())
    for key, value in args.items():
        config.set_property(key, value)
    before = len(image.get_layers())
    t0 = time.time()
    try:
        result = proc.run(config)
        status = str(result.index(0))
        error = ""
        if result.length() > 1 and result.index(1) is not None:
            error = str(getattr(result.index(1), "message", result.index(1)))
    except Exception as err:  # noqa: BLE001
        status, error = "EXCEPTION", repr(err)
    entry = {
        "case": case,
        "procedure": name,
        "args": {k: v for k, v in args.items()},
        "status": status,
        "error": error,
        "seconds": round(time.time() - t0, 1),
        "layers_before": before,
        "layers": layers(image),
        "size": [image.get_width(), image.get_height()],
    }
    report["cases"].append(entry)
    print(f"[mac-e2e] {case}: {status} {entry['seconds']}s {error[:200]}", flush=True)
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(os.path.join(OUT, f"{case}.png")))
    save_report()
    return entry


try:
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(IMAGE))
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(os.path.join(OUT, "00-before.png")))

    image.select_rectangle(Gimp.ChannelOps.REPLACE, 420, 300, 260, 200)
    run("01-fill-prompt", "python-fu-openfill-generative-fill", image,
        prompt="a large grey boulder on grass, photo", negative="blurry, text", variations=1,
        strength=1.0, seed=12345, model="active")
    run("02-fill-again-warm", "python-fu-openfill-generative-fill", image,
        prompt="a small red wooden shed, photo", negative="blurry", variations=1,
        strength=1.0, seed=7, model="active")

    image.select_rectangle(Gimp.ChannelOps.REPLACE, 760, 60, 140, 140)
    run("03-remove-object", "python-fu-openfill-generative-fill", image,
        prompt="", negative="", variations=1, strength=1.0, seed=1, model="active", remove=True)

    image.select_rectangle(Gimp.ChannelOps.REPLACE, 80, 480, 300, 220)
    run("04-fill-variations-3", "python-fu-openfill-generative-fill", image,
        prompt="a wooden picnic table on grass, photo", negative="blurry", variations=3,
        strength=1.0, seed=99, model="active")

    Gimp.Selection.none(image)
    run("05-expand-right-256", "python-fu-openfill-generative-expand", image,
        prompt="", negative="blurry", variations=1, left=0, top=0, right=256, bottom=0, seed=7, model="active")

    run("06-text-to-image-layer", "python-fu-openfill-text-to-image", image,
        prompt="a small wooden cabin in a meadow, photo", negative="blurry", variations=1,
        width=512, height=384, target="layer", seed=3, model="active")

    image.select_rectangle(Gimp.ChannelOps.REPLACE, 10, 10, 24, 24)
    run("07-tiny-selection", "python-fu-openfill-generative-fill", image,
        prompt="a bird", negative="", variations=1, strength=1.0, seed=2, model="active")

    Gimp.Selection.none(image)
    run("08-fill-without-selection", "python-fu-openfill-generative-fill", image,
        prompt="a bird", negative="", variations=1, strength=1.0, seed=2, model="active")
    report["ok"] = True
except Exception:  # noqa: BLE001
    report["ok"] = False
    report["error"] = traceback.format_exc()
    print(report["error"], file=sys.stderr, flush=True)
finally:
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_report()
