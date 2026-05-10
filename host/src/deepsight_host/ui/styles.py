"""Qt stylesheet constants for DeepSight host UI."""

DARK_THEME = """
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: 13px;
}

QLabel {
    background: transparent;
}

QGroupBox {
    border: 1px solid #333355;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #8888cc;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QPushButton {
    background-color: #2a2a4a;
    border: 1px solid #444466;
    border-radius: 4px;
    padding: 6px 16px;
    color: #ccccdd;
}

QPushButton:hover {
    background-color: #3a3a5a;
    border-color: #666688;
}

QPushButton:pressed {
    background-color: #1a1a3a;
}

QPushButton#danger {
    background-color: #4a2020;
    border-color: #884444;
    color: #ff8888;
}

QPushButton#danger:hover {
    background-color: #5a3030;
}

QComboBox {
    background-color: #2a2a4a;
    border: 1px solid #444466;
    border-radius: 4px;
    padding: 4px 8px;
    color: #ccccdd;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #2a2a4a;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background: #6666aa;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #8888cc;
}

QTabWidget::pane {
    border: 1px solid #333355;
    background: #1a1a2e;
}

QTabBar::tab {
    background: #2a2a4a;
    border: 1px solid #333355;
    padding: 6px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #3a3a6a;
    border-bottom-color: #3a3a6a;
}

QLabel#status_green {
    color: #00cc66;
    font-weight: bold;
}

QLabel#status_yellow {
    color: #cccc00;
    font-weight: bold;
}

QLabel#status_red {
    color: #cc3333;
    font-weight: bold;
}

QLabel#value {
    color: #00cccc;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
}

QLabel#heading {
    color: #8888cc;
    font-size: 11px;
    text-transform: uppercase;
}

QSplitter {
    background: transparent;
}
"""
