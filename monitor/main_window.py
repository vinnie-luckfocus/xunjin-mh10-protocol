#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口：工具栏 + 设备卡片列 + 传感器面板 + 通信质量面板 + 日志区。
"""

import csv
import time
from typing import Optional

from PySide6 import QtCore, QtWidgets

from .analyzer import BusAnalyzer, MONITORED_SLAVES
from .serial_source import SerialSniffer, available_ports
from .widgets import (
    BackBoardPanel,
    DeviceCard,
    EventLogView,
    FrameLogView,
    FrontBoardPanel,
    QualityPanel,
)

REFRESH_MS = 100


class MainWindow(QtWidgets.QMainWindow):
    error_occurred = QtCore.Signal(str)

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MH10 Modbus 总线监控分析器")
        self.resize(1440, 900)

        self.analyzer = BusAnalyzer()
        self.sniffer: Optional[SerialSniffer] = None
        self._frames_seen = 0
        self._events_seen = 0
        self._default_baud = baudrate

        self._build_toolbar()
        self._build_body()

        self.error_occurred.connect(self._on_error)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        self._refresh_ports(select=port)
        if port:
            self._connect(port)

    # ------------------------------------------------------------------
    # 界面装配
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        bar = QtWidgets.QToolBar("主工具栏")
        bar.setMovable(False)
        self.addToolBar(bar)

        bar.addWidget(self._dim(" 端口 "))
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(200)
        self.port_combo.setEditable(True)  # 可手输 COM 口或 socket://host:port
        self.port_combo.setToolTip("串口设备（如 COM5、/dev/ttyUSB0）\n"
                                   "或 bus_tap 监控端地址（socket://127.0.0.1:7301）")
        bar.addWidget(self.port_combo)

        refresh_btn = QtWidgets.QPushButton("刷新")
        refresh_btn.clicked.connect(lambda: self._refresh_ports())
        bar.addWidget(refresh_btn)

        bar.addWidget(self._dim(" 波特率 "))
        self.baud_combo = QtWidgets.QComboBox()
        for baud in ("9600", "19200", "38400", "57600", "115200", "230400"):
            self.baud_combo.addItem(baud)
        self.baud_combo.setCurrentText(str(self._default_baud))
        bar.addWidget(self.baud_combo)

        self.connect_btn = QtWidgets.QPushButton("连接")
        self.connect_btn.setCheckable(True)
        self.connect_btn.toggled.connect(self._on_connect_toggled)
        bar.addWidget(self.connect_btn)

        self.status_label = QtWidgets.QLabel(" 未连接 ")
        self.status_label.setStyleSheet("color:#8b98a8; font-weight:bold;")
        bar.addWidget(self.status_label)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        bar.addWidget(spacer)

        self.duration_label = QtWidgets.QLabel("运行 00:00:00 ")
        self.duration_label.setStyleSheet("color:#8b98a8;")
        bar.addWidget(self.duration_label)

        reset_btn = QtWidgets.QPushButton("复位统计")
        reset_btn.clicked.connect(self._reset_stats)
        bar.addWidget(reset_btn)

        export_btn = QtWidgets.QPushButton("导出帧日志 CSV")
        export_btn.clicked.connect(self._export_csv)
        bar.addWidget(export_btn)

    @staticmethod
    def _dim(text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setObjectName("title")
        return lab

    def _build_body(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        main_row = QtWidgets.QHBoxLayout()
        root.addLayout(main_row, 3)

        # 左：设备卡片列
        devices_col = QtWidgets.QVBoxLayout()
        self.device_cards = {}
        for sid in MONITORED_SLAVES:
            card = DeviceCard(sid)
            self.device_cards[sid] = card
            devices_col.addWidget(card)
        devices_col.addStretch()
        main_row.addLayout(devices_col, 0)

        # 中：前/后板面板
        center_col = QtWidgets.QVBoxLayout()
        self.front_panel = FrontBoardPanel()
        self.back_panel = BackBoardPanel()
        center_col.addWidget(self.front_panel, 1)
        center_col.addWidget(self.back_panel, 1)
        main_row.addLayout(center_col, 1)

        # 右：通信质量
        self.quality_panel = QualityPanel()
        self.quality_panel.setMinimumWidth(240)
        main_row.addWidget(self.quality_panel, 0)

        # 下：日志区
        self.tabs = QtWidgets.QTabWidget()
        self.frame_log = FrameLogView()
        self.event_log = EventLogView()
        self.tabs.addTab(self.frame_log, "实时帧")
        self.tabs.addTab(self.event_log, "事件")
        root.addWidget(self.tabs, 2)

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _refresh_ports(self, select: Optional[str] = None) -> None:
        current = select or self.port_combo.currentText()
        self.port_combo.clear()
        ports = available_ports()
        if current and current not in ports:
            ports.append(current)  # 手动指定/虚拟端口，枚举不到也要可选
        self.port_combo.addItems(ports)
        if current:
            idx = self.port_combo.findText(current)
            self.port_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_connect_toggled(self, checked: bool) -> None:
        if checked and self.sniffer is None:
            self._connect(self.port_combo.currentText())
        elif not checked and self.sniffer is not None:
            self._disconnect()

    def _connect(self, port: str) -> None:
        if self.sniffer is not None:
            return  # 已连接（setChecked 会再次触发 toggled）
        if not port:
            self.error_occurred.emit("未选择串口")
            self.connect_btn.setChecked(False)
            return
        baud = int(self.baud_combo.currentText())
        self.analyzer.baudrate = baud
        self.sniffer = SerialSniffer(
            port, self.analyzer, baudrate=baud,
            on_error=lambda msg: self.error_occurred.emit(msg),
        )
        self.sniffer.start()
        self.connect_btn.setChecked(True)
        self.connect_btn.setText("断开")
        self.status_label.setText(f" 监听中 {port} @ {baud} ")
        self.status_label.setStyleSheet("color:#2ecc71; font-weight:bold;")
        self.port_combo.setEnabled(False)
        self.baud_combo.setEnabled(False)

    def _disconnect(self) -> None:
        if self.sniffer is not None:
            self.sniffer.stop()
            self.sniffer.join(timeout=1.0)
            self.sniffer = None
        self.connect_btn.setChecked(False)
        self.connect_btn.setText("连接")
        self.status_label.setText(" 未连接 ")
        self.status_label.setStyleSheet("color:#8b98a8; font-weight:bold;")
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f" 错误: {message} ")
        self.status_label.setStyleSheet("color:#e74c3c; font-weight:bold;")
        if self.sniffer is not None:
            self._disconnect()
        QtWidgets.QMessageBox.warning(self, "串口错误", message)

    # ------------------------------------------------------------------
    # 刷新与导出
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self.analyzer.poll()
        self.analyzer.record_sensor_history()
        snap = self.analyzer.snapshot()
        now = snap["now"]

        for sid, card in self.device_cards.items():
            card.update_stats(snap["devices"][sid], now)

        self.front_panel.update_stats(snap["front"], snap["history"]["speed"], now)
        self.back_panel.update_stats(
            snap["back"], snap["history"]["np_is"], snap["history"]["np_os"], now)
        self.quality_panel.update_stats(snap["totals"], snap["fps"], snap["bps"], snap["bus_load"])

        frames = snap["frame_log"]
        if len(frames) < self._frames_seen:  # 复位后重新填充
            self._frames_seen = 0
            self.frame_log.clear()
        self.frame_log.append(frames[self._frames_seen:])
        self._frames_seen = len(frames)

        events = snap["events"]
        if len(events) < self._events_seen:
            self._events_seen = 0
        self.event_log.append(events[self._events_seen:])
        self._events_seen = len(events)

        secs = int(snap["duration"])
        self.duration_label.setText(
            f"运行 {secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d} ")

    def _reset_stats(self) -> None:
        self.analyzer.reset()
        self._frames_seen = 0
        self._events_seen = 0
        self.frame_log.clear()

    def _export_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出帧日志", f"mh10_frames_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV 文件 (*.csv)")
        if not path:
            return
        snap = self.analyzer.snapshot()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "方向", "地址", "CRC正确", "解码", "原始帧(hex)"])
            for rec in snap["frame_log"]:
                writer.writerow([
                    f"{rec.ts:.3f}", rec.direction,
                    f"0x{rec.slave:02X}" if rec.slave >= 0 else "?",
                    "是" if rec.ok else "否", rec.summary, rec.hex,
                ])
        self.status_label.setText(f" 已导出 {len(snap['frame_log'])} 条到 {path} ")

    def closeEvent(self, event) -> None:
        self._disconnect()
        super().closeEvent(event)
