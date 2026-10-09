import json, sys, re
from pathlib import Path
sys.path.insert(0, r"C:\AI\overnight-scratch\perf")
from analyse import ts
d = Path(sys.argv[1]); meta = json.loads((d / "launch-meta.json").read_text())
res = [json.loads(l) for l in open(d / "perf-results.jsonl")]
img = next(r for r in res if r["event"] == "image"); first = next(r for r in res if r["event"] == "fill")
lines = first["log"].splitlines(); f = lambda p: next((ts(l) for l in lines if p in l), None)
t0 = meta["t_launch"]
out = {"session": d.name, "case": first["id"], "launch_to_image_ready_s": round(img["t"] - t0, 2),
       "launch_to_fill_call_s": round(first["t_start"] - t0, 2),
       "fill_call_to_supervisor_launch_s": round(f("launching supervisor") - first["t_start"], 2),
       "supervisor_launch_to_backend_ready_s": round(f("backend ready") - f("launching supervisor"), 2),
       "launch_to_backend_ready_s": round(f("backend ready") - t0, 2),
       "backend_ready_to_result_downloaded_s": round(f("timing: queue->") - f("backend ready"), 2),
       "launch_to_first_fill_done_s": round(first["t_end"] - t0, 2),
       "first_fill_wall_s": first["wall_s"]}
m = re.search(r"queue->first step ([\d.]+) s, sampling ([\d.]+)", first["log"]); out["queue_to_first_step_s"] = float(m.group(1)); out["sampling_s"] = float(m.group(2))
json.dump(out, open(d / "cold-start.json", "w"), indent=1); print(out)
