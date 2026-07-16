#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势图封装（pyqtgraph）：深色背景、相对时间轴、多曲线。
"""

from typing import Dict, List, Sequence, Tuple

import pyqtgraph as pg
from PySide6 import QtWidgets


class TrendChart(pg.PlotWidget):
    """滚动趋势图：x 轴为相对秒（0 = 现在，负值为历史）。"""

    def __init__(self, title: str, series: Dict[str, str], window_s: float = 120.0,
                 y_label: str = "", parent=None):
        super().__init__(parent)
        self.window_s = window_s
        self.setBackground("#10161e")
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setAntialiasing(True)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()

        plot_item = self.getPlotItem()
        plot_item.setTitle(title, color="#8b98a8", size="10pt")
        if y_label:
            plot_item.setLabel("left", y_label, color="#8b98a8")
        plot_item.getAxis("bottom").setPen(pg.mkPen("#232d3a"))
        plot_item.getAxis("left").setPen(pg.mkPen("#232d3a"))
        plot_item.getAxis("bottom").setTextPen(pg.mkPen("#8b98a8"))
        plot_item.getAxis("left").setTextPen(pg.mkPen("#8b98a8"))

        if len(series) > 1:
            legend = plot_item.addLegend(offset=(8, 8), brush=pg.mkBrush(22, 29, 39, 200),
                                         pen=pg.mkPen("#232d3a"), labelTextColor="#c9d4e0")
            legend.setLabelTextSize("9pt")

        self._curves: Dict[str, pg.PlotDataItem] = {}
        for name, color in series.items():
            curve = self.plot(pen=pg.mkPen(color, width=2), name=name)
            self._curves[name] = curve

    def update_series(self, now: float, data: Dict[str, Sequence[Tuple[float, float]]]) -> None:
        """data: {系列名: [(绝对时间戳, 值), ...]}，超出窗口的丢弃。"""
        self.setXRange(-self.window_s, 0, padding=0)
        for name, curve in self._curves.items():
            points = [(ts - now, v) for ts, v in data.get(name, ()) if now - ts <= self.window_s]
            if points:
                xs, ys = zip(*points)
                curve.setData(xs, ys)
            else:
                curve.setData([], [])
