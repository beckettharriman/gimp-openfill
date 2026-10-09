# Runs inside a GUI gimp-3.2 (python-fu-eval). Warm-up fill, then the demo fill driven through the dialog.
import json, os, time, traceback
import gi
gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio
OUT = os.environ["SB_DEMO_OUT"]; HOOKS = os.environ["SB_TEST_UI_FILE"]
PHOTO = r"C:\AI\overnight-scratch\photos\landscape.jpg"
def ev(name, **kw):
    with open(os.path.join(OUT, "demo-events.jsonl"), "a") as fh:
        fh.write(json.dumps({"t": time.time(), "event": name, **kw}) + "\n")
def hooks(d):
    with open(HOOKS, "w") as fh: json.dump(d, fh)
def fill(image, mode, prompt, model):
    proc = Gimp.get_pdb().lookup_procedure("python-fu-stable-boy-generative-fill")
    cfg = proc.create_config()
    cfg.set_property("run-mode", mode); cfg.set_property("image", image)
    cfg.set_core_object_array("drawables", [image.get_layers()[0]])
    cfg.set_property("prompt", prompt); cfg.set_property("variations", 1); cfg.set_property("seed", 1234)
    cfg.set_property("model", model)
    t = time.perf_counter(); r = proc.run(cfg)
    return str(r.index(0)), round(time.perf_counter() - t, 3)
try:
    ev("start")
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(PHOTO))
    disp = Gimp.Display.new(image); Gimp.displays_flush()
    ev("display")
    if os.environ.get("SB_DEMO_WARMUP", "1") == "1":
        # warm-up: start the backend and load Juggernaut (non-interactive, no dialog), then undo it
        hooks({})
        image.select_rectangle(Gimp.ChannelOps.REPLACE, 1200, 900, 256, 256)
        image.undo_group_start()
        st, wall = fill(image, Gimp.RunMode.NONINTERACTIVE, "grass", "juggernaut-xl-v9")
        image.undo_group_end()
        for layer in image.get_layers()[:-1]:
            image.remove_layer(layer)
        Gimp.Selection.none(image); Gimp.displays_flush()
        ev("warmup_done", status=st, wall_s=wall)
    time.sleep(2)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 330, 70, 520, 330)
    Gimp.displays_flush()
    ev("selection")
    time.sleep(3)
    hooks({"type": "hot air balloon"})
    ev("dialog_call")
    st, wall = fill(image, Gimp.RunMode.INTERACTIVE, "", "juggernaut-xl-v9")
    Gimp.displays_flush()
    ev("demo_done", status=st, wall_s=wall)
    time.sleep(4)
    ev("end")
except Exception:
    ev("error", trace=traceback.format_exc())
finally:
    if os.environ.get("SB_DEMO_QUIT", "1") == "1":
        q = Gimp.get_pdb().lookup_procedure("gimp-quit"); c = q.create_config(); c.set_property("force", True); q.run(c)
