"""Parse perf-results.jsonl into per-case phase splits (CSV + JSON)."""
import json, re, sys, time, csv
from pathlib import Path

TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ")

def ts(line):
    m = TS.match(line)
    if not m: return None
    return time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) + int(m.group(2)) / 1000

def parse(r):
    out = {k: r[k] for k in ("id", "model", "sel", "remove", "wall_s", "status")}
    lines = r["log"].splitlines()
    find = lambda pat: next((l for l in lines if pat in l), None)
    fill = find("] fill: selection="); up = find("timing: upload"); q = find("timing: queue->")
    done = find("fill: done"); ready = find("backend ready")
    if fill:
        m = re.search(r"working=(\d+)x(\d+)", fill); out["working"] = f"{m.group(1)}x{m.group(2)}"
        m = re.search(r"context=Rect\(x=\d+, y=\d+, width=(\d+), height=(\d+)\)", fill); out["context"] = f"{m.group(1)}x{m.group(2)}"
    if up:
        m = re.search(r"image=(\d+) mask=(\d+) bytes in ([\d.]+) s", up)
        out["image_png_bytes"], out["mask_png_bytes"], out["upload_s"] = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if q:
        m = re.search(r"first step ([\d.]+) s, sampling ([\d.]+) s, download (\d+) bytes in ([\d.]+) s", q)
        out["queue_to_first_step_s"], out["sampling_s"], out["result_png_bytes"], out["download_s"] = float(m.group(1)), float(m.group(2)), int(m.group(3)), float(m.group(4))
    if fill and up:
        out["startup_s"] = round(ts(fill) - r["t_start"], 3)          # plug-in process start, settings, model lookup
        out["export_and_checks_s"] = round(ts(up) - out["upload_s"] - ts(fill), 3)  # crop+mask PNG, backend health, node info
    if q and done:
        out["insert_s"] = round(ts(done) - ts(q), 3)
        out["exit_s"] = round(r["t_end"] - ts(done), 3)
    if ready:
        out["backend_ready_at"] = ts(ready)
        m = re.search(r"after (\d+) s", ready); out["backend_wait_s"] = int(m.group(1))
    out["t_start"], out["t_end"] = r["t_start"], r["t_end"]
    return out

if __name__ == "__main__":
    src = Path(sys.argv[1]); rows = []
    for l in open(src / "perf-results.jsonl"):
        r = json.loads(l)
        if r.get("event") == "fill": rows.append(parse(r))
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with open(src / "phases.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    json.dump(rows, open(src / "phases.json", "w"), indent=1)
    for r in rows:
        print(r["id"], r["wall_s"], r.get("working"), r.get("startup_s"), r.get("export_and_checks_s"), r.get("upload_s"), r.get("queue_to_first_step_s"), r.get("sampling_s"), r.get("download_s"), r.get("insert_s"), r.get("exit_s"), r.get("image_png_bytes"))
