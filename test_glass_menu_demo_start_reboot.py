import win32gui
import win32con
import win32api
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import pystray
from PIL import Image, ImageDraw
import json
import os
import sys
import logging
import pythoncom
import shutil
from queue import Queue
from pathlib import Path

try:
    import winshell
except ImportError:
    os.system("pip install winshell")
    import winshell


class GlassMenuPro:
    """GlassMenuPro with auto-start and pin-on-top support"""

    def __init__(self):
        self.settings_file = "glass_settings.json"
        self.settings = self.load_settings()
        self.windows = {}
        self.pinned_windows = set(self.settings.get("pinned_windows", []))
        self.default_alpha = self.settings.get("default_alpha", 200)
        self.monitor_new = self.settings.get("monitor_new", True)
        self.running = True
        self.icon = None
        self.lock = threading.Lock()
        self.monitor_thread = None

        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
        self.logger = logging.getLogger("GlassMenuPro")

        self.ensure_autostart()

    # ========================= AUTOSTART =========================
    def ensure_autostart(self):
        """Add shortcut to Windows startup"""
        try:
            startup_path = Path(os.getenv("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            script_path = Path(sys.argv[0]).resolve()
            shortcut_path = startup_path / "GlassMenuPro.lnk"

            if not shortcut_path.exists():
                import winshell
                with winshell.shortcut(str(shortcut_path)) as link:
                    link.path = sys.executable
                    link.arguments = f'"{script_path}"'
                    link.description = "GlassMenuPro Autostart"
                self.logger.info(f"Autostart added: {shortcut_path}")
        except Exception as e:
            self.logger.error(f"Autostart setup failed: {e}")

    # ========================= SETTINGS =========================
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump({
                    "default_alpha": self.default_alpha,
                    "monitor_new": self.monitor_new,
                    "pinned_windows": list(self.pinned_windows)
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")

    # ========================= WINDOW OPS =========================
    def set_transparency(self, hwnd, alpha):
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if not (ex_style & win32con.WS_EX_LAYERED):
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
        except Exception as e:
            self.logger.debug(f"Transparency error: {e}")

    def toggle_pin(self, hwnd):
        """Toggle window always-on-top"""
        try:
            if hwnd in self.pinned_windows:
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                self.pinned_windows.remove(hwnd)
            else:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                self.pinned_windows.add(hwnd)
            self.save_settings()
            self.update_tray_menu()
        except Exception as e:
            self.logger.error(f"Error toggling pin: {e}")

    def apply_to_all(self):
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                self.set_transparency(hwnd, self.default_alpha)
                if hwnd in self.pinned_windows:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            return True
        win32gui.EnumWindows(callback, None)

    # ========================= TRAY =========================
    def create_icon(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([8, 8, 56, 56], fill=(100, 150, 255, 160), outline=(40, 60, 180), width=2)
        draw.rectangle([14, 14, 50, 50], fill=(255, 255, 255, 60))
        self.icon = pystray.Icon("GlassMenuPro", img, "GlassMenuPro")
        self.update_tray_menu()

    def update_tray_menu(self):
        if not self.icon:
            return
        try:
            def build_pin_menu():
                win_items = []
                for hwnd, title in self.enumerate_windows().items():
                    label = f"{'📌' if hwnd in self.pinned_windows else '⚪'} {title[:25]}"
                    win_items.append(pystray.MenuItem(label, lambda _, h=hwnd: self.toggle_pin(h)))
                return win_items or [pystray.MenuItem("Нет окон", None, enabled=False)]

            menu = pystray.Menu(
                pystray.MenuItem(f"🌫 Уровень: {self.default_alpha}", self.show_settings),
                pystray.MenuItem("📍 Закрепленные окна", pystray.Menu(*build_pin_menu())),
                pystray.MenuItem("🎨 Применить ко всем", self.apply_to_all),
                pystray.MenuItem("⚙️ Настройки", self.show_settings),
                pystray.MenuItem("❌ Выход", self.quit)
            )
            self.icon.menu = menu
        except Exception as e:
            self.logger.error(f"Menu update error: {e}")

    # ========================= ENUM + GUI =========================
    def enumerate_windows(self):
        result = {}
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    result[hwnd] = title
            return True
        win32gui.EnumWindows(callback, None)
        return result

    def show_settings(self):
        root = tk.Tk()
        root.title("Настройки GlassMenuPro")
        root.geometry("350x220")
        tk.Label(root, text="Прозрачность окон:", font=("Segoe UI", 10)).pack(pady=10)
        slider = ttk.Scale(root, from_=50, to=255, orient="horizontal", length=250)
        slider.set(self.default_alpha)
        slider.pack()
        tk.Label(root, text="Мониторинг новых окон").pack(pady=5)
        var = tk.BooleanVar(value=self.monitor_new)
        tk.Checkbutton(root, variable=var).pack()

        def save():
            self.default_alpha = int(slider.get())
            self.monitor_new = var.get()
            self.save_settings()
            root.destroy()

        tk.Button(root, text="Сохранить", command=save).pack(pady=10)
        root.mainloop()

    # ========================= LOOP =========================
    def run(self):
        self.create_icon()
        self.apply_to_all()
        if self.icon:
            self.icon.run()

    def quit(self):
        self.running = False
        self.save_settings()
        if self.icon:
            self.icon.stop()
        sys.exit(0)


if __name__ == "__main__":
    app = GlassMenuPro()
    app.run()
