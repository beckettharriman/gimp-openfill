# Runs inside a GUI GIMP (python-fu-eval): opens each OpenFill window interactively and screenshots it.
import json
import os
import subprocess
import sys
import time
import traceback

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
HOOKS = os.environ["OPENFILL_TEST_UI_FILE"]
os.makedirs(OUT, exist_ok=True)
report = {"cases": []}


def shots(name, delays):
    """Screen captures at the given seconds from now (taken by a detached shell, the dialog blocks us)."""
    cmd = "; ".join(f"sleep {d}; screencapture -x '{OUT}/{name}-{i}.png'" for i, d in enumerate(delays))
    subprocess.Popen(["sh", "-c", cmd])


def case(name, proc_name, image, hooks, delays, **args):
    with open(HOOKS, "w") as fh:
        json.dump(hooks, fh)
    shots(name, delays)
    proc = Gimp.get_pdb().lookup_procedure(proc_name)
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.INTERACTIVE)
    if image is not None:
        config.set_property("image", image)
        config.set_core_object_array("drawables", image.get_layers())
    for k, v in args.items():
        config.set_property(k, v)
    t0 = time.time()
    try:
        status = str(proc.run(config).index(0))
    except Exception as err:  # noqa: BLE001
        status = repr(err)
    entry = {"case": name, "status": status, "seconds": round(time.time() - t0, 1)}
    report["cases"].append(entry)
    print(f"[mac-gui] {entry}", flush=True)
    time.sleep(max(delays) - (time.time() - t0) + 1 if max(delays) > time.time() - t0 else 0.5)
    with open(os.path.join(OUT, "gui-report.json"), "w") as fh:
        json.dump(report, fh, indent=2)


try:
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(os.path.join(REPO, "tests/data/test-scene.png")))
    Gimp.Display.new(image)
    Gimp.displays_flush()
    time.sleep(3)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 420, 300, 260, 200)
    Gimp.displays_flush()

    case("01-fill-dialog", "python-fu-openfill-generative-fill", image, {"autoclose": 9}, [6])
    case("02-remove-dialog", "python-fu-openfill-generative-fill", image, {"autoclose": 9, "mode": "remove"}, [6])
    case("03-fill-advanced", "python-fu-openfill-generative-fill", image, {"autoclose": 9, "advanced": True}, [6])
    Gimp.Selection.none(image)
    case("04-expand-dialog", "python-fu-openfill-generative-expand", image, {"autoclose": 9}, [6])
    case("05-txt2img-dialog", "python-fu-openfill-text-to-image", image, {"autoclose": 9}, [6])
    case("06-settings-general", "python-fu-openfill-settings", None, {"autoclose": 9}, [6])
    case("07-settings-models", "python-fu-openfill-settings", None, {"autoclose": 12, "settings_tab": "models"}, [9])
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 420, 300, 260, 200)
    case(
        "08-real-fill-through-dialog",
        "python-fu-openfill-generative-fill",
        image,
        {"type": "a stone well with a wooden roof, photo", "click": "generate"},
        [5, 15, 35, 60],
    )
    Gimp.displays_flush()
    time.sleep(3)
    subprocess.run(["screencapture", "-x", os.path.join(OUT, "09-result.png")])
    report["layers"] = [layer.get_name() for layer in image.get_layers()]
    report["ok"] = True
except Exception:  # noqa: BLE001
    report["ok"] = False
    report["error"] = traceback.format_exc()
    print(report["error"], file=sys.stderr, flush=True)
finally:
    with open(os.path.join(OUT, "gui-report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
