"""Outside the GUI GIMP: position its window, poll it with SendMessageTimeout(WM_NULL, 100 ms) every 50 ms,
grab the window region at 2 fps, and press Enter in the Generative Fill dialog once the prompt is typed."""
import ctypes, ctypes.wintypes as wt, json, os, sys, threading, time
from pathlib import Path
import psutil
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
gimp_pid = int(sys.argv[1]); out = Path(sys.argv[2]); frames = out / "frames"; frames.mkdir(parents=True, exist_ok=True)
X, Y, W, H = 0, 0, 1920, 1200
stop = threading.Event()
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

def windows(pids, prefix=None):
    found = []
    def cb(h, _):
        if u.IsWindowVisible(h):
            pid = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            if pid.value in pids or (prefix and b.value.startswith(prefix)):
                found.append((h, pid.value, b.value))
        return True
    u.EnumWindows(EnumProc(cb), 0)
    return found

def tree_pids():
    try:
        p = psutil.Process(gimp_pid); return {gimp_pid} | {c.pid for c in p.children(recursive=True)}
    except psutil.Error:
        return set()

def log(name, **kw):
    with open(out / "capture-events.jsonl", "a") as fh: fh.write(json.dumps({"t": time.time(), "event": name, **kw}) + "\n")

main = None
while main is None and not stop.is_set():
    for h, pid, title in windows({gimp_pid}):
        if ("GIMP" in title or "GNU Image" in title) and not title.startswith("Welcome") and pid == gimp_pid: main = h; break
    if not psutil.pid_exists(gimp_pid): sys.exit(0)
    time.sleep(0.5)
log("main_window", hwnd=main)
u.ShowWindow(main, 1)  # SW_SHOWNORMAL (un-maximise)
u.SetWindowPos(main, 0, X, Y, W, H, 0x0040)
u.SetForegroundWindow(main)

def ping():
    res = ctypes.c_size_t()
    with open(out / "ping.jsonl", "a") as fh:
        while not stop.is_set():
            t0 = time.perf_counter()
            ok = u.SendMessageTimeoutW(main, 0, 0, 0, 0x0002, 100, ctypes.byref(res))  # WM_NULL, SMTO_ABORTIFHUNG
            dt = (time.perf_counter() - t0) * 1000
            fh.write(json.dumps({"t": time.time(), "ms": round(dt, 2), "ok": bool(ok)}) + "\n")
            time.sleep(max(0, 0.05 - dt / 1000))

gdi = ctypes.windll.gdi32
dwm = ctypes.windll.dwmapi
from PIL import Image

def ext_rect(h):
    r = wt.RECT()
    if dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def print_window(h):
    r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w <= 0 or hh <= 0: return None, None
    hdc = u.GetWindowDC(h); mdc = gdi.CreateCompatibleDC(hdc); bmp = gdi.CreateCompatibleBitmap(hdc, w, hh)
    gdi.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)
    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD), ("a", wt.LONG), ("b", wt.LONG), ("c", wt.DWORD), ("d", wt.DWORD)]
    bmi = BMI(); bmi.biSize = ctypes.sizeof(BMI); bmi.biWidth = w; bmi.biHeight = -hh; bmi.biPlanes = 1; bmi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    gdi.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bmi), 0)
    gdi.DeleteObject(bmp); gdi.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    img = Image.frombuffer("RGBA", (w, hh), buf, "raw", "BGRA", 0, 1).convert("RGB")
    ex = ext_rect(h)
    img = img.crop((ex[0] - r.left, ex[1] - r.top, ex[2] - r.left, ex[3] - r.top))
    return img, ex

_seen = set()
def log_once(hs):
    for h in hs:
        if h not in _seen:
            _seen.add(h); log("window", hwnd=h, rect=ext_rect(h))

def compose():
    base, mr = print_window(main)
    if base is None: return None
    pids = tree_pids()
    others = [h for h, pid, title in windows(pids, 'Stable Boy - ') if h != main]
    log_once(others)
    for h in reversed(others):  # EnumWindows is top first: paste bottom first
        im, ex = print_window(h)
        if im is None: continue
        if ex[2] <= mr[0] or ex[0] >= mr[2] or ex[3] <= mr[1] or ex[1] >= mr[3]: continue
        base.paste(im, (ex[0] - mr[0], ex[1] - mr[1]))
    return base

def grab():
    i = 0
    while not stop.is_set():
        t = time.time()
        try:
            im = compose()
            if im is not None: im.save(frames / f"f{i:05d}_{t:.2f}.png")
            if os.environ.get("SCREEN_BOX"):
                from PIL import ImageGrab
                box = tuple(int(v) for v in os.environ["SCREEN_BOX"].split(","))
                (out / "screen").mkdir(exist_ok=True)
                ImageGrab.grab(bbox=box, all_screens=True).save(out / "screen" / f"s{i:05d}_{t:.2f}.png")
        except Exception as e:
            log("grab_error", err=str(e))
        i += 1
        time.sleep(max(0, 0.5 - (time.time() - t)))

threading.Thread(target=ping, daemon=True).start()
threading.Thread(target=grab, daemon=True).start()
pressed = False; seen = None
while psutil.pid_exists(gimp_pid):
    for h, pid, title in windows({gimp_pid}):
        if title.startswith("Welcome to GIMP"):
            u.PostMessageW(h, 0x0010, 0, 0); log("welcome_closed")
    if not pressed:
        for h, pid, title in windows(tree_pids()):
            if title.startswith("Generative Fill") and pid != gimp_pid:
                if seen is None: seen = time.time(); log("dialog_seen", title=title, hwnd=h)
                if time.time() - seen > 4.0:
                    u.PostMessageW(h, 0x0100, 0x0D, 0x001C0001); u.PostMessageW(h, 0x0101, 0x0D, 0xC01C0001)
                    log("enter_posted", hwnd=h); pressed = True
                    time.sleep(2.5)
                    log("dialog_still_visible_after_enter", visible=bool(u.IsWindowVisible(h)))
                break
    time.sleep(0.2)
stop.set(); time.sleep(0.6); log("end")
