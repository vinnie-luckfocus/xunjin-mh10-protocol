#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口被动监听源：后台线程读取串口字节流，分帧后送入分析器。

只读不写，对总线完全透明（USB 转 RS485 工具与总线并联监听）。
"""

import threading
import time
from typing import Callable, Optional

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None

from .analyzer import BusAnalyzer
from .frames import FrameSegmenter


def available_ports() -> list:
    """列出系统可用串口，供 UI 下拉选择。"""
    if list_ports is None:
        return []
    return sorted(p.device for p in list_ports.comports())


class SerialSniffer(threading.Thread):
    """串口监听线程：读字节 → 分帧 → BusAnalyzer。"""

    def __init__(
        self,
        port: str,
        analyzer: BusAnalyzer,
        baudrate: int = 115200,
        gap_s: Optional[float] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True, name=f"sniffer-{port}")
        if serial is None:
            raise ImportError("请先安装依赖: pip install pyserial")
        self.port = port
        self.baudrate = baudrate
        self.analyzer = analyzer
        self.on_error = on_error
        self._stop_event = threading.Event()
        self._gap_s = gap_s

    def run(self) -> None:
        try:
            if "://" in self.port:
                # socket://host:port 等 URL 形式（用于 bus_tap 的 TCP 监控端）
                ser = serial.serial_for_url(self.port, timeout=0.005)
            else:
                ser = serial.Serial(
                    self.port, self.baudrate,
                    bytesize=8, parity='N', stopbits=1,
                    timeout=0.005,
                )
        except Exception as exc:  # 端口被占用/不存在/连接被拒等
            if self.on_error:
                self.on_error(f"无法打开 {self.port}: {exc}")
            return

        segmenter = FrameSegmenter(gap_s=self._gap_s)
        try:
            while not self._stop_event.is_set():
                data = ser.read(512)
                now = time.time()
                if data:
                    for frame in segmenter.feed(data, now):
                        self.analyzer.feed(frame)
                for frame in segmenter.poll(now):
                    self.analyzer.feed(frame)
                self.analyzer.poll(now)
        except Exception as exc:  # 热插拔掉线等
            if self.on_error and not self._stop_event.is_set():
                self.on_error(f"串口读取中断: {exc}")
        finally:
            try:
                ser.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
