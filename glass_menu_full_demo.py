import win32gui
import win32con
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
from queue import Queue

class GlassMenuLite:
    """Lightweight window transparency manager with GUI and tray"""

    def __init__(self):
        self.windows = {}  # Stores hwnd and window titles
        self.settings_file = "glass_settings.json"
        self.settings = self.load_settings()
        self.icon = None
        self.running = True
        self.monitoring_thread = None
        self.window_queue = Queue()
        self.lock = threading.Lock()

        # Default settings
        self.default_alpha = self.settings.get('default_alpha', 200)
        self.excluded = self.settings.get('excluded', [
            "Program Manager", "Task Switching", "Windows Shell Experience Host"
        ])
        self.monitor_new = self.settings.get('monitor_new', True)

        # Configure logging
        log_level = logging.DEBUG if os.getenv('DEBUG_LOG') else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
        return {}

    def save_settings(self):
        """Save settings to JSON file"""
        with self.lock:
            self.settings = {
                'default_alpha': self.default_alpha,
                'excluded': self.excluded,
                'monitor_new': self.monitor_new
            }
            try:
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"Error saving settings: {e}")

    def set_window_transparency(self, hwnd, alpha):
        """Set window transparency"""
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return False

            title = win32gui.GetWindowText(hwnd)
            if not title or title in self.excluded:
                return False

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            if not (style & win32con.WS_SYSMENU):
                return False

            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if not (ex_style & win32con.WS_EX_LAYERED):
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, int(alpha), win32con.LWA_ALPHA)

            self.logger.debug(f"Transparency set for window '{title[:30]}' to {alpha}")
            return True
        except Exception as e:
            self.logger.debug(f"Error setting transparency for window {hwnd}: {e}")
            return False

    def reset_transparency(self, hwnd):
        """Reset window transparency to 255 (opaque)"""
        try:
            if self.set_window_transparency(hwnd, 255):
                self.logger.debug(f"Transparency reset for window {hwnd}")
                return True
        except Exception as e:
            self.logger.debug(f"Error resetting transparency for window {hwnd}: {e}")
        return False

    def apply_to_all_windows(self, alpha=None):
        """Apply transparency to all visible windows with system menu"""
        try:
            alpha = alpha or self.default_alpha
            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and title not in self.excluded:
                        self.set_window_transparency(hwnd, alpha)
                        with self.lock:
                            self.windows[hwnd] = title
                return True

            win32gui.EnumWindows(callback, None)
            self.logger.info(f"Transparency applied to all windows (level: {alpha})")
        except Exception as e:
            self.logger.error(f"Error applying transparency to all windows: {e}")

    def monitor_windows(self):
        """Monitor new windows using a queue"""
        known_windows = set()

        try:
            def init_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    known_windows.add(hwnd)
                return True

            win32gui.EnumWindows(init_callback, None)
            self.apply_to_all_windows()

            while self.running and self.monitor_new:
                try:
                    current_windows = set()

                    def check_callback(hwnd, _):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if title and hwnd not in current_windows:
                                current_windows.add(hwnd)
                                if hwnd not in known_windows and title not in self.excluded:
                                    self.window_queue.put((hwnd, title))
                        return True

                    win32gui.EnumWindows(check_callback, None)
                    known_windows = current_windows

                    while not self.window_queue.empty():
                        hwnd, title = self.window_queue.get()
                        if win32gui.IsWindow(hwnd):
                            self.set_window_transparency(hwnd, self.default_alpha)
                            with self.lock:
                                self.windows[hwnd] = title
                        self.window_queue.task_done()

                    time.sleep(0.5)
                except Exception as e:
                    self.logger.debug(f"Error monitoring windows: {e}")
                    time.sleep(1)
        except Exception as e:
            self.logger.error(f"Critical error in window monitoring: {e}")

    def update_windows_list(self):
        """Update list of visible windows"""
        try:
            new_windows = {}
            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and title not in self.excluded:
                        new_windows[hwnd] = title
                return True

            win32gui.EnumWindows(callback, None)
            with self.lock:
                self.windows = new_windows
            self.update_tray_menu()
        except Exception as e:
            self.logger.error(f"Error updating window list: {e}")

    def show_settings_dialog(self):
        """Dialog for global settings"""
        try:
            root = tk.Tk()
            try:
                root.title("Transparency Settings")
                root.geometry("400x350")
                root.resizable(False, False)
                root.attributes("-topmost", True)

                root.update_idletasks()
                x = (root.winfo_screenwidth() - root.winfo_width()) // 2
                y = (root.winfo_screenheight() - root.winfo_height()) // 2
                root.geometry(f"+{x}+{y}")

                tk.Label(root, text="Default Transparency:", font=("Segoe UI", 10)).pack(pady=10)
                value_label = tk.Label(root, text=f"{self.default_alpha}")
                value_label.pack()

                def on_change(val):
                    try:
                        if root.winfo_exists():
                            self.default_alpha = int(float(val))
                            value_label.config(text=f"{self.default_alpha}")
                            self.logger.debug(f"Default transparency changed to {self.default_alpha}")
                    except Exception as e:
                        self.logger.error(f"Error in transparency slider: {e}")

                slider = ttk.Scale(root, from_=50, to=255, orient="horizontal",
                                  command=on_change, length=300)
                slider.set(self.default_alpha)
                slider.pack(pady=10)

                monitor_var = tk.BooleanVar(value=self.monitor_new)
                tk.Checkbutton(root, text="Monitor new windows",
                              variable=monitor_var, font=("Segoe UI", 9)).pack(pady=5)

                exclude_label = tk.Label(root, text="Excluded windows (one per line):")
                exclude_label.pack(pady=5)
                exclude_text = tk.Text(root, height=5, width=40)
                exclude_text.insert(tk.END, "\n".join(self.excluded))
                exclude_text.pack(pady=5)

                def apply_action():
                    try:
                        if root.winfo_exists():
                            self.apply_to_all_windows()
                            self.logger.debug("Apply to all windows button clicked")
                    except Exception as e:
                        self.logger.error(f"Error in Apply button: {e}")
                        messagebox.showerror("Error", f"Failed to apply transparency: {str(e)}")

                def reset_action():
                    try:
                        if root.winfo_exists():
                            with self.lock:
                                for hwnd in list(self.windows.keys()):
                                    self.reset_transparency(hwnd)
                            self.logger.debug("Reset all windows button clicked")
                    except Exception as e:
                        self.logger.error(f"Error in Reset button: {e}")
                        messagebox.showerror("Error", f"Failed to reset transparency: {str(e)}")

                def save_action():
                    try:
                        if root.winfo_exists():
                            self.monitor_new = monitor_var.get()
                            exclude_input = exclude_text.get("1.0", tk.END).strip().split("\n")
                            self.excluded = [x.strip() for x in exclude_input if x.strip()]
                            self.save_settings()
                            if self.monitor_new and (not self.monitoring_thread or not self.monitoring_thread.is_alive()):
                                self.monitoring_thread = threading.Thread(target=self.monitor_windows, daemon=True)
                                self.monitoring_thread.start()
                            self.logger.debug("Save and Close button clicked")
                            root.destroy()
                    except Exception as e:
                        self.logger.error(f"Error in Save button: {e}")
                        messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

                frame = tk.Frame(root)
                frame.pack(pady=10)
                tk.Button(frame, text="Apply to All", command=apply_action, width=15).grid(row=0, column=0, padx=5)
                tk.Button(frame, text="Reset All", command=reset_action, width=15).grid(row=0, column=1, padx=5)
                tk.Button(root, text="Save and Close", command=save_action, width=20).pack(pady=10)

                root.mainloop()
            except Exception as e:
                self.logger.error(f"Error in settings dialog UI: {e}")
                if root.winfo_exists():
                    root.destroy()
        except Exception as e:
            self.logger.error(f"Error opening settings dialog: {e}")
            messagebox.showerror("Error", f"Failed to open settings: {str(e)}")

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle([8, 8, 56, 56], fill=(70, 130, 180, 160), outline=(30, 90, 140), width=2)
            draw.rectangle([8, 8, 56, 20], fill=(30, 90, 140))
            draw.rectangle([16, 28, 48, 48], fill=(255, 255, 255, 80))

            self.icon = pystray.Icon("GlassMenuLite", img, "Glass Menu Lite - Transparency Manager")
            self.update_tray_menu()
            return self.icon
        except Exception as e:
            self.logger.error(f"Error creating tray icon: {e}")
            return None

    def update_tray_menu(self):
        """Update system tray menu"""
        if not self.icon:
            return

        try:
            menu_items = [
                pystray.MenuItem(
                    f"{'🟢' if self.monitor_new else '🔴'} Monitor new: {'ON' if self.monitor_new else 'OFF'}",
                    self.show_settings_dialog
                ),
                pystray.MenuItem(f"📊 Default level: {self.default_alpha}",
                               self.show_settings_dialog),
                pystray.MenuItem("─" * 35, None, enabled=False),
                pystray.MenuItem("⚙️ Settings", self.show_settings_dialog),
                pystray.MenuItem("🎨 Apply to all", self.apply_to_all_windows),
                pystray.MenuItem("🔄 Reset all", lambda: [self.reset_transparency(h) for h in list(self.windows.keys())]),
                pystray.MenuItem("─" * 35, None, enabled=False),
                pystray.MenuItem("❌ Exit", self.quit)
            ]

            self.icon.menu = pystray.Menu(*menu_items)
            self.logger.debug("Tray menu updated successfully")
        except Exception as e:
            self.logger.error(f"Error updating tray menu: {e}")

    def quit(self):
        """Terminate the application"""
        self.running = False
        self.save_settings()
        if self.icon:
            try:
                self.icon.stop()
            except Exception as e:
                self.logger.error(f"Error stopping tray icon: {e}")
        self.logger.info("Application terminated")
        sys.exit(0)

    def run(self):
        """Run the application"""
        self.logger.info("=" * 50)
        self.logger.info("🚀 Glass Menu Lite - Started")
        self.logger.info(f"📊 Default transparency: {self.default_alpha}")
        self.logger.info(f"🔄 Monitor new: {'ON' if self.monitor_new else 'OFF'}")
        self.logger.info("=" * 50)

        if self.monitor_new:
            self.monitoring_thread = threading.Thread(target=self.monitor_windows, daemon=True)
            self.monitoring_thread.start()

        try:
            self.create_tray_icon()
            if self.icon:
                self.icon.run()
            else:
                self.logger.error("Failed to create tray icon")
                input("Press Enter to exit...")
        except Exception as e:
            self.logger.error(f"Critical error: {e}")
            input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        app = GlassMenuLite()
        app.run()
    except Exception as e:
        logging.error(f"Critical error on startup: {e}")
        input("Press Enter to exit...")
