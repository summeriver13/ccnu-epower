"""System notification for a low balance, sent through the tray balloon API."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Optional

from .win32 import WNDCLASSW, WNDPROC, kernel32, user32

shell32 = ctypes.WinDLL("shell32", use_last_error=True)

CLASS_NAME = "EpowerNotify"
TITLE = "电费余额不足"
CALLBACK_MESSAGE = 0x0400 + 1
ICON_ID = 1
ICON_INFORMATION = 32516
BALLOON_TIMEOUT_MS = 10_000
NIM_ADD = 0
NIM_MODIFY = 1
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_INFO = 0x10
NIS_HIDDEN = 0x1
NIIF_WARNING = 0x2


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


user32.LoadIconW.restype = wintypes.HICON
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]


class _Notifier:
    """Hidden tray icon that owns the notification channel."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hwnd: Optional[int] = None
        self._proc = WNDPROC(self._wndproc)

    def send(self, title: str, message: str) -> bool:
        """Show a notification. Returns False when Windows refuses it."""
        with self._lock:
            if not self._ensure():
                return False
            data = self._data()
            data.uFlags = NIF_INFO
            data.szInfo = message
            data.szInfoTitle = title
            data.dwInfoFlags = NIIF_WARNING
            data.uTimeout = BALLOON_TIMEOUT_MS
            return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data)))

    def _ensure(self) -> bool:
        if self._hwnd:
            return True
        if not self._register():
            return False
        instance = kernel32.GetModuleHandleW(None)
        self._hwnd = user32.CreateWindowExW(
            0, CLASS_NAME, "", 0, 0, 0, 0, 0, None, None, instance, None
        )
        if not self._hwnd:
            return False
        data = self._data()
        data.uFlags = NIF_MESSAGE | NIF_ICON
        data.uCallbackMessage = CALLBACK_MESSAGE
        data.hIcon = user32.LoadIconW(None, ICON_INFORMATION)
        data.dwState = NIS_HIDDEN
        data.dwStateMask = NIS_HIDDEN
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None
            return False
        threading.Thread(target=self._pump, daemon=True).start()
        return True

    def _register(self) -> bool:
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = CLASS_NAME
        return bool(user32.RegisterClassW(ctypes.byref(wc)))

    def _data(self) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = ICON_ID
        return data

    def _pump(self) -> None:
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    def _wndproc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == CALLBACK_MESSAGE:
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_notifier: Optional[_Notifier] = None


def send_low_balance(value: float) -> bool:
    """Notify that the balance dropped below the alert threshold."""
    global _notifier
    if _notifier is None:
        _notifier = _Notifier()
    message = f"余额剩 {value:.2f} 元，请及时充值。"
    return _notifier.send(TITLE, message)
