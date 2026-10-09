import json, sys
from pathlib import Path
d = Path(sys.argv[1])
res = [json.loads(l) for l in open(d / "perf-results.jsonl")]
fills = [r for r in res if r["event"] == "fill"]
samples = [json.loads(l) for l in open(d / "samples.jsonl")]
meta = json.loads((d / "launch-meta.json").read_text()) if (d / "launch-meta.json").exists() else {}
rows = []
for i, r in enumerate(fills):
    after = [s for s in samples if s["t"] >= r["t_end"] + 0.3]
    s = after[0] if after else None
    rows.append({"n": i, "id": r["id"], "wall_s": r["wall_s"], "status": r["status"],
                 "gimp_console_mb": s and s["gimp_console_mb"], "children_mb": s and s["children_mb"],
                 "comfy_mb": s and s["comfy_mb"], "vram_mib": s and s["vram_mib"], "sample_t": s and s["t"]})
json.dump(rows, open(d / "soak.json", "w"), indent=1)
import csv
with open(d / "soak.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
soak = [r for r in rows if r["id"].startswith("soak")]
def slope(key):
    xs = list(range(1, len(soak) + 1)); ys = [r[key] for r in soak]
    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
for r in rows: print(r)
if soak:
    print({k: round(slope(k), 3) for k in ("wall_s", "gimp_console_mb", "comfy_mb", "vram_mib")})
print(meta)
