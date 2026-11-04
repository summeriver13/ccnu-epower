"""Windows taskbar band that shows the dorm electricity balance."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from .config import CliOptions, credentials_from_env, resolve_target
from .errors import CCNUEWError, ConfigError
from .widget import (
    alert_cleared,
    alert_due,
    balance_value,
    band_text,
    refresh_minutes,
    text_color,
)

WIN = sys.platform == "win32"
AUTOSTART_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
AUTOSTART_NAME = "ccnu-epower-band"
ACTION_REFRESH = 1
ACTION_OPEN = 2
ACTION_QUIT = 3
LIGHT_TASKBAR = (243, 243, 243)
DARK_TASKBAR = (32, 32, 32)
RESTART_DELAY_SECONDS = 3.0
KEEP_ON_TOP_SECONDS = 3.0


def taskbar_is_light() -> bool:
    """Return True when the taskbar uses the light theme."""
    if not WIN:
        return False
    import winreg

    path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return bool(winreg.QueryValueEx(key, "SystemUsesLightTheme")[0])
    except OSError:
        return False


def collect_once() -> dict[str, Any]:
    """Run one query and write the JSON report."""
    from .cli import query, write_report

    target = resolve_target(CliOptions())
    if target is None:
        raise ConfigError("缺少目标宿舍：请在 .env 设置 CCNU_METER_ID 或四个房间变量")
    report = query(credentials_from_env(), target)
    write_report(report)
    return report


class TaskbarApp:
    """Owns the band window, the cached report, and the refresh thread."""

    def __init__(self) -> None:
        from .band import Band

        self.light = taskbar_is_light()
        self.background = LIGHT_TASKBAR if self.light else DARK_TASKBAR
        self.report: Optional[dict[str, Any]] = None
        self.message = ""
        self.quit_requested = False
        self.alerted = False
        self.band = Band(
            band_text(None),
            text_color(None, self.light),
            self.background,
            on_left_click=self.open_report,
            on_right_click=self.show_menu,
        )
        self._stop = threading.Event()

    def run(self) -> int:
        if not self.band.create():
            print("找不到任务栏，无法显示电费", file=sys.stderr)
            return 1
        for target in (self._loop, self._keep_on_top):
            threading.Thread(target=target, daemon=True).start()
        self.band.run()
        self._stop.set()
        return 0 if self.quit_requested else 1

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(refresh_minutes() * 60)

    def _keep_on_top(self) -> None:
        while not self._stop.is_set():
            self.band.keep_on_top()
            self._stop.wait(KEEP_ON_TOP_SECONDS)

    def refresh(self) -> None:
        """Fetch a new report and repaint the band."""
        try:
            report = collect_once()
        except (CCNUEWError, ConfigError) as exc:
            self.message = str(exc)
            self.apply(None)
            return
        self.message = ""
        self.apply(report)

    def apply(self, report: Optional[dict[str, Any]]) -> None:
        self.report = report
        self.band.update(band_text(report), text_color(report, self.light))
        self._alert(balance_value(report))

    def _alert(self, value: Optional[float]) -> None:
        if alert_cleared(value):
            self.alerted = False
            return
        if alert_due(value, self.alerted):
            from .notify import send_low_balance

            self.alerted = send_low_balance(value)

    def open_report(self) -> None:
        from .cli import OUTPUT_DIR, OUTPUT_FILE

        path = Path(OUTPUT_DIR) / OUTPUT_FILE
        if path.exists():
            os.startfile(path)  # noqa: S606

    def show_menu(self) -> None:
        from . import win32

        status = self.message or band_text(self.report)
        win32.show_menu(
            self.band.hwnd,
            [
                (status, 0, True),
                (None, 0, False),
                ("立即刷新", ACTION_REFRESH, False),
                ("打开报告", ACTION_OPEN, False),
                ("退出", ACTION_QUIT, False),
            ],
            self._on_command,
        )

    def _on_command(self, command: int) -> None:
        if command == ACTION_REFRESH:
            threading.Thread(target=self.refresh, daemon=True).start()
        elif command == ACTION_OPEN:
            self.open_report()
        elif command == ACTION_QUIT:
            self.quit_requested = True
            self.band.close()


def autostart_target() -> str:
    """Return the command line that starts the band at logon."""
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    executable = windowless if windowless.exists() else python
    return subprocess.list2cmdline([str(executable), "-m", "epower.taskbar"])


def install_autostart() -> str:
    import winreg

    command = autostart_target()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
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
        prog="epower-band", description="在 Windows 任务栏显示宿舍电费"
    )
    parser.add_argument(
        "--install-autostart", action="store_true", help="写入开机自启，然后退出"
    )
    parser.add_argument(
        "--uninstall-autostart", action="store_true", help="删除开机自启，然后退出"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    from dotenv import load_dotenv

    args = build_parser().parse_args(argv)
    _silence_missing_streams()
    if not WIN:
        print("epower-band 只支持 Windows", file=sys.stderr)
        return 1
    root = project_root()
    if root is not None:
        os.chdir(root)
    load_dotenv()

    if args.install_autostart:
        print(f"已写入开机自启：{install_autostart()}")
        return 0
    if args.uninstall_autostart:
        removed = uninstall_autostart()
        print("已删除开机自启" if removed else "没有找到开机自启项")
        return 0

    from . import win32

    win32.enable_dpi_awareness()
    while True:
        code = TaskbarApp().run()
        if code == 0 or win32.taskbar_present():
            return code
        time.sleep(RESTART_DELAY_SECONDS)


def project_root() -> Optional[Path]:
    """Return the repository root when the package runs from a source tree."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").exists() else None


if __name__ == "__main__":
    sys.exit(main())
