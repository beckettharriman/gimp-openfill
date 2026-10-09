"""Launch gimp-console with tests/gimp_batch_perf.py and sample memory/VRAM every 0.5 s."""
import argparse, json, os, shutil, socket, subprocess, time
from pathlib import Path
import psutil

REPO = Path(r"C:\repos\gimp-stable-boy")
PROFILE = Path(r"C:\AI\overnight-scratch\gimp-profile-test")
GIMP = Path(r"C:\Users\becke\AppData\Local\Programs\GIMP 3\bin\gimp-console-3.2.exe")
DRIVER = REPO / "tests" / "gimp_batch_perf.py"
CONFIG = PROFILE / "stable-boy" / "config.json"
PROTECTED = 13040

def port_open():
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 8188)); return True
    except OSError:
        return False
    finally:
        s.close()

def vram():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None

def sample(root):
    gimp_ws = None; plugin_ws = 0
    try:
        gimp_ws = root.memory_info().rss
        for p in root.children(recursive=True):
            try:
                cmd = " ".join(p.cmdline() or [])
                if "ComfyUI" in cmd: continue
                plugin_ws += p.memory_info().rss
            except psutil.Error: pass
    except psutil.Error: pass
    comfy = 0
    for p in psutil.process_iter(["cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
            if "ComfyUI" in cmd and "main.py" in cmd: comfy += p.memory_info().rss
        except psutil.Error: pass
    mb = lambda b: round(b / 2**20, 1) if b is not None else None
    return {"t": time.time(), "gimp_console_mb": mb(gimp_ws), "children_mb": mb(plugin_ws), "comfy_mb": mb(comfy), "vram_mib": vram()}

ap = argparse.ArgumentParser(); ap.add_argument("--plan"); ap.add_argument("--out"); ap.add_argument("--steps", type=int, default=20)
ap.add_argument("--timeout", type=int, default=1800)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
backup = CONFIG.read_text(encoding="utf-8")
cfg = json.loads(backup); cfg["steps"] = a.steps; cfg["progress_window"] = False
CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
meta = {"port_8188_open_before": port_open(), "vram_before": vram(), "steps": a.steps}
env = dict(os.environ, GIMP3_DIRECTORY=str(PROFILE), SB_PERF_PLAN=a.plan, SB_PERF_OUT=str(out))
cmd = [str(GIMP), "--new-instance", "--no-splash", "--console-messages", "--batch-interpreter", "python-fu-eval",
       "-b", f"exec(open(r'{DRIVER}').read())"]
(out / "batch-command.txt").write_text(
    f"set GIMP3_DIRECTORY={PROFILE}\nset SB_PERF_PLAN={a.plan}\nset SB_PERF_OUT={out}\n"
    f"\"{GIMP}\" --new-instance --no-splash --console-messages --batch-interpreter python-fu-eval -b \"exec(open(r'{DRIVER}').read())\"\n"
    f"(launcher: python {__file__} --plan {a.plan} --out {out} --steps {a.steps}; config steps={a.steps}, progress_window=false)\n", encoding="utf-8")
try:
    meta["t_launch"] = time.time()
    so = open(out / "gimp-stdout.txt", "w"); se = open(out / "gimp-stderr.txt", "w")
    proc = subprocess.Popen(cmd, env=env, stdout=so, stderr=se)
    meta["gimp_pid"] = proc.pid
    root = psutil.Process(proc.pid)
    with open(out / "samples.jsonl", "a") as fh:
        while proc.poll() is None:
            fh.write(json.dumps(sample(root)) + "\n"); fh.flush()
            if time.time() - meta["t_launch"] > a.timeout:
                for p in root.children(recursive=True):
                    if p.pid != PROTECTED: p.kill()
                proc.kill(); meta["killed"] = True; break
            time.sleep(0.5)
    proc.wait(60)
    meta["t_exit"] = time.time()
    # after exit: how quickly ComfyUI goes away
    for i in range(60):
        if not port_open(): break
        time.sleep(1)
    meta["port_closed_after_exit_s"] = round(time.time() - meta["t_exit"], 1)
    time.sleep(3); meta["vram_after"] = vram()
finally:
    CONFIG.write_text(backup, encoding="utf-8")
(out / "launch-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(json.dumps(meta))
