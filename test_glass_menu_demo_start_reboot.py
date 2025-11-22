import win32gui, win32con, win32api
import pystray
from PIL import Image, ImageDraw
from threading import Timer
import sys

# Глобальная прозрачность
current_alpha = 255
history = []

def set_window_alpha(hwnd, alpha):
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if not (style & win32con.WS_EX_LAYERED):
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
    win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)

def apply_transparency(alpha):
    global current_alpha
    if alpha == current_alpha:
        return
    current_alpha = alpha
    history.append(alpha)

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            set_window_alpha(hwnd, alpha)
        return True

    win32gui.EnumWindows(enum_callback, None)

# Постоянное применение к новым окнам
def watch_new_windows():
    apply_transparency(current_alpha)
    Timer(1.5, watch_new_windows).start()

def create_icon():
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, 56, 56], radius=16, fill=(0, 255, 255))
    draw.text((20, 22), "GL", fill="black", font_size=24)
    return img

def setup_menu(icon):
    icon.icon = create_icon()
    icon.title = "GlassMenu — Global Transparency"
    
    menu = pystray.Menu(
        pystray.MenuItem("20% — Очень прозрачно",  lambda: apply_transparency(51)),
        pystray.MenuItem("40% — Прозрачно",       lambda: apply_transparency(102)),
        pystray.MenuItem("60% — Полупрозрачно",  lambda: apply_transparency(153)),
        pystray.MenuItem("80% — Слабо",           lambda: apply_transparency(204)),
        pystray.MenuItem("100% — Непрозрачно",   lambda: apply_transparency(255)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("История", lambda: print("\n[GlassMenu] История:", history[-10:], "\n")),
        pystray.MenuItem("Выход", lambda: (icon.stop(), sys.exit(0)))
    )
    icon.menu = menu

if __name__ == "__main__":
    icon = pystray.Icon("GlassMenu")
    setup_menu(icon)
    
    # Первый запуск + слежка за новыми окнами
    apply_transparency(255)
    Timer(2.0, watch_new_windows).start()
    
    print("GlassMenu активен | Правый клик по иконке в трее")
    icon.run()
