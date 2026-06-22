"""\u5c06 TokenPulse \u5fae\u578b\u76d1\u63a7\u9762\u677f\u5d4c\u5165 Windows \u4efb\u52a1\u680f\u7684\u5e95\u5c42\u6a21\u5757\u3002

\u672c\u6a21\u5757\u5b9e\u73b0\u4e09\u4ef6\u4e8b\uff1a
1. \u4f7f\u7528 ctypes \u8c03\u7528 Shell32.SetCurrentProcessExplicitAppUserModelID \u4e3a\u5f53\u524d\u8fdb\u7a0b\u6ce8\u518c\u72ec\u7acb
   \u7684\u5e94\u7528\u8eab\u4efd ID\u3002\u8fd9\u662f\u4f7f Windows \u4efb\u52a1\u680f / \u6258\u76d8\u4e0d\u518d\u663e\u793a Python.exe \u9ed8\u8ba4
   \u56fe\u6807\u7684\u6839\u672c\u63aa\u65bd\u3002\u4f60\u5e94\u5728 import \u5b8c PySide6 \u4e4b\u540e\u3001QApplication \u5b9e\u4f8b\u5316\u4e4b\u524d
   \u8c03\u7528 setup_app_identity()\u3002
2. \u63d0\u4f9b\u4e00\u4e2a TaskbarMonitorWidget \u6784\u4ef6\uff0c\u5185\u90e8\u53ea\u88c5\u4e00\u4e2a\u7d27\u51d1\u578b QLabel\uff0c
   \u9762\u677f\u4e3a\u201cTkns: 12.5K | Cost: \u00a50.15\u201d\u8fd9\u79cd\u4e00\u884c\u6587\u672c\u3002
3. \u63d0\u4f9b embed_into_taskbar() \u4e0e fallback_to_corner() \u4e24\u4e2a\u51fd\u6570\uff0c\u4f1a\u5c1d\u8bd5
   win32gui.SetParent \u5c06 widget \u6302\u8f7d\u5230 Shell_TrayWnd\uff0c\u5931\u8d25\u5219\u964d\u7ea7\u4e3a
   \u5c4f\u5e55\u53f3\u4e0b\u89d2\u5bc6\u8d34\u6258\u76d8\u4e0a\u65b9\u7684\u7edd\u5bf9\u5750\u6807\u3002

\u5176\u4e2d\u6240\u6709\u53ef\u80fd\u62a5\u9519\u7684 Win32 \u8c03\u7528\u90fd\u88ab try/except \u5305\u88f9\uff0c\u4ee5\u9632 Windows 11 \u4efb\u52a1\u680f
\u4e2d\u592e\u96c6\u4e2d\u5e03\u5c40\u9020\u6210\u7684 E_ACCESSDENIED \u3002
"""

from __future__ import annotations

# ctypes \u90e8\u5206\uff1a\u5fc5\u987b\u5728 import \u9636\u6bb5\u5b8c\u6210\uff0c\u6240\u4ee5\u653e\u5728\u6587\u4ef6\u9876\u90e8\u3002
# \u4f46\u4e3a\u4e86\u907f\u514d\u5728\u5176\u4ed6\u5e73\u53f0\u4e0a\u8df3\u51fa\u9519\uff08\u4f8b\u5982\u4ec5\u5b8c\u5168\u4e0d\u5b58\u5728 shell32\uff09\uff0c\u4f60\u53ef\u4ee5\u5728
# \u8c03\u7528\u8005\u811a\u672c\u91cc\u5148\u68c0\u67e5 sys.platform == "win32"\u3002
import ctypes
import sys
from ctypes import wintypes
from typing import Optional, Tuple

# PySide6 \u5bfc\u5165\u9650\u5b9a\uff0c\u4e0d\u6df7\u7528 PyQt5/PyQt6\u3002
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget


# ========================================================================
# 1) AppUserModelID \u2014 \u8eab\u4efd\u9519\u91cf\u91cd\u5b9a\u5411
# ========================================================================
APP_ID = "TokenPulse.CoreApp.v1"  # \u5e94\u7528\u8eab\u4efd ID\uff0c\u8df3\u51fa\u6258\u76d8\u9ed8\u8ba4\u56fe\u6807\u7684\u6839\u672c


def setup_app_identity(app_id: str = APP_ID) -> bool:
    """\u8c03\u7528 Windows Shell32.SetCurrentProcessExplicitAppUserModelID\u3002

    \u8fd4\u56de True \u8868\u793a\u6210\u529f\uff0cFalse \u8868\u793a\u51fd\u6570\u672c\u8eab\u4e0d\u53ef\u7528\u6216\u88ab\u62d2\u7edd\u3002

    \u4f7f\u7528\u65b9\u6cd5\uff08\u4e3b\u811a\u672c\u6700\u9760\u524d\uff09:
        from tokenpulse.platform.taskbar_embedder import setup_app_identity
        setup_app_identity()
        app = QApplication(sys.argv)
        app.setApplicationDisplayName("TokenPulse")
    """
    if sys.platform != "win32":
        return False
    try:
        # ctypes.windll \u5728 Windows \u4e0b\u4f1a\u61c2\u5f97\u52a0\u8f7d shell32.dll
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except (OSError, AttributeError) as exc:
        # \u5982\u679c\u51fd\u6570\u4e0d\u5b58\u5728\uff08\u4e0d\u5e94\u8be5\uff09\u6216\u8005\u88ab\u62d2\u7edd\uff0c\u8fd4\u56de False\u3002
        # \u8c03\u7528\u8005\u53ef\u4ee5\u9009\u62e9\u662f\u5426\u7ed3\u675f\u8fdb\u7a0b\uff0c\u9ed8\u8ba4\u5141\u8bb8\u964d\u7ea7\u8fd0\u884c\u3002
        print(f"[taskbar_embedder] SetAppUserModelID failed: {exc}", file=sys.stderr)
        return False


# ========================================================================
# 2) TaskbarMonitorWidget \u2014 \u4e00\u4e2a\u8d85\u8f7b\u91cf\u7684 QWidget
# ========================================================================
class TaskbarMonitorWidget(QWidget):
    """\u4efb\u52a1\u680f\u5185\u5d4c\u7684\u8d85\u8f7b\u91cf\u9762\u677f\u3002

    \u8bbe\u8ba1\u539f\u5219\uff1a
    - \u53ea\u542b\u4e00\u4e2a QLabel\uff0c\u663e\u793a\u6837\u5f0f\u4e3a "Tkns: 12.5K | Cost: \u00a50.15"
    - \u9ed8\u8ba4\u80cc\u666f\u4e0e\u4efb\u52a1\u680f\u5408\u5e76\uff1a\u900f\u660e (WA_TranslucentBackground)
    - \u4e0d\u53ef\u4ee5\u6709\u6846 (FramelessWindowHint)
    - \u53ef\u9009\u8bbe\u4e3a\u4efb\u52a1\u680f\u7684\u5b50\u7a97\u53e3\uff08\u8c03\u7528\u8005\u8d1f\u8d23\u8c03\u7528 embed_into_taskbar\uff09
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # \u6784\u9020\u65f6\u5c31\u5f3a\u52a0\u4e24\u4e2a flag\uff1a
        #   - FramelessWindowHint\uff1a\u65e0\u6807\u9898\u680f / \u8fb9\u6846
        #   - Tool\uff1a\u4e0d\u5728\u4efb\u52a1\u680f\u51fa\u73b0\u72ec\u7acb\u56fe\u6807\uff08\u907f\u514d\u4e0e\u4e3b\u7a97\u53e3\u91cd\u590d\uff09
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        # \u900f\u660e\u80cc\u666f\uff0c\u8ba9 Windows \u4efb\u52a1\u680f\u80cc\u666f\u900f\u51fa\u6765
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # \u4e0d\u53d6\u7126\u70b9
        self.setFocusPolicy(Qt.NoFocus)

        # \u4e2d\u6587\u53cb\u597d\u5b57\u4f53
        from PySide6.QtGui import QFontDatabase
        available = set(QFontDatabase.families())
        font_name = next(
            (f for f in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI")
             if f in available),
            "Segoe UI",
        )
        self._label = QLabel("Tkns: 0  |  Cost: \u00a50.00", self)
        font = QFont(font_name, 9)
        font.setBold(False)
        self._label.setFont(font)
        # \u6587\u672c\u989c\u8272\u8d8b\u8fd1\u767d\u8272\uff0c\u4ee5\u9002\u5e94 Windows 11 \u4efb\u52a1\u680f\u9ed1\u8272\u80cc\u666f
        palette = self._label.palette()
        palette.setColor(QPalette.WindowText, QColor("#FFFFFF"))
        self._label.setPalette(palette)
        # \u53bb\u6389 padding\uff0c\u8ba9 label \u80fd\u62e5\u63a5\u4e0a\u4e0b\u53f3\u53f3
        self._label.setContentsMargins(0, 0, 0, 0)
        self._label.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)

        # \u6a2a\u5411\u5e03\u5c40\uff0c\u8ba9 label \u586b\u6ee1\u6574\u4e2a widget
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)  # \u5de6\u53f3 8px \u5185\u8fb9\u8ddd\uff0c\u4e0a\u4e0b 2px
        layout.setSpacing(0)
        layout.addWidget(self._label)

    # ------------------------------------------------------------------ API
    def set_metrics(self, tokens: int, cost: float, plan_label: str = "") -> None:
        """\u66f4\u65b0\u663e\u793a\u6587\u672c\u3002

        tokens\uff1a\u5f53\u524d\u4f1a\u8bdd\u603b token \u6570\u91cf
        cost\uff1a\u5f53\u524d\u4f1a\u8bdd\u7d2f\u8ba1\u8d39\u7528\uff08\u5143\uff09
        plan_label\uff1a\u53ef\u9009\uff0c\u4f8b\u5982 "Plus"\u3002\u4e3a\u7a7a\u5219\u4e0d\u663e\u793a\u3002
        """
        from ..ui.high_perf_chart import _humanize  # \u590d\u7528\u5168\u5c40\u4eba\u6027\u5316\u51fd\u6570
        tkns_text = _humanize(tokens) if tokens > 0 else "0"
        cost_text = "\u00a5{:.2f}".format(cost) if cost >= 1 else "\u00a5{:.4f}".format(cost)
        plan_part = ("  |  " + plan_label) if plan_label else ""
        self._label.setText(f"Tkns: {tkns_text}  |  Cost: {cost_text}{plan_part}")


# ========================================================================
# 3) Win32 \u4efb\u52a1\u680f\u6302\u8f7d\u903b\u8f91
# ========================================================================
# \u5728 Windows 7/10/11 \u4e0a\uff0c\u4efb\u52a1\u680f\u7a97\u53e3\u7c7b\u540d\u7c7b\u4e3a "Shell_TrayWnd"\u3002
# \u5982\u679c\u4f60\u7684 Windows \u662f\u591a\u4e2a\u663e\u793a\u5668 + \u4efb\u52a1\u680f\u62d3\u5c55\uff0c\u53ef\u80fd\u4f1a\u6709\u591a\u4e2a\uff0c\u4f46\u53ea\u9700\u8981\u7b2c\u4e00\u4e2a\u3002
SHELL_TRAY_CLASS = "Shell_TrayWnd"


def _find_shell_tray_hwnd() -> Optional[int]:
    """\u67e5\u627e Windows \u4efb\u52a1\u680f\u7684\u539f\u751f\u7a97\u53e3\u53e5\u67c4\u3002

    \u91c7\u7528\u9636\u68af\u5f0f\u9000\u907f\uff1a
    1. \u9996\u9009 win32gui\uff08\u5982\u679c pywin32 \u5df2\u5b89\u88c5\uff09
    2. \u5176\u6b21 ctypes + user32.FindWindowW
    3. \u4e0d\u53ef\u7528\u5219\u8fd4\u56de None
    """
    if sys.platform != "win32":
        return None
    # 1) pywin32 \u8def\u5f84
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.FindWindow(SHELL_TRAY_CLASS, None)
        if hwnd:
            return int(hwnd)
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] win32gui.FindWindow failed: {exc}", file=sys.stderr)
    # 2) ctypes \u5907\u9009\u8def\u5f84
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(SHELL_TRAY_CLASS, None)
        if hwnd:
            return int(hwnd)
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] ctypes FindWindowW failed: {exc}", file=sys.stderr)
    return None


def _get_widget_hwnd(widget: QWidget) -> int:
    """\u63d0\u53d6 QWidget \u7684\u539f\u751f Windows \u7a97\u53e3\u53e5\u67c4\u3002"""
    return int(widget.winId())  # winId() \u8fd4\u56de WId\uff0c\u5728 Windows \u4e0b\u7b49\u540c hwnd


def _set_parent(child_hwnd: int, parent_hwnd: int) -> bool:
    """\u8c03\u7528 SetParent\uff0c\u8fd4\u56de\u662f\u5426\u6210\u529f\u3002"""
    if sys.platform != "win32":
        return False
    try:
        import win32gui  # type: ignore
        win32gui.SetParent(child_hwnd, parent_hwnd)
        return True
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] win32gui.SetParent failed: {exc}", file=sys.stderr)
    # ctypes \u5907\u9009\u8def\u5f84
    try:
        user32 = ctypes.windll.user32
        user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
        user32.SetParent.restype = wintypes.HWND
        result = user32.SetParent(child_hwnd, parent_hwnd)
        return result != 0
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] ctypes SetParent failed: {exc}", file=sys.stderr)
        return False


def _move_to_tray_slot(child_hwnd: int, tray_hwnd: int, width: int = 220, height: int = 28) -> bool:
    """\u5728\u4efb\u52a1\u680f\u4e0a\u8c03\u6574\u4f4d\u7f6e\uff1a\u9ed8\u8ba4\u5e03\u5c40\u4e3a TrayNotifyIcon \u5de6\u4fa7\u3002"""
    if sys.platform != "win32":
        return False
    # SetWindowPos flags
    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040
    SWP_NOACTIVATE = 0x0010
    flags = SWP_NOZORDER | SWP_SHOWWINDOW | SWP_NOACTIVATE
    try:
        import win32gui  # type: ignore
        # \u67e5\u4efb\u52a1\u680f\u5de6\u4e0a\u89d2\uff0c\u628a widget \u653e\u5230 TrayNotifyWnd \u4e4b\u524d
        tray_rect = win32gui.GetWindowRect(tray_hwnd)
        # \u9ed8\u8ba4\u653e\u4efb\u52a1\u680f\u53f3\u4fa7\u7b2c\u4e8c\u4e2a\u533a\u57df\uff08\u9002\u5408\u4e2d\u6587 Windows\uff09
        x = tray_rect[0] + 200
        y = tray_rect[1] + (tray_rect[3] - tray_rect[1] - height) // 2
        win32gui.SetWindowPos(child_hwnd, 0, x, y, width, height, flags)
        return True
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] win32gui.SetWindowPos failed: {exc}", file=sys.stderr)
    try:
        user32 = ctypes.windll.user32
        # RECT \u7ed3\u6784
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = RECT()
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        if not user32.GetWindowRect(tray_hwnd, ctypes.byref(rect)):
            return False
        x = rect.left + 200
        y = rect.top + ((rect.bottom - rect.top - height) // 2)
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        return bool(user32.SetWindowPos(child_hwnd, 0, x, y, width, height, flags))
    except Exception as exc:  # pragma: no cover
        print(f"[taskbar_embedder] ctypes SetWindowPos failed: {exc}", file=sys.stderr)
        return False


# ========================================================================
# 4) \u4e3b\u5165\u53e3\uff1a\u5c1d\u8bd5\u6302\u8f7d \u2192 \u5931\u8d25\u964d\u7ea7
# ========================================================================
def embed_into_taskbar(widget: TaskbarMonitorWidget) -> bool:
    """\u5c06 TaskbarMonitorWidget \u6302\u8f7d\u5230 Windows \u4efb\u52a1\u680f\u3002\u6210\u529f\u8fd4\u56de True\u3002

    \u5931\u8d25\u539f\u56e0\u53ef\u80fd\u662f\uff1a
    - \u4e0d\u5728 Windows \u4e0a\u8fd0\u884c
    - \u672a\u88c5 pywin32 \u4e14 ctypes \u8def\u5f84\u4e5f\u5931\u8d25
    - Windows 11 \u4efb\u52a1\u680f\u4e2d\u592e\u96c6\u4e2d\uff0cAPI \u62d2\u7edd\u8bbf\u95ee
    - \u4efb\u52a1\u680f\u88ab\u9690\u85cf

    \u8c03\u7528\u8005\u5e94\u5728\u8fd9\u4e2a\u51fd\u6570\u8fd4\u56de False \u540e\u624b\u52a8\u8c03\u7528 fallback_to_corner(widget)\u3002
    """
    if sys.platform != "win32":
        return False
    try:
        # \u4fdd\u8bc1 widget \u5df2\u7ecf show() \u8fc7\u4e86\uff0c\u5426\u5219 winId \u4ecd\u53ef\u80fd\u6709\u6548\u4f46\u4e0d\u53ef\u89c1
        if not widget.isVisible():
            widget.show()
        # \u7ed9 Qt \u4e00\u70b9\u65f6\u95f4\u8ba9\u5b83\u5b8c\u6210 show
        QApplication.processEvents()
        tray_hwnd = _find_shell_tray_hwnd()
        if not tray_hwnd:
            return False
        child_hwnd = _get_widget_hwnd(widget)
        if not _set_parent(child_hwnd, tray_hwnd):
            return False
        if not _move_to_tray_slot(child_hwnd, tray_hwnd, width=220, height=28):
            # \u4f4d\u7f6e\u8c03\u6574\u5931\u8d25\u4e0d\u91cd\u8981\uff0cSetParent \u5df2\u7ecf\u6210\u529f
            pass
        return True
    except Exception as exc:  # \u6700\u540e\u4e00\u9053\u9632\u7ebf
        print(f"[taskbar_embedder] embed failed: {exc}", file=sys.stderr)
        return False


def fallback_to_corner(widget: TaskbarMonitorWidget) -> bool:
    """\u4efb\u52a1\u680f\u6302\u8f7d\u5931\u8d25\u540e\u7684\u964d\u7ea7\u7b56\u7565\u3002

    \u8868\u73b0\uff1a
    - \u5c06 widget \u4ece\u4efb\u4f55\u7236\u7a97\u53e3\u62c6\u51fa\uff08SetParent(NULL)\uff09
    - \u52a0\u4e0a Tool | FramelessWindowHint | WindowStaysOnTopHint
    - \u6839\u636e\u4e3b\u5c4f\u5e55\u53ef\u7528\u533a\u57df\u3001\u6258\u76d8\u4f4d\u7f6e\uff0c\u5b9a\u4f4d\u5230\u53f3\u4e0b\u89d2\u6258\u76d8\u4e0a\u65b9
    """
    if sys.platform != "win32":
        return False
    try:
        widget_hwnd = _get_widget_hwnd(widget)
        # \u5c06\u7236\u7a97\u53e3\u91cd\u7f6e\u4e3a None\uff08\u62c6\u51fa\u4efb\u52a1\u680f\uff09
        try:
            _set_parent(widget_hwnd, 0)
        except Exception:
            pass
        # \u91cd\u7f6e flag
        widget.setParent(None)
        widget.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        widget.setAttribute(Qt.WA_TranslucentBackground, True)
        # \u5c4f\u5e55\u53f3\u4e0b\u89d2\uff0c\u6258\u76d8\u4e0a\u65b9 36px \u5904
        screen = QApplication.primaryScreen()
        if screen is None:
            return False
        screen_geo = screen.availableGeometry()
        w, h = 220, 28
        # \u53f3\u4e0b\u89d2\u5750\u6807\uff0c\u7559 12px \u8fb9\u8ddd
        x = screen_geo.right() - w - 12
        y = screen_geo.bottom() - h - 36
        widget.setGeometry(x, y, w, h)
        widget.show()
        widget.raise_()
        return True
    except Exception as exc:
        print(f"[taskbar_embedder] fallback failed: {exc}", file=sys.stderr)
        return False


def setup_taskbar_monitor(initial_tokens: int = 0, initial_cost: float = 0.0) -> Optional[TaskbarMonitorWidget]:
    """\u4e00\u952e\u8d77\u4f4f\u4efb\u52a1\u680f\u76d1\u63a7\u9762\u677f\u3002

    \u8fd4\u56de widget \u5b9e\u4f8b\uff0c\u8c03\u7528\u8005\u5e94\u4fdd\u7559\u8be5\u5b9e\u4f8b\u53c2\u8003\uff0c\u5b9a\u671f\u8c03\u7528 set_metrics \u5237\u65b0\u3002
    \u5982\u679c\u6302\u8f7d\u5931\u8d25\u4f1a\u81ea\u52a8\u964d\u7ea7\u4e3a\u53f3\u4e0b\u89d2\u60ac\u6d6e\u9762\u677f\u3002
    """
    if sys.platform != "win32":
        return None
    widget = TaskbarMonitorWidget()
    widget.set_metrics(initial_tokens, initial_cost)
    if embed_into_taskbar(widget):
        return widget
    if fallback_to_corner(widget):
        return widget
    # \u4e24\u79cd\u90fd\u5931\u8d25\u4e86\uff08\u4e0d\u53ef\u80fd\uff0c\u4f46\u4ee5\u9632\u4e07\u4e00\uff09
    return None


# \u5feb\u901f\u9a8c\u8bc1 -------------------------------------------------------------------
if __name__ == "__main__":
    # \u5fc5\u987b\u5148\u8c03\u7528\u8eab\u4efd\u6ce8\u518c
    setup_app_identity()
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("TokenPulse")
    w = setup_taskbar_monitor(initial_tokens=12500, initial_cost=0.15)
    if w:
        print("[OK] taskbar monitor visible, set_metric() ready")
    else:
        print("[WARN] taskbar monitor unavailable on this platform")
    QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())
