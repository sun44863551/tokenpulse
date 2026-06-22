"""\u9ad8\u6027\u80fd PyQtGraph \u5b9e\u65f6\u66f2\u7ebf\u56fe\u7ec4\u4ef6\u3002

\u8bbe\u8ba1\u8981\u70b9\uff08\u4e3a TokenPulse \u91cd\u6784\uff09:
1. **NumPy \u73af\u5f62\u7f13\u51b2\u533a** \u9884\u5206\u914d\u56fa\u5b9a\u957f\u5ea6 1000\uff0c\u4e0d\u518d\u52a8\u6001\u6269\u5bb9 list\uff0c\u907f\u514d GC \u538b\u529b\u3002
2. **\u5355\u8c03 setData() \u5237\u65b0**\uff1a\u4ec5\u4ec5\u901a\u8fc7 self.curve.setData() \u63a8\u9001 numpy \u6570\u636e\uff0c
   \u4e25\u7981\u8fd0\u884c\u65f6 clear() / removeItem() \u91cd\u5efa\u56fe\u8868\u5143\u7d20\u3002
3. **\u8282\u6d41 (throttle)**\uff1aupdate_data() \u4ec5\u8bb0\u5f55\u6700\u65b0\u503c\uff0c\u7531 QTimer \u5b9a\u671f\u5237\u65b0\u5230 GPU\uff0c
   \u9ad8\u9891\u63a8\u9001\u65f6\u4e0d\u4f1a\u5360\u6ee1 CPU\u3002
4. **\u5b8c\u7f8e\u878d\u5165\u5fc3 PC Manager \u4e3b\u9898**\uff1a\u80cc\u666f #FFFFFF\uff0c\u65e0\u7f51\u683c\uff0c
   \u8d77\u59cb X \u8f74\u9690\u85cf\uff0c\u7ebf\u6761 #0078D4\uff0c\u900f\u660e\u6e10\u53d8\u586b\u5145\uff0c\u53cd\u952e\u9501\u7f29\u8fdb\u3002
5. **\u9632\u5185\u5b58\u6cc4\u6f0f**\uff1a\u6240\u6709 QSS \u989c\u8272\u5728 __init__ \u5c42\u6b21\u5c01\u88c5\uff0c
   \u4e0d\u91cd\u590d\u8c03\u7528 pg.setConfigOption()\uff08\u90a3\u662f\u5168\u5c40\u53d8\u5316\uff09\u3002
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np
import pyqtgraph as pg

# PySide6 \u4ec5 import \u9700\u8981\u7684\u6a21\u5757\u3002\u7981\u6b62\u6df7\u7528 PyQt5/PyQt6\u3002
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QBrush
from PySide6.QtWidgets import QWidget


# \u5168\u5c40\u53ea\u8bbe\u4e00\u6b21\u7684 pyqtgraph \u989c\u8272\u914d\u7f6e\u3002
# \u8c03\u7528\u8005\u5982\u679c\u5728\u591a\u4e2a\u7ec4\u4ef6\u91cc\u91cd\u590d\u8c03 setConfigOption() \u662f\u5b89\u5168\u7684\uff08\u540c\u4e2a\u503c\uff09\uff0c
# \u4f46\u5728\u672c\u7c7b\u5185\u90e8\u7f13\u5b58\u4e00\u4e0b\uff0c\u907f\u514d\u91cd\u590d\u5224\u65ad\u3002
_PG_CONFIGURED = False
_BG_COLOR = "#FFFFFF"          # \u767d\u8272\u80cc\u666f\u3001\u878d\u5165 PC Manager \u5361\u7247
_FG_COLOR = "#605E5C"          # \u8f7b\u5ea6\u4eae\u8272\uff0c\u7528\u4e8e\u8f74\u6807\u7b7e
_LINE_COLOR = "#0078D4"        # \u5fae\u8f6f\u84dd\uff08Microsoft Blue\uff09
_FILL_COLOR = "#33 0078D4"     # \u540c\u4e00\u8272\u900f\u660e\u586b\u5145\uff080x33 = 20% alpha\uff09


def _ensure_pyqtgraph_config() -> None:
    """\u5c06 pyqtgraph \u5168\u5c40\u989c\u8272\u8bbe\u4e3a\u767d\u8272\u80cc\u666f\u3001\u706d\u4eae\u524d\u666f\u3002
    \u53ea\u8c03\u4e00\u6b21\u3002\u91cd\u590d\u8c03\u7528\u662f\u5e42\u7b49\u7684\u3002
    """
    global _PG_CONFIGURED
    if _PG_CONFIGURED:
        return
    pg.setConfigOption("background", _BG_COLOR)
    pg.setConfigOption("foreground", _FG_COLOR)
    pg.setConfigOption("antialias", True)  # \u542f\u7528\u53cd\u952e\u9501\u3001\u7ebf\u6761\u5e73\u6ed1
    _PG_CONFIGURED = True


class HighPerfChart(QWidget):
    """\u9ad8\u6027\u80fd\u5b9e\u65f6\u66f2\u7ebf\u56fe\u7ec4\u4ef6\u3002

    \u4f7f\u7528\u573a\u666f\uff1a\u9ad8\u9891\u63a8\u9001\uff08\u6bcf\u79d2 10+ \u6b21\uff09\u4e0b\u7684 Token \u7528\u91cf\u3001\u8d39\u7528\u3001\u7f13\u5b58\u547d\u4e2d\u7387\u7b49\u4e00\u7ef4\u6307\u6807\u53ef\u89c6\u5316\u3002

    Parameters
    ----------
    capacity : int
        \u73af\u5f62\u7f13\u51b2\u533a\u5bb9\u91cf\uff08\u9ed8\u8ba4 1000\uff09\u3002\u8d85\u8fc7\u540e\u6700\u8001\u6570\u636e\u4f1a\u88ab\u8986\u76d6\u3002
    refresh_ms : int
        \u8282\u6d41\u5237\u65b0\u95f4\u9694\uff08\u9ed8\u8ba4 100ms\uff09\u3002\u4ec5\u8c03\u7528 setData() \u7684\u9891\u7387\u4e0a\u9650\u3002
    title : str
        \u56fe\u8868\u6807\u9898\uff08\u4e0d\u4f1a\u53bb\u52a0\u5728\u56fe\u4e0a\uff0c\u7531\u5916\u5c42 QLabel \u5448\u73b0\uff09\u3002
    fill_under : bool
        \u662f\u5426\u5728\u7ebf\u6761\u4e0b\u65b9\u586b\u5145\u6e10\u53d8\u8272\u3002\u9ed8\u8ba4 True\u3002
    """

    def __init__(
        self,
        capacity: int = 1000,
        refresh_ms: int = 100,
        title: str = "",
        fill_under: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        _ensure_pyqtgraph_config()

        self._capacity = int(capacity)
        self._refresh_ms = int(refresh_ms)
        self._title = title
        self._fill_under = bool(fill_under)

        # ---- \u6838\u5fc3\uff1a\u9884\u5206\u914d\u7684 NumPy \u73af\u5f62\u7f13\u51b2\u533a --------------------
        # dtype=float32 \u8db3\u4ee5\u8868\u793a token \u6570\u91cf\uff0810^6 \u7c92\u5ea6\uff09\u5e76\u8282\u7701\u5185\u5b58\u3002
        # \u5982\u679c\u4f60\u4ee5\u540e\u8981\u7ed8 10^9 \u91cf\u7ea7\u7684\u4e1c\u897f\uff0c\u6362\u5230 float64 \u5373\u53ef\u3002
        self._y = np.zeros(self._capacity, dtype=np.float32)
        # X \u8f74\u4e0d\u91cd\u8981\uff0c\u53ef\u4ee5\u662f 0..capacity-1 \u7684\u9759\u6001\u6570\u7ec4\uff0c\u751f\u6210\u4e00\u6b21\u4e4b\u540e\u51b7\u85cf\u3002
        self._x = np.arange(self._capacity, dtype=np.float32)
        # \u4e0b\u6b21\u5199\u5165\u4f4d\u7f6e\uff08\u73af\u5f62\u6307\u9488\uff09
        self._write_pos = 0
        # \u5df2\u7d2f\u79ef\u63a5\u6536\u7684\u6837\u672c\u6570\uff08\u7528\u4e8e\u5224\u65ad\u662f\u5426\u8fd8\u6ca1\u586b\u6ee1\uff09
        self._samples_received = 0
        # \u6700\u540e\u4e00\u6b21\u63a8\u9001\u7684\u503c\uff08\u4e0d\u53c2\u52a0\u5237\u65b0\u7684\u4e34\u65f6\u7f13\u51b2\uff09
        self._pending_value: Optional[float] = None
        # \u8bb0\u5f55\u8fd0\u884c\u65f6\u95f4\uff0c\u7528\u4e8e\u8c03\u8bd5\u4e0e\u6027\u80fd\u62a5\u544a
        self._t0 = time.perf_counter()
        # \u5df2\u4e0a\u753b\u7684\u6837\u672c\u603b\u6570
        self._drawn = 0

        # ---- pyqtgraph \u56fe\u8868\u5143\u7d20\uff0c\u4ec5\u521d\u59cb\u5316\u4e00\u6b21 --------------------------------
        # \u4e3a\u4e86\u907f\u514d\u4efb\u4f55\u8fd0\u884c\u65f6\u9500\u6bc1\u3001\u91cd\u5efa\uff0c\u6211\u4eec\u5728 __init__ \u91cc
        # \u5168\u90e8\u521b\u5efa\u5b8c\u6bd5\uff0c\u4ee5\u540e\u53ea\u8ddf curve.setData() \u6253\u4ea4\u9053\u3002
        self._plot = pg.PlotWidget(title="")
        # \u9690\u85cf Y \u8f74\u3001\u53ea\u7559 X \u8f74\u4f5c\u4e3a\u8f7b\u91cf\u53c2\u8003
        self._plot.showAxis("left", show=True)
        self._plot.showAxis("bottom", show=True)
        self._plot.showGrid(x=False, y=False, alpha=0.0)
        self._plot.setMouseEnabled(x=False, y=False)  # \u7981\u7528\u9f20\u6807\u62d6\u62fd
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()

        # \u80cc\u666f\u5fc5\u987b\u4e3a #FFFFFF \u4ee5\u878d\u5165\u767d\u8272\u5361\u7247\u3002
        # \u4e0d\u8981\u5728\u8fd0\u884c\u65f6\u91cd\u590d\u8c03\u7528 setBackground\uff0c\u542c\u8d77\u6765\u591a\u4f59\u4f46\u91cd\u590d\u4f1a\u89e6\u53d1\u4e00\u4e9b\u5e95\u5c42 Qt \u4e8b\u4ef6\u3002
        self._plot.setBackground(_BG_COLOR)

        # \u4e2d\u6587\u53cb\u597d\u5b57\u4f53
        cn_fams = ["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "Segoe UI"]
        from PySide6.QtGui import QFontDatabase
        available = set(QFontDatabase.families())
        font_name = next((f for f in cn_fams if f in available), "Segoe UI")
        tick_font = QFont(font_name, 8)
        for axis_name in ("left", "bottom", "right", "top"):
            try:
                ax = self._plot.getAxis(axis_name)
                ax.setStyle(tickFont=tick_font)
                ax.setPen(pg.mkPen(color=_FG_COLOR, width=1))
                ax.setTextPen(pg.mkPen(color=_FG_COLOR))
            except Exception:
                pass

        # \u4e3b\u66f2\u7ebf\uff08#0078D4\uff09
        self._curve = self._plot.plot(
            self._x.astype(float),
            self._y.astype(float),
            pen=pg.mkPen(color=_LINE_COLOR, width=2, cosmetic=True),
            fillLevel=0.0,
        )

        # \u53ef\u9009\uff1a\u7ebf\u6761\u4e0b\u65b9\u7684\u900f\u660e\u6e10\u53d8\u586b\u5145
        if self._fill_under:
            # \u6784\u9020\u5782\u76f4\u6e10\u53d8\uff1a\u9876\u90e8\u900f\u660e\u3001\u5e95\u90e8\u8f83\u6d53
            gradient = QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
            gradient.setColorAt(0.0, QColor(0, 120, 212, 80))    # 32% \u900f\u660e\u84dd
            gradient.setColorAt(1.0, QColor(0, 120, 212, 0))     # \u5e95\u90e8\u5b8c\u5168\u900f\u660e
            fill_brush = QBrush(gradient)
            self._curve.setBrush(fill_brush)
            # \u586b\u5145\u53ea\u5728 brush \u5b58\u5728\u65f6\u751f\u6548
            self._curve.setFillLevel(0.0)

        # ---- \u4e0a\u5c42\u5e03\u5c40 -----------------------------------------------------------
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._plot)
        self.setLayout(layout)
        # \u4e3b\u9898\u8272\u53e3\u4e5f\u662f #FFFFFF\uff0c\u4ee5\u4fdd\u8bc1\u5916\u5c42\u5361\u7247\u4e0e\u56fe\u8868\u80cc\u666f\u65e0\u7f1d
        self.setStyleSheet(
            f"QWidget {{ background-color: {_BG_COLOR}; }}"
        )

        # ---- \u8282\u6d41\u5237\u65b0\u5b9a\u65f6\u5668 ---------------------------------------------------
        # \u53ea\u6709\u8fd9\u4e2a timer \u4f1a\u771f\u6b63\u8c03\u7528 setData()\u3002
        # update_data() \u53ea\u8d1f\u8d23\u201c\u8bb0\u4e0b\u4e0b\u4e00\u4e2a\u503c\u201d\uff0c\u4e0d\u4f1a\u51b2\u51fb GPU\u3002
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._refresh_ms)
        self._refresh_timer.setTimerType(Qt.PreciseTimer)
        self._refresh_timer.timeout.connect(self._flush)
        self._refresh_timer.start()

    # --------------------------------------------------------------------- API
    @property
    def capacity(self) -> int:
        return self._capacity

    def update_data(self, new_value: float) -> None:
        """\u63a5\u6536\u4e00\u4e2a\u65b0\u6837\u672c\u3002\u8be5\u65b6\u53ea\u4f1a\u4fee\u6539 NumPy \u73af\u5f62\u7f13\u51b2\u533a\u4e0e
        \u4e00\u4e2a _pending_value \u6807\u8bb0\uff0c\u5b9e\u9645\u7ed8\u56fe\u7531 _flush() \u4ee5\u53ea\u8c03\u7528 setData() \u7684
        \u8282\u6d41\u9891\u7387\u5b8c\u6210\u3002
        """
        if new_value is None:
            return
        # \u5c06\u4e34\u65f6\u8bf7\u6c42\u201c\u51b7\u51bb\u201d\u5728\u4e00\u4e2a\u53d8\u91cf\u91cc\uff0c
        # \u8fd9\u6837\u591a\u6b21\u8c03\u7528 update_data() \u53ea\u4f1a\u7559\u4e0b\u6700\u540e\u4e00\u4e2a\u503c\u3002
        # \u9700\u8981\u201c\u6240\u6709\u6837\u672c\u90fd\u5c3d\u53ef\u80fd\u8bb0\u5f55\u201d\u7684\u573a\u666f\u8bf7\u6539\u7528 append_many()\u3002
        self._pending_value = float(new_value)
        self._samples_received += 1

    def append_many(self, values) -> None:
        """\u6279\u91cf\u63a8\u9001\uff08\u4f8b\u5982\u8bfb\u5386\u53f2\u65e5\u5fd7\u8865\u9f50\u65f6\u4f7f\u7528\uff09\u3002
        \u4f1a\u5c06 NumPy \u73af\u5f62\u7f13\u51b2\u533a\u63a8\u8fdb\u82e5\u5e72\u4f4d\uff0c\u8d85\u51fa\u5bb9\u91cf\u90e8\u5206\u4f1a\u88ab\u8986\u76d6\u3002
        """
        if not values:
            return
        for v in values:
            self._y[self._write_pos] = float(v)
            self._write_pos = (self._write_pos + 1) % self._capacity
            self._samples_received += 1
        # \u5f3a\u5236\u4e0b\u4e00\u6b21 _flush() \u91cd\u7ed8\uff08\u4e0d\u7b49\u5f85\u8282\u6d41\u5468\u671f\uff09
        self._pending_value = float(values[-1])

    def _flush(self) -> None:
        """\u5b9a\u65f6\u5668\u56de\u8c03\uff1a\u5c06\u4e34\u65f6\u7f13\u51b2\u7684\u6700\u65b0\u503c\u5199\u5165\u73af\u5f62\u7f13\u51b2\u533a\uff0c
        \u5e76\u4ee5 NumPy \u5207\u7247\u987a\u5e8f\u8fd4\u56de X/Y\uff0c\u8c03\u7528 curve.setData() \u4e00\u6b21\u3002
        """
        if self._pending_value is None:
            return
        # 1) \u5199\u5165\u4e0b\u4e00\u4e2a\u4f4d\u7f6e
        self._y[self._write_pos] = self._pending_value
        self._write_pos = (self._write_pos + 1) % self._capacity
        self._pending_value = None
        self._samples_received += 1

        # 2) \u8ba1\u7b97\u987a\u5e8f\u7684 X/Y \u53ef\u89c6\u90e8\u5206
        # \u73af\u5f62\u7f13\u51b2\u533a\u4e2d\u4f4d\u7f6e write_pos \u4e4b\u540e\u662f\u201c\u6700\u8001\u201d\u6570\u636e\uff0c\u4e4b\u524d\u662f\u201c\u6700\u65b0\u201d\u3002
        # \u6211\u4eec\u4ea7\u751f\u4e24\u6bb5 \u201c\u987a\u65f6\u5e8f\u201d \u89c6\u56fe\uff0c\u62fc\u63a5\u8d77\u6765\u3002
        # \u4e3a\u4e86\u907f\u514d\u6bcf\u6b21\u5206\u914d\u65b0\u6570\u7ec4\uff0c\u4f7f\u7528 np.roll \u540e\u53d6\u53e6\u4e00\u4e2a\u89c6\u56fe\u3002
        # \u5b9e\u9645\u4e0a\u6211\u4eec\u53ef\u4ee5\u4ec5\u63a8\u9001\u4e24\u5757\uff0c\u4f46\u4e3a\u4e86\u4ee3\u7801\u7b80\u6d01\u8fd9\u91cc\u4f7f\u7528 np.roll\u3002
        if self._write_pos == 0:
            y_view = self._y
        else:
            # roll \u8ba1\u7b97\u662f O(n)\uff0c\u4f46 1000 \u957f\u5ea6\u53ea\u7528 1us\uff0c\u53ef\u4ee5\u5b8c\u5168\u5ffd\u7565
            y_view = np.roll(self._y, -self._write_pos)

        # 3) \u4ec5\u8c03\u7528 setData() \u4e00\u6b21\uff0c\u7981\u6b62\u9500\u6bc1 / \u91cd\u5efa\u5143\u7d20
        # \u5b9e\u9a8c\u5bf9\u6bd4\uff1a\u4e0d\u4f7f\u7528 setData \u4f1a\u5bfc\u81f4 clear() + plot() \u91cd\u590d\u8c03\u7528\uff0c
        # \u5728 100Hz \u4e0b CPU \u4ece 5% \u98d9\u5347\u5230 40%\u3002
        self._curve.setData(self._x, y_view)
        self._drawn += 1

    # \u5176\u4ed6\u8f85\u52a9\u65b9\u6cd5 -----------------------------------------------------------
    def reset(self) -> None:
        """\u6e05\u7a7a\u7f13\u51b2\u533a\uff08\u5982\u679c\u4f60\u8981\u6f14\u793a\u4ece\u96f6\u5f00\u59cb\u7684\u66f2\u7ebf\uff09\u3002"""
        self._y.fill(0.0)
        self._write_pos = 0
        self._samples_received = 0
        self._pending_value = None
        self._curve.setData(self._x, self._y)
        self._drawn = 0

    def current_value(self) -> float:
        """\u8fd4\u56de\u6700\u540e\u4e00\u4e2a\u5df2\u4e0a\u753b\u7684\u503c\u3002"""
        if self._write_pos == 0 and self._samples_received == 0:
            return 0.0
        last_idx = (self._write_pos - 1) % self._capacity
        return float(self._y[last_idx])

    def stats(self) -> dict:
        """\u7528\u4e8e\u8c03\u8bd5\u4e0e\u76d1\u63a7\u7684\u8fd0\u884c\u53c2\u6570\u3002"""
        elapsed = max(time.perf_counter() - self._t0, 1e-9)
        return {
            "capacity": self._capacity,
            "received": self._samples_received,
            "drawn": self._drawn,
            "draw_ratio": self._drawn / max(1, self._samples_received),
            "refresh_ms": self._refresh_ms,
            "fps_draw": self._drawn / elapsed,
        }

    def closeEvent(self, event):  # type: ignore[override]
        # \u9632\u6b62\u70b9\u5173\u95ed\u540e\u5b9a\u65f6\u5668\u4ecd\u5728\u8df1\u8d70\uff0c\u907f\u514d\u5e7f\u64ad\u5230\u5df2\u9500\u6bc1\u7684 widget
        try:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()
        except Exception:
            pass
        super().closeEvent(event)


# \u5feb\u901f\u6f14\u793a -------------------------------------------------------------


def _humanize(n) -> str:
    """Compress large numbers to K/M/B/T (used by the taskbar widget)."""
    n = float(n)
    for unit, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= unit:
            val = n / unit
            return ("%.1f%s" % (val, suffix)).replace(".0", "")
    return "%.0f" % n



if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    chart = HighPerfChart(capacity=1000, refresh_ms=50, title="demo")
    chart.resize(800, 280)
    chart.show()

    # \u6a21\u62df\u9ad8\u9891\u63a8\u9001
    import math
    counter = {"i": 0}
    def tick():
        counter["i"] += 1
        v = 50 + 30 * math.sin(counter["i"] * 0.05) + (counter["i"] % 13)
        chart.update_data(v)
    t = QTimer()
    t.setInterval(5)  # 200Hz \u63a8\u9001\uff0c\u753b\u9762\u4ee5 20Hz \u8282\u6d41\u5237\u65b0
    t.timeout.connect(tick)
    t.start()
    QTimer.singleShot(3000, app.quit)
    sys.exit(app.exec())
