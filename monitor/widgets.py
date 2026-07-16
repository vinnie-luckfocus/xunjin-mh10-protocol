#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控界面组件：设备卡片、前/后板传感器面板、通信质量面板、日志视图。
"""

import time
from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .analyzer import DEVICE_NAMES, TOOLHEAD_STATES
from .charts import TrendChart

GREEN = "#2ecc71"
RED = "#e74c3c"
ORANGE = "#f39c12"
CYAN = "#29b6f6"
GRAY = "#5b6672"
DIM = "#8b98a8"

STATE_COLORS = {
    "OFFLINE": GRAY,
    "PEDAL_ONLY": ORANGE,
    "TOOLHEAD_ONLY": ORANGE,
    "ONLINE_WAIT_SELFCHECK": CYAN,
    "SELF_CHECK": CYAN,
    "ONLINE_READY": GREEN,
    "WAITTING": CYAN,
    "RUNNING": GREEN,
    "ATTRACTING": GREEN,
    "EXCEPTION": RED,
}


def fmt_ts(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"


def fmt_age(ts: Optional[float], now: float) -> str:
    if ts is None:
        return "从未"
    age = now - ts
    if age < 1:
        return f"{age * 1000:.0f} ms 前"
    if age < 60:
        return f"{age:.1f} s 前"
    return f"{int(age // 60)} min 前"


def _dot(color: str) -> str:
    return f'<span style="color:{color}; font-size:16px;">●</span>'


class Indicator(QtWidgets.QWidget):
    """开关量指示灯：圆点 + 名称。"""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)
        self._dot_label = QtWidgets.QLabel("●")
        self._name_label = QtWidgets.QLabel(name)
        self._name_label.setStyleSheet(f"color:{DIM};")
        layout.addWidget(self._dot_label)
        layout.addWidget(self._name_label)

    def set_state(self, value: Optional[int], invert: bool = False) -> None:
        if value is None:
            color = GRAY
        else:
            on = bool(value) != invert
            color = GREEN if on else GRAY
        self._dot_label.setStyleSheet(f"color:{color};")


class DeviceCard(QtWidgets.QFrame):
    """单个从机设备的存活与通信质量卡片。"""

    def __init__(self, slave_id: int, parent=None):
        super().__init__(parent)
        self.slave_id = slave_id
        self.setObjectName("card")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        self.dot = QtWidgets.QLabel("●")
        self.dot.setStyleSheet(f"color:{GRAY}; font-size:18px;")
        self.title = QtWidgets.QLabel(f"{DEVICE_NAMES[slave_id]}")
        self.title.setStyleSheet("font-weight:bold; font-size:14px;")
        addr = QtWidgets.QLabel(f"0x{slave_id:02X}")
        addr.setStyleSheet(f"color:{DIM};")
        header.addWidget(self.dot)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(addr)
        layout.addLayout(header)

        self.status = QtWidgets.QLabel("未发现")
        self.status.setStyleSheet(f"color:{DIM}; font-weight:bold;")
        layout.addWidget(self.status)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        self._values: Dict[str, QtWidgets.QLabel] = {}
        rows = [
            ("success", "成功率"), ("latency", "平均延迟"),
            ("seen", "最近通信"), ("req_resp", "请求/响应"),
            ("timeout_retry", "超时/重试"), ("crc_exc", "CRC/异常"),
            ("versions", "版本"),
        ]
        for i, (key, label) in enumerate(rows):
            lab = QtWidgets.QLabel(label)
            lab.setObjectName("title")
            val = QtWidgets.QLabel("—")
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self._values[key] = val
        layout.addLayout(grid)
        layout.addStretch()

    def update_stats(self, d: dict, now: float) -> None:
        if d["alive"]:
            self.dot.setStyleSheet(f"color:{GREEN}; font-size:18px;")
            self.status.setText("在线")
            self.status.setStyleSheet(f"color:{GREEN}; font-weight:bold;")
        elif d["ever_seen"]:
            self.dot.setStyleSheet(f"color:{RED}; font-size:18px;")
            self.status.setText("离线")
            self.status.setStyleSheet(f"color:{RED}; font-weight:bold;")
        else:
            self.dot.setStyleSheet(f"color:{GRAY}; font-size:18px;")
            self.status.setText("未发现")
            self.status.setStyleSheet(f"color:{DIM}; font-weight:bold;")

        v = self._values
        rate = d["success_rate"]
        v["success"].setText("—" if rate is None else f"{rate:.1f} %")
        if rate is not None:
            color = GREEN if rate >= 99 else (ORANGE if rate >= 90 else RED)
            v["success"].setStyleSheet(f"color:{color};")

        if d["latency_avg"] is not None:
            v["latency"].setText(
                f"{d['latency_avg'] * 1000:.1f} ms"
                f"（{d['latency_min'] * 1000:.1f}~{d['latency_max'] * 1000:.1f}）")
        else:
            v["latency"].setText("—")

        v["seen"].setText(fmt_age(d["last_seen"], now))
        v["req_resp"].setText(f"{d['requests']} / {d['responses']}")
        v["timeout_retry"].setText(f"{d['timeouts']} / {d['retries']}")
        if d["timeouts"]:
            v["timeout_retry"].setStyleSheet(f"color:{ORANGE};")
        else:
            v["timeout_retry"].setStyleSheet("")
        v["crc_exc"].setText(f"{d['crc_errors']} / {d['exceptions']}")
        if d["crc_errors"] or d["exceptions"]:
            v["crc_exc"].setStyleSheet(f"color:{RED};")
        else:
            v["crc_exc"].setStyleSheet("")

        ver = d["versions"]
        if ver["sw"] is not None or ver["hw"] is not None:
            parts = []
            if ver["hw"] is not None:
                parts.append(f"HW {ver['hw'] >> 8}.{ver['hw'] & 0xFF}")
            if ver["sw"] is not None:
                parts.append(f"SW {ver['sw'] >> 8}.{ver['sw'] & 0xFF}")
            if ver["svn"] is not None:
                parts.append(f"SVN {ver['svn']}")
            if ver["protocol"] is not None:
                parts.append(f"PROTO {ver['protocol']:04X}")
            v["versions"].setText("  ".join(parts))
            v["versions"].setToolTip("硬件 / 软件 / SVN / 协议版本")
        else:
            v["versions"].setText("—")


class FrontBoardPanel(QtWidgets.QFrame):
    """前板（工具头）实时数据面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("前板 · 工具头")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        layout.addWidget(title)

        # 状态 + 异常横幅
        state_row = QtWidgets.QHBoxLayout()
        self.state_label = QtWidgets.QLabel("—")
        self.state_label.setAlignment(QtCore.Qt.AlignCenter)
        self.state_label.setMinimumHeight(44)
        self.state_label.setStyleSheet(self._state_style(GRAY))
        state_row.addWidget(self.state_label, 2)

        self.exception_label = QtWidgets.QLabel("")
        self.exception_label.setAlignment(QtCore.Qt.AlignCenter)
        self.exception_label.setMinimumHeight(44)
        self.exception_label.setStyleSheet(
            f"background:{RED}; color:white; font-weight:bold; font-size:15px;"
            "border-radius:6px; padding:4px 10px;")
        self.exception_label.hide()
        state_row.addWidget(self.exception_label, 1)
        layout.addLayout(state_row)

        # 数值区 + 速度趋势
        mid = QtWidgets.QHBoxLayout()
        values = QtWidgets.QGridLayout()
        values.setVerticalSpacing(4)

        values.addWidget(self._dim("实际速度"), 0, 0)
        self.speed = QtWidgets.QLabel("—")
        self.speed.setObjectName("bigValue")
        self.speed.setStyleSheet(f"color:{CYAN};")
        values.addWidget(self.speed, 1, 0)

        values.addWidget(self._dim("位置"), 2, 0)
        self.position = QtWidgets.QProgressBar()
        self.position.setRange(0, 100)
        self.position.setFixedHeight(18)
        values.addWidget(self.position, 3, 0)

        values.addWidget(self._dim("往复次数"), 4, 0)
        self.count = QtWidgets.QLabel("—")
        self.count.setStyleSheet("font-size:18px; font-weight:bold;")
        values.addWidget(self.count, 5, 0)

        values.addWidget(self._dim("工具头型号 / 目标速度 / 目标方向"), 6, 0)
        self.targets = QtWidgets.QLabel("—")
        values.addWidget(self.targets, 7, 0)
        values.setRowStretch(8, 1)
        mid.addLayout(values, 1)

        self.speed_chart = TrendChart("工具头速度 (RPM)", {"速度": CYAN})
        mid.addWidget(self.speed_chart, 2)
        layout.addLayout(mid)

        # 开关量指示
        indicators = QtWidgets.QHBoxLayout()
        self.ind_pedal_insert = Indicator("踏板插入")
        self.ind_pedal_switch = Indicator("踏板踩下")
        self.ind_tool_insert = Indicator("工具头插入")
        self.ind_tool_switch = Indicator("工具头开关")
        for ind in (self.ind_pedal_insert, self.ind_pedal_switch,
                    self.ind_tool_insert, self.ind_tool_switch):
            indicators.addWidget(ind)
        indicators.addStretch()
        layout.addLayout(indicators)

    @staticmethod
    def _dim(text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setObjectName("title")
        return lab

    @staticmethod
    def _state_style(color: str) -> str:
        return (f"background:#1a2432; color:{color}; border:1px solid {color};"
                "border-radius:6px; font-size:20px; font-weight:bold;")

    def update_stats(self, front: dict, history_speed, now: float) -> None:
        name = front["state_name"]
        color = STATE_COLORS.get(name, CYAN)
        self.state_label.setText(name)
        self.state_label.setStyleSheet(self._state_style(color))

        if front["exception"]:
            self.exception_label.setText(f"异常：{front['exception_name']}")
            self.exception_label.show()
        else:
            self.exception_label.hide()

        self.speed.setText("—" if front["speed_rpm"] is None else f"{front['speed_rpm']} RPM")
        if front["position"] is not None:
            self.position.setValue(max(0, min(100, front["position"])))
        self.count.setText("—" if front["count"] is None else str(front["count"]))

        def fmt(value, suffix=""):
            return "—" if value is None else f"{value}{suffix}"

        self.targets.setText(
            f"型号 {fmt(front['info'])}  ·  目标速度 {fmt(front['target_speed'])}"
            f"  ·  目标方向 {fmt(front['target_dir'])}  ·  目标状态 {fmt(front['target_state'])}")

        self.ind_pedal_insert.set_state(front["pedal_insert"])
        self.ind_pedal_switch.set_state(front["pedal_switch"])
        self.ind_tool_insert.set_state(front["toolhead_insert"])
        self.ind_tool_switch.set_state(front["toolhead_switch"])

        self.speed_chart.update_series(now, {"速度": history_speed})


class BackBoardPanel(QtWidgets.QFrame):
    """后板（负压）实时数据面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("后板 · 负压系统")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        layout.addWidget(title)

        values = QtWidgets.QHBoxLayout()
        col_is = QtWidgets.QVBoxLayout()
        lab = QtWidgets.QLabel("入口侧负压")
        lab.setObjectName("title")
        self.np_is = QtWidgets.QLabel("—")
        self.np_is.setObjectName("bigValue")
        self.np_is.setStyleSheet(f"color:{ORANGE};")
        col_is.addWidget(lab)
        col_is.addWidget(self.np_is)
        values.addLayout(col_is)

        col_os = QtWidgets.QVBoxLayout()
        lab = QtWidgets.QLabel("出口侧负压")
        lab.setObjectName("title")
        self.np_os = QtWidgets.QLabel("—")
        self.np_os.setObjectName("bigValue")
        self.np_os.setStyleSheet(f"color:{GREEN};")
        col_os.addWidget(lab)
        col_os.addWidget(self.np_os)
        values.addLayout(col_os)

        col_st = QtWidgets.QVBoxLayout()
        lab = QtWidgets.QLabel("负压目标状态 / 后板版本")
        lab.setObjectName("title")
        self.target = QtWidgets.QLabel("—")
        self.target.setStyleSheet("font-size:16px; font-weight:bold;")
        col_st.addWidget(lab)
        col_st.addWidget(self.target)
        values.addLayout(col_st)
        values.addStretch()
        layout.addLayout(values)

        self.np_chart = TrendChart("负压趋势 (kPa)", {"入口": ORANGE, "出口": GREEN})
        layout.addWidget(self.np_chart)

    def update_stats(self, back: dict, history_is, history_os, now: float) -> None:
        self.np_is.setText("—" if back["np_is_kpa"] is None else f"{back['np_is_kpa']:.2f} kPa")
        self.np_os.setText("—" if back["np_os_kpa"] is None else f"{back['np_os_kpa']:.2f} kPa")
        version = "—" if back["version"] is None else f"0x{back['version']:04X}"
        self.target.setText(f"{back['target_state_name']}  ·  {version}")
        self.np_chart.update_series(now, {"入口": history_is, "出口": history_os})


class QualityPanel(QtWidgets.QFrame):
    """总线通信质量统计面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("通信质量")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        layout.addWidget(title)

        lab = QtWidgets.QLabel("丢包率（未响应）")
        lab.setObjectName("title")
        layout.addWidget(lab)
        self.loss = QtWidgets.QLabel("—")
        self.loss.setObjectName("bigValue")
        layout.addWidget(self.loss)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(2)
        self._values: Dict[str, QtWidgets.QLabel] = {}
        rows = [
            ("requests", "总请求"), ("responses", "总响应"),
            ("timeouts", "未响应"), ("retries", "重试"),
            ("crc", "CRC 错误"), ("exceptions", "异常响应"),
            ("orphans", "孤立帧"), ("fps", "帧率"),
            ("bytes", "吞吐量"), ("frames", "总帧数"),
        ]
        for i, (key, label) in enumerate(rows):
            lab = QtWidgets.QLabel(label)
            lab.setObjectName("title")
            val = QtWidgets.QLabel("—")
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self._values[key] = val
        layout.addLayout(grid)

        lab = QtWidgets.QLabel("总线负载")
        lab.setObjectName("title")
        layout.addWidget(lab)
        self.bus_load = QtWidgets.QProgressBar()
        self.bus_load.setRange(0, 100)
        self.bus_load.setFixedHeight(16)
        layout.addWidget(self.bus_load)
        layout.addStretch()

    def update_stats(self, totals: dict, fps: float, bps: float, bus_load: float) -> None:
        loss = totals["loss_rate"]
        self.loss.setText(f"{loss:.2f} %")
        color = GREEN if loss == 0 else (ORANGE if loss < 5 else RED)
        self.loss.setStyleSheet(f"color:{color};")

        v = self._values
        v["requests"].setText(str(totals["requests"]))
        v["responses"].setText(str(totals["responses"]))
        v["timeouts"].setText(str(totals["timeouts"]))
        v["timeouts"].setStyleSheet(f"color:{ORANGE};" if totals["timeouts"] else "")
        v["retries"].setText(str(totals["retries"]))
        v["crc"].setText(str(totals["crc_errors"]))
        v["crc"].setStyleSheet(f"color:{RED};" if totals["crc_errors"] else "")
        v["exceptions"].setText(str(totals["exceptions"]))
        v["exceptions"].setStyleSheet(f"color:{RED};" if totals["exceptions"] else "")
        v["orphans"].setText(str(totals["orphans"]))
        v["fps"].setText(f"{fps:.1f} 帧/s")
        v["bytes"].setText(f"{bps:.0f} B/s")
        v["frames"].setText(str(totals["frames"]))
        self.bus_load.setValue(int(min(100, bus_load)))
        self.bus_load.setFormat(f"{bus_load:.1f} %")


class FrameLogView(QtWidgets.QWidget):
    """实时帧日志：过滤、暂停、清空。"""

    MAX_ROWS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self._dim("设备"))
        self.device_filter = QtWidgets.QComboBox()
        self.device_filter.addItem("全部", None)
        for sid, name in DEVICE_NAMES.items():
            self.device_filter.addItem(f"{name} (0x{sid:02X})", sid)
        controls.addWidget(self.device_filter)
        controls.addWidget(self._dim("方向"))
        self.dir_filter = QtWidgets.QComboBox()
        self.dir_filter.addItems(["全部", "REQ", "RESP", "ERR"])
        controls.addWidget(self.dir_filter)
        self.pause = QtWidgets.QCheckBox("暂停滚动")
        controls.addWidget(self.pause)
        clear = QtWidgets.QPushButton("清空")
        clear.clicked.connect(self.clear)
        controls.addWidget(clear)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["时间", "方向", "地址", "解码", "原始帧(hex)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(2, 50)
        self.table.setColumnWidth(3, 480)
        layout.addWidget(self.table)

    @staticmethod
    def _dim(text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setObjectName("title")
        return lab

    def append(self, records) -> None:
        if self.pause.isChecked():
            return
        dev_filter = self.device_filter.currentData()
        dir_filter = self.dir_filter.currentText()
        for rec in records:
            if dev_filter is not None and rec.slave != dev_filter:
                continue
            if dir_filter != "全部" and rec.direction != dir_filter:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(fmt_ts(rec.ts)))
            dir_item = QtWidgets.QTableWidgetItem(rec.direction)
            dir_item.setForeground(QtGui.QColor(
                {"REQ": CYAN, "RESP": GREEN}.get(rec.direction, RED)))
            self.table.setItem(row, 1, dir_item)
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(
                f"0x{rec.slave:02X}" if rec.slave >= 0 else "?"))
            summary_item = QtWidgets.QTableWidgetItem(rec.summary)
            if not rec.ok:
                summary_item.setForeground(QtGui.QColor(RED))
            self.table.setItem(row, 3, summary_item)
            hex_item = QtWidgets.QTableWidgetItem(rec.hex)
            hex_item.setForeground(QtGui.QColor(DIM))
            self.table.setItem(row, 4, hex_item)
        while self.table.rowCount() > self.MAX_ROWS:
            self.table.removeRow(0)
        self.table.scrollToBottom()

    def clear(self) -> None:
        self.table.setRowCount(0)


class EventLogView(QtWidgets.QWidget):
    """事件日志：设备上下线、状态迁移、异常、复位等。"""

    MAX_ROWS = 1000
    LEVEL_COLORS = {"info": GREEN, "warn": ORANGE, "error": RED}
    LEVEL_NAMES = {"info": "信息", "warn": "警告", "error": "错误"}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["时间", "级别", "事件"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 60)
        layout.addWidget(self.table)

    def append(self, events) -> None:
        for ev in events:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(fmt_ts(ev.ts)))
            level_item = QtWidgets.QTableWidgetItem(self.LEVEL_NAMES.get(ev.level, ev.level))
            level_item.setForeground(QtGui.QColor(self.LEVEL_COLORS.get(ev.level, DIM)))
            self.table.setItem(row, 1, level_item)
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(ev.message))
        while self.table.rowCount() > self.MAX_ROWS:
            self.table.removeRow(0)
        self.table.scrollToBottom()
