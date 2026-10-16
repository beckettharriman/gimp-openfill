# Runs inside GIMP (python-fu-eval): one non-interactive fill, prints the status and the message the user would get.
import os
import time

from gi.repository import Gimp, Gio

REPO = os.environ["OPENFILL_REPO"]
CASE = os.environ["OPENFILL_ROB_CASE"]
image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(os.path.join(REPO, "tests/data/test-scene.png")))
image.select_rectangle(Gimp.ChannelOps.REPLACE, 420, 300, 260, 200)


def run(name, **args):
    proc = Gimp.get_pdb().lookup_procedure(name)
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    if "image" in [p.get_name() for p in proc.get_arguments()]:
        config.set_property("image", image)
        config.set_core_object_array("drawables", image.get_layers())
    for k, v in args.items():
        config.set_property(k, v)
    t0 = time.time()
    result = proc.run(config)
    err = result.index(1) if result.length() > 1 else None
    print(f"[mac-rob] {CASE} {name}: status={result.index(0)} {time.time() - t0:.1f}s "
          f"error={getattr(err, 'message', err)!r} layers={len(image.get_layers())}", flush=True)


if CASE == "stop-backend":
    run("python-fu-openfill-generative-fill", prompt="a stone well, photo", variations=1, strength=1.0, seed=1,
        model="active")
    run("python-fu-openfill-stop-backend")
else:
    run("python-fu-openfill-generative-fill", prompt="a stone well, photo", variations=1, strength=1.0, seed=1,
        model="active")
