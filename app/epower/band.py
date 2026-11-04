"""Taskbar band window built on the win32 bindings."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable, Optional

from .win32 import (
    BAND_GAP_AT_96DPI,
    BAND_HEIGHT_AT_96DPI,
    BAND_PADDING_AT_96DPI,
    DT_CENTER,
    DT_SINGLELINE,
    DT_VCENTER,
    FONT_POINTS,
    PAINTSTRUCT,
    SIZE,
    SWP_SHOWWINDOW,
    TRANSPARENT,
    WM_DESTROY,
    WM_ERASEBKGND,
    WM_LBUTTONUP,
    WM_PAINT,
    WM_PRINTCLIENT,
    WM_RBUTTONUP,
    WNDCLASSW,
    WNDPROC,
    WS_CHILD,
    WS_CLIPSIBLINGS,
    WS_VISIBLE,
    Color,
    _colorref,
    _window_rect,
    gdi32,
    kernel32,
    user32,
)


class Band:
    """One line of text drawn as a child window of the taskbar."""

    def __init__(
        self,
        text: str,
        color: Color,
        background: Color,
        on_left_click: Optional[Callable[[], None]] = None,
        on_right_click: Optional[Callable[[], None]] = None,
    ) -> None:
        self.text = text
        self.color = color
        self.background = background
        self.on_left_click = on_left_click
        self.on_right_click = on_right_click
        self.hwnd: Optional[int] = None
        self.shell: Optional[int] = None
        self._registered = False
        self._font: Optional[int] = None
        self._dpi = 96
        self._size = (0, 0)
        self._proc = WNDPROC(self._wndproc)

    def create(self) -> bool:
        """Create the window and attach it to the taskbar."""
        self.shell = user32.FindWindowW("Shell_TrayWnd", None)
        tray = user32.FindWindowExW(self.shell, None, "TrayNotifyWnd", None)
        if not self.shell or not tray:
            return False
        self._dpi = user32.GetDpiForWindow(self.shell) or 96
        self._font = gdi32.CreateFontW(
            -round(FONT_POINTS * self._dpi / 72),
            0,
            0,
            0,
            400,
            0,
            0,
            0,
            1,
            0,
            0,
            5,
            0,
            "Segoe UI",
        )
        self._register()
        if not self._place():
            return False
        return bool(user32.IsWindow(self.hwnd))

    def _register(self) -> None:
        if self._registered:
            return
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "EpowerTaskbarBand"
        user32.RegisterClassW(ctypes.byref(wc))
        self._registered = True

    def _scaled(self, value: int) -> int:
        return round(value * self._dpi / 96)

    def _width(self, text: str) -> int:
        dc = gdi32.CreateCompatibleDC(None)
        old = gdi32.SelectObject(dc, self._font)
        size = SIZE()
        gdi32.GetTextExtentPoint32W(dc, text, len(text), ctypes.byref(size))
        gdi32.SelectObject(dc, old)
        gdi32.DeleteDC(dc)
        return size.cx + 2 * self._scaled(BAND_PADDING_AT_96DPI)

    def _place(self) -> bool:
        shell = user32.FindWindowW("Shell_TrayWnd", None)
        tray = user32.FindWindowExW(shell, None, "TrayNotifyWnd", None)
        if not shell or not tray:
            return False
        self.shell = shell
        left, top, right, bottom = _window_rect(shell)
        width, height = self._width(self.text), self._scaled(BAND_HEIGHT_AT_96DPI)
        x = _window_rect(tray)[0] - self._scaled(BAND_GAP_AT_96DPI) - width
        y = top + (bottom - top - height) // 2
        self._size = (width, height)
        if not self.hwnd:
            self.hwnd = user32.CreateWindowExW(
                0,
                "EpowerTaskbarBand",
                "",
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                x - left,
                y - top,
                width,
                height,
                shell,
                None,
                kernel32.GetModuleHandleW(None),
                None,
            )
            if not self.hwnd:
                return False
        user32.SetWindowPos(
            self.hwnd, 0, x - left, y - top, width, height, SWP_SHOWWINDOW
        )
        return True

    def update(self, text: str, color: Color) -> None:
        """Replace the text and colour, then repaint."""
        if text == self.text and color == self.color:
            return
        self.text = text
        self.color = color
        if self.hwnd:
            self._place()
            user32.InvalidateRect(self.hwnd, None, True)

    def close(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def run(self) -> None:
        """Pump messages until the window is destroyed."""
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    def _paint(self, hwnd: int) -> None:
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        self._draw(hdc)
        user32.EndPaint(hwnd, ctypes.byref(paint))

    def _draw(self, hdc: int) -> None:
        brush = gdi32.CreateSolidBrush(_colorref(self.background))
        area = wintypes.RECT(0, 0, self._size[0], self._size[1])
        user32.FillRect(hdc, ctypes.byref(area), brush)
        gdi32.DeleteObject(brush)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, _colorref(self.color))
        old = gdi32.SelectObject(hdc, self._font)
        box = wintypes.RECT(0, 0, self._size[0], self._size[1])
        user32.DrawTextW(
            hdc,
            self.text,
            -1,
            ctypes.byref(box),
            DT_CENTER | DT_VCENTER | DT_SINGLELINE,
        )
        gdi32.SelectObject(hdc, old)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            self._paint(hwnd)
            return 0
        if msg == WM_PRINTCLIENT:
            self._draw(wintypes.HDC(wparam))
            return 0
        if msg == WM_LBUTTONUP and self.on_left_click:
            self.on_left_click()
            return 0
        if msg == WM_RBUTTONUP and self.on_right_click:
            self.on_right_click()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
