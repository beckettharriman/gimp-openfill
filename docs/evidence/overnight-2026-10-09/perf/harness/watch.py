import ctypes, ctypes.wintypes as wt, json, sys, time
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
EP = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
out = open(sys.argv[1], "a"); end = time.time() + float(sys.argv[2])
while time.time() < end:
    rows = []
    def cb(h, _):
        n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
        if "Stable Boy" in b.value or "Generative" in b.value:
            pid = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid)); r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            rows.append([h, pid.value, b.value, bool(u.IsWindowVisible(h)), [r.left, r.top, r.right, r.bottom], "%08x" % (u.GetWindowLongW(h, -16) & 0xffffffff), "%08x" % (u.GetWindowLongW(h, -20) & 0xffffffff), u.GetWindow(h, 4)])
        return True
    u.EnumWindows(EP(cb), 0)
    out.write(json.dumps({"t": time.time(), "w": rows}) + "\n"); out.flush(); time.sleep(0.5)
