import json, os, subprocess, sys, time
from pathlib import Path
PROFILE = Path(r"C:\AI\overnight-scratch\gimp-profile-test"); CONFIG = PROFILE / "stable-boy" / "config.json"
GIMP = r"C:\Users\becke\AppData\Local\Programs\GIMP 3\bin\gimp-3.2.exe"
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
warm = sys.argv[2] if len(sys.argv) > 2 else "1"
backup = CONFIG.read_text(encoding="utf-8")
cfg = json.loads(backup); cfg.update(steps=20, progress_window=True, progress_window_x=int(os.environ.get("PW_X", "-1")), progress_window_y=int(os.environ.get("PW_Y", "-1")))
CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
hooks = out / "ui-hooks.json"; hooks.write_text("{}")
env = dict(os.environ, GIMP3_DIRECTORY=str(PROFILE), SB_TEST_UI_FILE=str(hooks), SB_DEMO_OUT=str(out), SB_PERF_STALL="1", SB_DEMO_WARMUP=warm)
cmd = [GIMP, "--new-instance", "--no-splash", "--batch-interpreter", "python-fu-eval", "-b", r"exec(open(r'C:\AI\overnight-scratch\perf\gui_demo.py').read())"]
(out / "batch-command.txt").write_text(" ".join(cmd) + "\n(env GIMP3_DIRECTORY=%s SB_TEST_UI_FILE=%s SB_PERF_STALL=1; config steps=20 progress_window=true)\n" % (PROFILE, hooks))
try:
    t0 = time.time()
    p = subprocess.Popen(cmd, env=env, stdout=open(out / "gimp-stdout.txt", "w"), stderr=open(out / "gimp-stderr.txt", "w"))
    cap = subprocess.Popen([sys.executable, r"C:\AI\overnight-scratch\perf\capture.py", str(p.pid), str(out)])
    try:
        p.wait(900)
    except subprocess.TimeoutExpired:
        p.kill()
    cap.wait(30)
finally:
    CONFIG.write_text(backup, encoding="utf-8")
print("done", round(time.time() - t0, 1))
