import json, sys, re
from pathlib import Path
d = Path(sys.argv[1])
ev = {e['event']: e['t'] for e in map(json.loads, open(d / 'demo-events.jsonl'))}
ping = [json.loads(l) for l in open(d / 'ping.jsonl')]
def stats(a, b):
    p = [x for x in ping if a <= x['t'] <= b]
    return {"polls": len(p), "timeouts_100ms": sum(not x['ok'] for x in p), "max_ms": max(x['ms'] for x in p), "polls_over_50ms": sum(x['ms'] > 50 for x in p)}
out = {"session": d.name, "warmup_fill_noninteractive": stats(ev['display'], ev['warmup_done']),
       "demo_fill_dialog_to_layer": stats(ev['dialog_call'], ev['demo_done']), "demo_wall_s_including_dialog": round(ev['demo_done'] - ev['dialog_call'], 2)}
json.dump(out, open(d / 'gui-stats.json', 'w'), indent=1); print(out)
