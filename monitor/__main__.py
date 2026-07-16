#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MH10 Modbus 总线监控分析器入口。

用法：
    python -m monitor                        # 启动后手动选择串口并连接
    python -m monitor --port /dev/ttyUSB0    # 启动并自动连接
    python -m monitor --screenshot out.png --screenshot-delay 8
        # 无头验证：延时后保存界面截图并退出（配合 QT_QPA_PLATFORM=offscreen）
"""

import argparse
import sys

from .app import create_app
from .main_window import MainWindow


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="monitor", description="MH10 Modbus 总线监控分析器")
    parser.add_argument("--port", help="串口设备路径（如 COM5 或 /dev/ttyUSB0）")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--screenshot", help="保存界面截图到指定路径后退出（验证用）")
    parser.add_argument("--screenshot-delay", type=float, default=8.0, help="截图前等待秒数")
    parser.add_argument("--screenshot-tab", type=int, default=0, help="截图前切换到的底部标签页序号")
    args = parser.parse_args(argv)

    app = create_app()
    window = MainWindow(port=args.port, baudrate=args.baudrate)
    window.show()

    if args.screenshot:
        from PySide6 import QtCore

        def grab_and_quit():
            window.tabs.setCurrentIndex(args.screenshot_tab)
            pixmap = window.grab()
            pixmap.save(args.screenshot)
            snap = window.analyzer.snapshot()
            print(f"[screenshot] frames={snap['totals']['frames']} "
                  f"requests={snap['totals']['requests']} "
                  f"responses={snap['totals']['responses']} "
                  f"loss={snap['totals']['loss_rate']:.1f}%")
            app.quit()

        QtCore.QTimer.singleShot(int(args.screenshot_delay * 1000), grab_and_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
