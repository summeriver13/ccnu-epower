"""Windows tray icon that shows the dorm electricity balance."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

from .config import CliOptions, credentials_from_env, resolve_target
from .errors import CCNUEWError, ConfigError
from .widget import icon_color, icon_text, refresh_minutes, tray_title

ICON_SIZE = 32
ICON_RADIUS = 7
TOOLTIP_LIMIT = 127
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "ccnu-epower-tray"


def _font_for(text: str):
    from PIL import ImageFont

    for size in range(20, 7, -1):
        font = ImageFont.load_default(size=size)
        left, top, right, bottom = font.getbbox(text)
        if right - left <= ICON_SIZE - 4 and bottom - top <= ICON_SIZE - 4:
            return font
    return ImageFont.load_default(size=8)


def build_image(text: str, color: tuple[int, int, int]):
    """Draw a rounded badge with the balance text in white."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        [0, 0, ICON_SIZE - 1, ICON_SIZE - 1], radius=ICON_RADIUS, fill=color
    )
    font = _font_for(text)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    offset = (
        (ICON_SIZE - (right - left)) / 2 - left,
        (ICON_SIZE - (bottom - top)) / 2 - top,
    )
    draw.text(offset, text, font=font, fill=(255, 255, 255, 255))
    return image


def collect_once() -> dict[str, Any]:
    """Run one query and write the JSON report."""
    from .cli import query, write_report

    target = resolve_target(CliOptions())
    if target is None:
        raise ConfigError("缺少目标宿舍：请在 .env 设置 CCNU_METER_ID 或四个房间变量")
    report = query(credentials_from_env(), target)
    write_report(report)
    return report


class TrayApp:
    """Owns the icon, the cached report, and the refresh thread."""

    def __init__(self) -> None:
        self._report: Optional[dict[str, Any]] = None
        self._icon: Any = None
        self._wake = threading.Event()

    def run(self) -> None:
        import pystray

        self._icon = pystray.Icon(
            "ccnu-epower",
            icon=build_image("…", (107, 114, 128)),
            title="ccnu-epower：正在取数",
            menu=pystray.Menu(
                pystray.MenuItem("打开报告", self._open_report, default=True),
                pystray.MenuItem("立即刷新", self._refresh),
                pystray.MenuItem("退出", self._quit),
            ),
        )
        self._icon.run(setup=self._start)

    def _start(self, icon: Any) -> None:
        icon.visible = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while not self._wake.is_set():
            try:
                self._refresh()
            except Exception as exc:  # keep the icon alive and show the cause
                self._apply(None, f"ccnu-epower：{exc}")
            self._wake.wait(refresh_minutes() * 60)

    def _refresh(self, *_: Any) -> None:
        try:
            report = collect_once()
        except (CCNUEWError, ConfigError) as exc:
            self._apply(None, f"ccnu-epower：{exc}")
            return
        self._apply(report, tray_title(report))

    def _apply(self, report: Optional[dict[str, Any]], title: str) -> None:
        self._report = report
        if self._icon is None:
            return
        self._icon.icon = build_image(icon_text(report), icon_color(report))
        self._icon.title = title[:TOOLTIP_LIMIT]

    def _open_report(self, *_: Any) -> None:
        if not self._report:
            return
        from .cli import OUTPUT_DIR, OUTPUT_FILE

        path = Path(OUTPUT_DIR) / OUTPUT_FILE
        if path.exists():
            os.startfile(path)  # noqa: S606

    def _quit(self, *_: Any) -> None:
        self._wake.set()
        if self._icon is not None:
            self._icon.stop()


def autostart_target() -> str:
    """Return the command line that starts the tray at logon."""
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    executable = windowless if windowless.exists() else python
    return subprocess.list2cmdline([str(executable), "-m", "epower.tray"])


def install_autostart() -> str:
    import winreg

    command = autostart_target()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, command)
    return command


def uninstall_autostart() -> bool:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, AUTOSTART_NAME)
    except FileNotFoundError:
        return False
    return True


def _silence_missing_streams() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epower-tray", description="在 Windows 托盘显示宿舍电费"
    )
    parser.add_argument(
        "--install-autostart", action="store_true", help="写入开机自启，然后退出"
    )
    parser.add_argument(
        "--uninstall-autostart", action="store_true", help="删除开机自启，然后退出"
    )
    return parser


def project_root() -> Optional[Path]:
    """Return the repository root when the package runs from a source tree."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").exists() else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    from dotenv import load_dotenv

    args = build_parser().parse_args(argv)
    _silence_missing_streams()
    root = project_root()
    if root is not None:
        os.chdir(root)
    load_dotenv()

    if sys.platform != "win32":
        print("epower-tray 只支持 Windows", file=sys.stderr)
        return 1
    if args.install_autostart:
        print(f"已写入开机自启：{install_autostart()}")
        return 0
    if args.uninstall_autostart:
        removed = uninstall_autostart()
        print("已删除开机自启" if removed else "没有找到开机自启项")
        return 0

    TrayApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
