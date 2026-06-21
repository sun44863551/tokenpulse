"""QSS stylesheet for TokenPulse.

The look is a dark "developer dashboard" theme with subtle gradients and
rounded cards.  We intentionally avoid external assets so the app works
out of the box.
"""

QSS = """
* {
    font-family: "Segoe UI", "SF Pro Display", "Inter", sans-serif;
}

QMainWindow, QWidget#root {
    background-color: #0d1117;
    color: #e6edf3;
}

QLabel#titleLabel {
    font-size: 22px;
    font-weight: 600;
    color: #f0f6fc;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #8b949e;
}

QFrame#card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
}

QLabel#cardTitle {
    font-size: 12px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QLabel#cardValue {
    font-size: 28px;
    font-weight: 600;
    color: #f0f6fc;
}

QLabel#cardSubValue {
    font-size: 13px;
    color: #c9d1d9;
}

QLabel#pill {
    background-color: #1f6feb;
    color: white;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#pillWarning {
    background-color: #d29922;
    color: #0d1117;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#pillSuccess {
    background-color: #238636;
    color: white;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#pillDanger {
    background-color: #da3633;
    color: white;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}

QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #21262d;
}

QToolTip {
    background-color: #1f242c;
    color: #f0f6fc;
    border: 1px solid #30363d;
    padding: 4px;
}

QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: #f0f6fc;
    font-size: 11px;
    min-height: 12px;
}

QProgressBar::chunk {
    background-color: #2f81f7;
    border-radius: 5px;
}

QProgressBar#warning::chunk {
    background-color: #d29922;
}

QProgressBar#danger::chunk {
    background-color: #da3633;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #30363d;
    color: #f0f6fc;
}

QPushButton:pressed {
    background-color: #1f6feb;
    color: white;
}

QListWidget {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    color: #c9d1d9;
}

QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #21262d;
}

QListWidget::item:selected {
    background-color: #1f6feb;
    color: white;
}
"""