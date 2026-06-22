"""QSS stylesheet for TokenPulse.

PC Manager style: light theme, white cards with subtle shadow,
Microsoft blue (#0078D4) accent, generous whitespace, rounded corners.
"""

# ---------------------------------------------------------------- palette
COLOR_BG = "#F3F3F3"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1F1F1F"
COLOR_TEXT_SECONDARY = "#605E5C"
COLOR_TEXT_MUTED = "#8A8886"
COLOR_BORDER = "#EDEBE9"
COLOR_ACCENT = "#0078D4"
COLOR_ACCENT_HOVER = "#106EBE"
COLOR_ACCENT_PRESSED = "#005A9E"
COLOR_SUCCESS = "#107C10"
COLOR_WARNING = "#FF8C00"
COLOR_DANGER = "#D13438"

QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    color: """ + COLOR_TEXT + """;
}

QMainWindow,
QWidget#root {
    background-color: """ + COLOR_BG + """;
}

QLabel#titleLabel {
    font-size: 24px;
    font-weight: 600;
    color: """ + COLOR_TEXT + """;
}

QLabel#subtitleLabel {
    font-size: 13px;
    color: """ + COLOR_TEXT_SECONDARY + """;
    margin-top: 2px;
}

QLabel#cardTitle {
    font-size: 12px;
    color: """ + COLOR_TEXT_SECONDARY + """;
    font-weight: 500;
}

QLabel#cardValue {
    font-size: 30px;
    font-weight: 600;
    color: """ + COLOR_TEXT + """;
}

QLabel#cardSubValue {
    font-size: 12px;
    color: """ + COLOR_TEXT_MUTED + """;
}

QLabel#heroLabel {
    font-size: 12px;
    color: """ + COLOR_TEXT_SECONDARY + """;
    font-weight: 500;
}

QLabel#heroValue {
    font-size: 34px;
    font-weight: 700;
    color: """ + COLOR_TEXT + """;
    line-height: 1.1;
}

QLabel#heroSub {
    font-size: 13px;
    color: """ + COLOR_TEXT_MUTED + """;
}

/* Cards: white with subtle shadow and rounded corners. */
QFrame#card {
    background-color: """ + COLOR_CARD + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 12px;
}

QFrame#heroCard {
    background-color: """ + COLOR_CARD + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 14px;
}

QFrame#tipCard {
    border-radius: 8px;
    border: 1px solid transparent;
}

/* Status pills (small colored labels with optional leading dot). */
QLabel#pill {
    background-color: #DEECF9;
    color: """ + COLOR_ACCENT + """;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#pillSuccess {
    background-color: #DFF6DD;
    color: """ + COLOR_SUCCESS + """;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#pillWarning {
    background-color: #FFF4CE;
    color: #866800;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#pillDanger {
    background-color: #FDE7E9;
    color: """ + COLOR_DANGER + """;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QStatusBar {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT_MUTED + """;
    border-top: 1px solid """ + COLOR_BORDER + """;
}

QToolTip {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT + """;
    border: 1px solid """ + COLOR_BORDER + """;
    padding: 4px;
    border-radius: 4px;
}

QProgressBar {
    background-color: #EDEBE9;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: """ + COLOR_TEXT + """;
    font-size: 11px;
    min-height: 12px;
}

QProgressBar::chunk {
    background-color: """ + COLOR_ACCENT + """;
    border-radius: 5px;
}

QProgressBar#warning::chunk {
    background-color: """ + COLOR_WARNING + """;
}

QProgressBar#danger::chunk {
    background-color: """ + COLOR_DANGER + """;
}

/* Standard secondary button. */
QPushButton {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #F3F2F1;
    border-color: #C8C6C4;
}

QPushButton:pressed {
    background-color: #EDEBE9;
}

/* Primary (Microsoft blue) action button. */
QPushButton#primaryButton {
    background-color: """ + COLOR_ACCENT + """;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: """ + COLOR_ACCENT_HOVER + """;
}

QPushButton#primaryButton:pressed {
    background-color: """ + COLOR_ACCENT_PRESSED + """;
}

QPushButton#primaryButton:disabled {
    background-color: #C8C6C4;
    color: white;
}

/* Large hero action button (used in the new top hero section). */
QPushButton#heroAction {
    background-color: """ + COLOR_ACCENT + """;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 110px;
}

QPushButton#heroAction:hover {
    background-color: """ + COLOR_ACCENT_HOVER + """;
}

QPushButton#heroAction:pressed {
    background-color: """ + COLOR_ACCENT_PRESSED + """;
}

QPushButton#heroActionSecondary {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    min-width: 110px;
}

QPushButton#heroActionSecondary:hover {
    background-color: #F3F2F1;
    border-color: """ + COLOR_ACCENT + """;
    color: """ + COLOR_ACCENT + """;
}

QListWidget {
    background-color: """ + COLOR_CARD + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 8px;
    color: """ + COLOR_TEXT + """;
}

QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid """ + COLOR_BORDER + """;
}

QListWidget::item:last {
    border-bottom: none;
}

QListWidget::item:selected {
    background-color: #DEECF9;
    color: """ + COLOR_ACCENT + """;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 0;
}

QScrollBar::handle:vertical {
    background: #C8C6C4;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #A19F9D;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: none;
    height: 0;
}

QMenuBar {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT + """;
    border-bottom: 1px solid """ + COLOR_BORDER + """;
    padding: 2px;
}

QMenuBar::item {
    padding: 5px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #F3F2F1;
}

QMenu {
    background-color: """ + COLOR_CARD + """;
    color: """ + COLOR_TEXT + """;
    border: 1px solid """ + COLOR_BORDER + """;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 18px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #DEECF9;
    color: """ + COLOR_ACCENT + """;
}

QMenu::separator {
    height: 1px;
    background: """ + COLOR_BORDER + """;
    margin: 4px 6px;
}
"""
