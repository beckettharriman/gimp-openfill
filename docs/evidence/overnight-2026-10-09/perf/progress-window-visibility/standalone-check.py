import ctypes, sys, os
sys.path.insert(0, r"C:\repos\gimp-stable-boy\gimp-stable-boy")
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from stable_boy.progress_window import ProgressWindow
u = ctypes.windll.user32
noact = os.environ.get("NOACT", "1") == "1"
if not noact:
    import stable_boy.progress_window as pw
    pw._NoActivate.before_show = lambda self: None
if os.environ.get("DIALOG_FIRST") == "1":
    d = Gtk.Dialog(title="first"); d.show_all(); GLib.timeout_add(300, lambda: (d.destroy(), Gtk.main_quit(), False)[-1]); Gtk.main()
w = ProgressWindow("Generative Fill", "Test", position=(1180, 130))
def check():
    found = []
    EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(ctypes.c_void_p(h), b, 256)
        if b.value == "Stable Boy - Generative Fill": found.append(h)
        return True
    u.EnumWindows(EP(cb), None)
    for h in found:
        st = u.GetWindowLongW(ctypes.c_void_p(h), -16); ex = u.GetWindowLongW(ctypes.c_void_p(h), -20)
        print("noact", noact, "hwnd", h, "visible", bool(u.IsWindowVisible(ctypes.c_void_p(h))), "style %08x ex %08x" % (st & 0xffffffff, ex & 0xffffffff), "gtk visible", w.get_visible(), "mapped", w.get_mapped())
    Gtk.main_quit(); return False
GLib.timeout_add(1500, check)
Gtk.main()
