#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QApplication 装配与深色主题。
"""

import sys

from PySide6 import QtWidgets

DARK_QSS = """
QMainWindow, QWidget {
    background: #0e131a; color: #e6edf3;
    font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    font-size: 13px;
}
QFrame#card { background: #161d27; border: 1px solid #232d3a; border-radius: 8px; }
QLabel#title { color: #8b98a8; font-size: 12px; }
QLabel#bigValue { font-size: 28px; font-weight: bold; }
QToolBar { background: #11161d; border-bottom: 1px solid #232d3a; spacing: 6px; padding: 6px; }
QPushButton {
    background: #1f2a38; border: 1px solid #2d3a4d; border-radius: 4px; padding: 5px 14px;
}
QPushButton:hover { background: #263548; }
QPushButton:checked { background: #0a5a8a; border-color: #29b6f6; }
QPushButton:disabled { color: #5b6672; }
QComboBox {
    background: #1f2a38; border: 1px solid #2d3a4d; border-radius: 4px; padding: 4px 8px;
}
QComboBox QAbstractItemView { background: #1f2a38; selection-background-color: #0a5a8a; }
QCheckBox { spacing: 4px; }
QTabWidget::pane { border: 1px solid #232d3a; top: -1px; }
QTabBar::tab {
    background: #11161d; padding: 6px 18px; border: 1px solid #232d3a;
    border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #1f2a38; color: #29b6f6; }
QTableWidget { background: #10161e; gridline-color: #1c2530; border: none; }
QTableWidget::item { padding: 2px; }
QHeaderView::section {
    background: #161d27; border: none; border-bottom: 1px solid #232d3a;
    padding: 4px; color: #8b98a8;
}
QProgressBar {
    background: #1f2a38; border: none; border-radius: 4px;
    text-align: center; color: #e6edf3; font-size: 11px;
}
QProgressBar::chunk { background: #29b6f6; border-radius: 4px; }
QMessageBox { background: #161d27; }
QToolTip { background: #1f2a38; color: #e6edf3; border: 1px solid #2d3a4d; }
"""


def create_app(argv=None) -> QtWidgets.QApplication:
    app = QtWidgets.QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("MH10 总线监控")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    return app
