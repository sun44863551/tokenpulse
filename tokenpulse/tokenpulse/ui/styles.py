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

# Style template using placeholder substitution to avoid triple-quote collisions
_QSS_TEMPLATE = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    color: __TEXT__;
}

QMainWindow,
QWidget#root {
    background-color: __BG__;
}

QLabel#titleLabel {
    font-size: 24px;
    font-weight: 600;
    color: __TEXT__;
}

QLabel#subtitleLabel {
    font-size: 13px;
    color: __TEXT_SECONDARY__;
    margin-top: 2px;
}

QLabel#cardTitle {
    font-size: 12px;
    color: __TEXT_SECONDARY__;
    font-weight: 500;
}

QLabel#cardValue {
    font-size: 30px;
    font-weight: 600;
    color: __TEXT__;
}

QLabel#cardSubValue {
    font-size: 12px;
    color: __TEXT_MUTED__;
}

QLabel#heroLabel {
    font-size: 12px;
    color: __TEXT_SECONDARY__;
    font-weight: 500;
}

QLabel#heroValue {
    font-size: 34px;
    font-weight: 700;
    color: __TEXT__;
    line-height: 1.1;
}

QLabel#heroSub {
    font-size: 13px;
    color: __TEXT_MUTED__;
}

QFrame#card {
    background-color: __CARD__;
    border: 1px solid __BORDER__;
    border-radius: 10px;
}

QFrame#heroCard {
    background-color: __CARD__;
    border: 1px solid __BORDER__;
    border-radius: 12px;
}

QFrame#tipCard {
    border-radius: 8px;
    border: 1px solid transparent;
}

QLabel#pill {
    background-color: #DEECF9;
    color: __ACCENT__;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#pillSuccess {
    background-color: #DFF6DD;
    color: __SUCCESS__;
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
    color: __DANGER__;
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
}

QStatusBar {
    background-color: __CARD__;
    color: __TEXT_MUTED__;
    border-top: 1px solid __BORDER__;
}

QToolTip {
    background-color: __CARD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    padding: 4px;
    border-radius: 4px;
}

QProgressBar {
    background-color: #EDEBE9;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: __TEXT__;
    font-size: 11px;
    min-height: 12px;
}

QProgressBar::chunk {
    background-color: __ACCENT__;
    border-radius: 5px;
}

QProgressBar#warning::chunk {
    background-color: __WARNING__;
}

QProgressBar#danger::chunk {
    background-color: __DANGER__;
}

QPushButton {
    background-color: __CARD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    outline: none;
}

QPushButton:hover {
    background-color: #F3F2F1;
    border-color: #C8C6C4;
}

QPushButton:focus {
    border: 2px solid __ACCENT__;
    padding: 6px 13px;
}

QPushButton:pressed {
    background-color: #EDEBE9;
}

QPushButton#primaryButton {
    background-color: __ACCENT__;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: __ACCENT_HOVER__;
}

QPushButton#primaryButton:pressed {
    background-color: __ACCENT_PRESSED__;
}

QPushButton#primaryButton:disabled {
    background-color: #C8C6C4;
    color: white;
}

QPushButton#heroAction {
    background-color: __ACCENT__;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 110px;
}

QPushButton#heroAction:hover {
    background-color: __ACCENT_HOVER__;
}

QPushButton#heroAction:pressed {
    background-color: __ACCENT_PRESSED__;
}

QPushButton#heroActionSecondary {
    background-color: __CARD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    min-width: 110px;
}

QPushButton#heroActionSecondary:hover {
    background-color: #F3F2F1;
    border-color: __ACCENT__;
    color: __ACCENT__;
}

QListWidget {
    background-color: __CARD__;
    border: 1px solid __BORDER__;
    border-radius: 8px;
    color: __TEXT__;
}

QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid __BORDER__;
}

QListWidget::item:last {
    border-bottom: none;
}

QListWidget::item:selected {
    background-color: #DEECF9;
    color: __ACCENT__;
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
    background-color: __CARD__;
    color: __TEXT__;
    border-bottom: 1px solid __BORDER__;
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
    background-color: __CARD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 18px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #DEECF9;
    color: __ACCENT__;
}

QMenu::separator {
    height: 1px;
    background: __BORDER__;
    margin: 4px 6px;
}

/* === v0.dev-inspired stat card === */
QFrame#statCard {
    background-color: __CARD__;
    border: 1px solid __BORDER__;
    border-radius: 10px;
}

QFrame#statCard:hover {
    border-color: #C8C6C4;
}

QLabel#statValue {
    color: __TEXT__;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.2;
}

QLabel#statTitle {
    color: __TEXT_SECONDARY__;
    font-size: 12px;
    font-weight: 500;
}

QLabel#statSub {
    color: __TEXT_MUTED__;
    font-size: 11px;
}

QLabel#trendUp {
    color: __SUCCESS__;
    font-size: 11px;
    font-weight: 600;
}

QLabel#trendDown {
    color: __DANGER__;
    font-size: 11px;
    font-weight: 600;
}

QLabel#trendFlat {
    color: __TEXT_MUTED__;
    font-size: 11px;
    font-weight: 600;
}
"""

QSS = (
    _QSS_TEMPLATE
    .replace("__BG__", COLOR_BG)
    .replace("__CARD__", COLOR_CARD)
    .replace("__TEXT__", COLOR_TEXT)
    .replace("__TEXT_SECONDARY__", COLOR_TEXT_SECONDARY)
    .replace("__TEXT_MUTED__", COLOR_TEXT_MUTED)
    .replace("__BORDER__", COLOR_BORDER)
    .replace("__ACCENT__", COLOR_ACCENT)
    .replace("__ACCENT_HOVER__", COLOR_ACCENT_HOVER)
    .replace("__ACCENT_PRESSED__", COLOR_ACCENT_PRESSED)
    .replace("__SUCCESS__", COLOR_SUCCESS)
    .replace("__WARNING__", COLOR_WARNING)
    .replace("__DANGER__", COLOR_DANGER)
)
