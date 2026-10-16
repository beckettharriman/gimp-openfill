# Runs inside GIMP (python-fu-eval). Downloads the starter models the way the Models tab does.
import json
import os
import sys
import time
import traceback

REPO = os.environ["OPENFILL_REPO"]
OUT = os.environ["OPENFILL_TEST_OUT"]
sys.path.insert(0, os.path.join(REPO, "gimp-openfill"))
os.makedirs(OUT, exist_ok=True)
report = {"steps": []}


def step(name, **info):
    info["time"] = time.strftime("%H:%M:%S")
    report["steps"].append({"step": name, **info})
    print(f"[mac-models] {name}: {json.dumps(info, default=str)[:400]}", flush=True)
    with open(os.path.join(OUT, "models-report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)


def wait_task(app, task_id, timeout=3600):
    t0, last = time.time(), 0
    while time.time() - t0 < timeout:
        status = app.task_status()
        cur = status.get("current") or {}
        if cur.get("task_id") == task_id and time.time() - last > 30:
            last = time.time()
            print(f"[mac-models]   {cur.get('state')} {cur.get('file')} {cur.get('done')}/{cur.get('total')}", flush=True)
        for h in status.get("history") or []:
            if h.get("task_id") == task_id:
                return h
        time.sleep(2)
    return {"state": "timeout"}


try:
    from openfill.app import App

    app = App()
    step("start", models_root=str(app.models_root), comfy_dir=app.settings.comfy_dir, comfy_ready=app.comfy_ready())
    for model_id in ("lama-big", "dreamshaper-8-inpainting"):
        nodes = app.nodes_to_install(model_id)
        step("nodes-needed", model=model_id, nodes=[(n.folder, n.commit) for n in nodes])
        if nodes:
            tid = app.queue_node_install(model_id)
            step("nodes-installed", model=model_id, result=wait_task(app, tid))
        ids = app.queue_download(model_id)
        step("download-queued", model=model_id, ids=ids)
        for tid in ids:
            step("download-finished", model=model_id, result=wait_task(app, tid))
    app.set_active("dreamshaper-8-inpainting")
    step("statuses", rows={r["id"]: r["status"] for r in App().model_rows()}, active=App().settings.active_model)
    report["ok"] = True
except Exception as err:  # noqa: BLE001
    report["ok"] = False
    report["error"] = traceback.format_exc()
    print(report["error"], file=sys.stderr, flush=True)
finally:
    with open(os.path.join(OUT, "models-report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
