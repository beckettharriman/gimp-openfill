import json, sys
from statistics import mean
rows = json.load(open(sys.argv[1]))
tiers = [("sd15", "SD 1.5 Inpainting (fast)"), ("quality", "SDXL 1.0 Base + Fooocus (quality)"), ("juggernaut", "Juggernaut XL v9 + Fooocus (quality)"), ("mat", "MAT Places512 (removal)")]
def g(t, s): return [r for r in rows if r["id"].startswith(f"{t}-{s}-")]
print("| Model (tier) | 512 px | 1024 px | 2048 px | First call after switching to it (512 px) |")
print("|---|---|---|---|---|")
for t, name in tiers:
    cells = []
    for s in (512, 1024, 2048):
        rs = g(t, s); cells.append(" / ".join(f"{r['wall_s']:.1f}" for r in rs) + " s")
    sw = [r for r in rows if r["id"] == f"{t}-switch-512"]
    cells.append(f"{sw[0]['wall_s']:.1f} s" if sw else "n/a (first model of the session, see cold start)")
    print(f"| {name} | " + " | ".join(cells) + " |")
print()
print("| Model | Selection | Context crop | Working size | Crop PNG | Plug-in start | Export + checks | Upload | Queue to first step | Sampling | Download | Insert | Total |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for t, name in tiers:
    for s in (512, 1024, 2048):
        rs = g(t, s)
        m = lambda k: mean(r[k] for r in rs)
        print(f"| {name.split(' (')[0]} | {s} | {rs[0]['context']} | {rs[0]['working']} | {rs[0]['image_png_bytes']/2**20:.1f} MB | {m('startup_s'):.2f} | {m('export_and_checks_s'):.2f} | {m('upload_s'):.2f} | {m('queue_to_first_step_s'):.2f} | {m('sampling_s'):.2f} | {m('download_s'):.2f} | {m('insert_s'):.2f} | {m('wall_s'):.2f} |")
