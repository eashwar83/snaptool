"""Native Windows global hotkey registration."""

import ctypes
import sys
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


VK_BY_NAME = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "prtscr": 0x2C,
    "prntscrn": 0x2C,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
}


MODIFIER_BY_NAME = {
    "alt": MOD_ALT,
    "control": MOD_CONTROL,
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
    "meta": MOD_WIN,
    "cmd": MOD_WIN,
}


def _normalize_key_name(value):
    return value.lower().replace(" ", "").replace("_", "").replace("-", "")


def parse_hotkey(combo):
    """Convert a user-facing hotkey string into RegisterHotKey modifiers and VK."""
    modifiers = 0
    key = None

    parts = [part.strip() for part in combo.split("+") if part.strip()]
    if not parts:
        raise ValueError("empty hotkey")

    for part in parts:
        name = _normalize_key_name(part)
        modifier = MODIFIER_BY_NAME.get(name)
        if modifier:
            modifiers |= modifier
            continue

        if key is not None:
            raise ValueError("hotkey must contain exactly one non-modifier key")

        if len(name) == 1 and ("a" <= name <= "z" or "0" <= name <= "9"):
            key = ord(name.upper())
        elif name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
            key = 0x70 + int(name[1:]) - 1
        else:
            key = VK_BY_NAME.get(name)

        if key is None:
            raise ValueError(f"unsupported key '{part}'")

    if key is None:
        raise ValueError("hotkey must contain a non-modifier key")

    return modifiers | MOD_NOREPEAT, key


class NativeHotkeyManager(QAbstractNativeEventFilter):
    """Register global hotkeys with the Windows shell and route WM_HOTKEY to Qt."""

    def __init__(self):
        super().__init__()
        self._callbacks = {}
        self._registered_ids = set()
        self._installed = False
        self._next_id = 1
        self._user32 = None

        if sys.platform == "win32":
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._user32.RegisterHotKey.argtypes = (
                wintypes.HWND,
                ctypes.c_int,
                wintypes.UINT,
                wintypes.UINT,
            )
            self._user32.RegisterHotKey.restype = wintypes.BOOL
            self._user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
            self._user32.UnregisterHotKey.restype = wintypes.BOOL

            app = QCoreApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self)
                self._installed = True

    @property
    def available(self):
        return self._user32 is not None

    def register(self, combo, callback):
        if not self.available:
            return False

        modifiers, vk = parse_hotkey(combo)
        hotkey_id = self._next_id
        self._next_id += 1

        if not self._user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
            error = ctypes.get_last_error()
            raise OSError(error, f"RegisterHotKey failed for '{combo}'")

        self._callbacks[hotkey_id] = callback
        self._registered_ids.add(hotkey_id)
        return True

    def unregister_all(self):
        if not self.available:
            return

        for hotkey_id in list(self._registered_ids):
            self._user32.UnregisterHotKey(None, hotkey_id)
        self._registered_ids.clear()
        self._callbacks.clear()
        self._next_id = 1

    def close(self):
        self.unregister_all()
        if self._installed:
            app = QCoreApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self)
            self._installed = False

    def nativeEventFilter(self, event_type, message):
        # Registered thread hotkeys arrive as windows_dispatcher_MSG.
        if isinstance(event_type, str):
            event_name = event_type
        else:
            event_name = bytes(event_type).decode("ascii", errors="ignore")

        if event_name not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0

        msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
        if msg.message != WM_HOTKEY:
            return False, 0

        callback = self._callbacks.get(int(msg.wParam))
        if callback is None:
            return False, 0

        QTimer.singleShot(0, callback)
        return True, 0
