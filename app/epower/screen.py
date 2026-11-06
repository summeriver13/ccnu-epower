"""Screen pixels of the taskbar, used to keep the band clear of icons."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import List, Optional, Tuple

Rect = Tuple[int, int, int, int]

CONTENT_DELTA = 45
CONTENT_MIN_PIXELS = 2
BYTES_PER_PIXEL = 4
CAPTURE_COPY = 0x00CC0020
DIB_RGB_COLORS = 0
RED_WEIGHT = 299
GREEN_WEIGHT = 587
BLUE_WEIGHT = 114

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class _Header(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _Quad(ctypes.Structure):
    _fields_ = [
        ("blue", ctypes.c_byte),
        ("green", ctypes.c_byte),
        ("red", ctypes.c_byte),
        ("reserved", ctypes.c_byte),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("header", _Header), ("colors", _Quad * 1)]


gdi32.CreateDCW.restype = wintypes.HDC
gdi32.CreateDCW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_void_p,
]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.UINT,
]


def content_left(bounds: Rect) -> Optional[int]:
    """Return the leftmost x inside bounds that holds high-contrast pixels."""
    captured = _capture(bounds)
    if captured is None:
        return None
    width, height, data = captured
    levels = _luminance(data, width, height)
    middle = _median(levels)
    for column in range(width):
        lit = sum(1 for row in levels if abs(row[column] - middle) > CONTENT_DELTA)
        if lit >= CONTENT_MIN_PIXELS:
            return bounds[0] + column
    return None


def _capture(bounds: Rect) -> Optional[Tuple[int, int, bytes]]:
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return None
    screen = gdi32.CreateDCW("DISPLAY", None, None, None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    try:
        gdi32.SelectObject(memory, bitmap)
        gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, CAPTURE_COPY)
        return width, height, _bits(memory, bitmap, width, height)
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        gdi32.DeleteDC(screen)


def _bits(memory: int, bitmap: int, width: int, height: int) -> bytes:
    info = _BitmapInfo()
    info.header.biSize = ctypes.sizeof(_Header)
    info.header.biWidth = width
    info.header.biHeight = -height
    info.header.biPlanes = 1
    info.header.biBitCount = BYTES_PER_PIXEL * 8
    buffer = ctypes.create_string_buffer(width * height * BYTES_PER_PIXEL)
    gdi32.GetDIBits(
        memory, bitmap, 0, height, buffer, ctypes.byref(info), DIB_RGB_COLORS
    )
    return buffer.raw


def _luminance(data: bytes, width: int, height: int) -> List[List[int]]:
    step = BYTES_PER_PIXEL
    levels = []
    for line in range(height):
        start = line * width * step
        row = data[start : start + width * step]
        levels.append(
            [
                (
                    row[index + 2] * RED_WEIGHT
                    + row[index + 1] * GREEN_WEIGHT
                    + row[index] * BLUE_WEIGHT
                )
                // 1000
                for index in range(0, len(row), step)
            ]
        )
    return levels


def _median(levels: List[List[int]]) -> int:
    values = sorted(value for row in levels for value in row)
    return values[len(values) // 2]
