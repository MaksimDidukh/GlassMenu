import win32gui
import win32con
import time

def set_window_transparency(hwnd, alpha):
    """
    Устанавливает прозрачность для окна по его дескриптору.
    hwnd: дескриптор окна
    alpha: уровень прозрачности (0 - полностью прозрачное, 255 - полностью непрозрачное)
    """
    try:
        # Проверяем, что окно видимо и не является системным
        if not win32gui.IsWindowVisible(hwnd):
            return

        # Получаем заголовок окна
        window_title = win32gui.GetWindowText(hwnd)
        if not window_title:  # Пропускаем окна без заголовка
            return

        # Проверяем, есть ли у окна стандартные элементы управления (например, кнопка закрытия)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        has_sys_menu = style & win32con.WS_SYSMENU  # Проверяем наличие системного меню (с кнопкой закрытия)
        if not has_sys_menu:
            return

        # Устанавливаем атрибуты окна для поддержки прозрачности
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)

        # Устанавливаем прозрачность
        win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
        print(f"Прозрачность установлена для окна '{window_title}' на {alpha}")

    except Exception as e:
        print(f"Ошибка при установке прозрачности для окна '{window_title}': {e}")

def enum_windows_callback(hwnd, windows):
    """
    Callback-функция для перечисления всех окон.
    windows: список для хранения дескрипторов окон
    """
    windows.append(hwnd)

def set_transparency_for_all_windows(alpha=200):
    """
    Устанавливает прозрачность для всех видимых окон с кнопкой закрытия.
    alpha: уровень прозрачности (0 - 255)
    """
    windows = []
    # Перечисляем все окна
    win32gui.EnumWindows(enum_windows_callback, windows)

    for hwnd in windows:
        set_window_transparency(hwnd, alpha)
        time.sleep(0.1)  # Небольшая пауза для предотвращения перегрузки

def main():
    # Устанавливаем прозрачность (например, 200)
    alpha_level = 200  # Измените это значение, если нужно (0-255)
    print(f"Установка прозрачности на {alpha_level} для всех окон...")
    set_transparency_for_all_windows(alpha_level)
    print("Готово!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Скрипт остановлен пользователем")