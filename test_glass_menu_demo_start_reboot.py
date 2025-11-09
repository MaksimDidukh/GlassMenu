# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ФИНАЛЬНАЯ ВЕРСИЯ — GO! (всё в одном файле, без багов, красиво)
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
import win32gui, win32con, win32api
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw
import json, os, sys, logging
from pathlib import Path

try:
    import winshell
except ImportError:
    os.system("pip install winshell -q")
    import winshell

class GlassMenuPro:
    def __init__(self):
        self.settings_file = "glass_settings.json"
        self.settings = self.load_settings()
        self.pinned = set(self.settings.get("pinned", []))
        self.alpha = self.settings.get("alpha", 200)
        self.monitor = self.settings.get("monitor", True)
        self.icon = None
        self.ensure_autostart()

    def ensure_autostart(self):
        try:
            startup = Path(os.getenv("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            lnk = startup / "GlassMenuPro.lnk"
            if not lnk.exists():
                with winshell.shortcut(str(lnk)) as s:
                    s.path = sys.executable
                    s.arguments = f'"{Path(sys.argv[0]).resolve()}"'
                    s.description = "GlassMenuPro"
        except: pass

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return {}

    def save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump({"alpha": self.alpha, "monitor": self.monitor, "pinned": list(self.pinned)}, f, indent=2)
        except: pass

    def set_alpha(self, hwnd, a):
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd): return
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if not (style & win32con.WS_EX_LAYERED):
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, a, win32con.LWA_ALPHA)
        except: pass

    def toggle_pin(self, hwnd):
        if hwnd in self.pinned:
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            self.pinned.remove(hwnd)
        else:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            self.pinned.add(hwnd)
        self.save_settings()
        self.update_menu()

    def apply_all(self, a=None):
        a = a if a is not None else self.alpha
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                self.set_alpha(hwnd, a)
                if hwnd in self.pinned:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            return True
        win32gui.EnumWindows(cb, None)

    def enum_windows(self):
        wins = {}
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t: wins[hwnd] = t
            return True
        win32gui.EnumWindows(cb, None)
        return wins

    def create_icon(self):
        img = Image.new("RGBA", (64,64), (0,0,0,0))
        d = ImageDraw.Draw(img)
        d.rectangle([8,8,56,56], fill=(80,160,255,180), outline=(0,100,255), width=3)
        d.text((20,24), "G", fill=(255,255,255,220), font=None)
        self.icon = pystray.Icon("GlassMenuPro", img, "GlassMenuPro")
        self.update_menu()

    def update_menu(self):
        if not self.icon: return
        wins = self.enum_windows()
        pin_items = []
        for hwnd, title in wins.items():
            pin_items.append(pystray.MenuItem(
                f"{'📌' if hwnd in self.pinned else '⚪'} {title[:30]}",
                lambda _, h=hwnd: self.toggle_pin(h)
            ))
        if not pin_items:
            pin_items = [pystray.MenuItem("Нет окон", None, enabled=False)]

        menu = pystray.Menu(
            pystray.MenuItem(f"🌫 {self.alpha}", self.show_gui),
            pystray.MenuItem("📍 Закрепить", pystray.Menu(*pin_items)),
            pystray.MenuItem("🎨 Применить всем", self.apply_all),
            pystray.MenuItem("⚙ Настройки", self.show_gui),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Выход", self.quit)
        )
        self.icon.menu = menu

    def show_gui(self):
        win = tk.Tk()
        win.title("GlassMenuPro")
        win.geometry("400x260")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        tk.Label(win, text="Прозрачность", font=("Segoe UI", 12, "bold")).pack(pady=15)

        frame = tk.Frame(win)
        frame.pack(pady=10)

        slider = ttk.Scale(frame, from_=50, to=255, orient="horizontal", length=320)
        slider.set(self.alpha)
        slider.pack(side=tk.LEFT)

        val = tk.Label(frame, text=str(self.alpha), width=5, font=("Consolas", 11))
        val.pack(side=tk.LEFT, padx=10)

        def live(e=None):
            a = int(slider.get())
            val.config(text=str(a))
            self.alpha = a
            self.apply_all(a)
            self.update_menu()

        slider.config(command=live)

        tk.Label(win, text="Мониторить новые окна").pack(pady=(20,5))
        monitor_var = tk.BooleanVar(value=self.monitor)
        tk.Checkbutton(win, variable=monitor_var).pack()

        def save():
            self.monitor = monitor_var.get()
            self.save_settings()
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=20)
        tk.Button(btns, text="Сохранить", width=12, command=save).pack(side=tk.LEFT, padx=8)
        tk.Button(btns, text="Отмена", width=12, command=win.destroy).pack(side=tk.LEFT, padx=8)

        win.mainloop()

    def run(self):
        self.create_icon()
        self.apply_all()
        self.icon.run()

    def quit(self):
        self.save_settings()
        if self.icon: self.icon.stop()
        sys.exit(0)

if __name__ == "__main__":
    GlassMenuPro().run()
