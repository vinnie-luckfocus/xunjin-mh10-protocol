#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 共享 fixture：创建虚拟串口对并启动虚拟前后板。
"""

import ctypes
import fcntl
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from mh10_protocol import MH10_MODBUS_BAUDRATE
from virtual_board import VirtualBoard


def create_pty_pair():
    """创建一对 pseudo-terminal 设备。

    macOS 上 os.ttyname 可能抛出 ERANGE，因此使用 TIOCPTYGNAME ioctl。
    返回 (master_fd, slave_name, slave_fd)。
    """
    if os.name != "posix":
        raise RuntimeError("当前平台不支持 PTY，请在 Linux/macOS 上运行测试")

    import pty

    master_fd, slave_fd = pty.openpty()

    # Linux 可直接用 ptsname；macOS 需用 ioctl 获取
    if sys.platform == "darwin":
        TIOCPTYGNAME = 0x40807453
        buf = ctypes.create_string_buffer(128)
        fcntl.ioctl(master_fd, TIOCPTYGNAME, buf)
        slave_name = buf.value.decode()
    else:
        slave_name = os.ttyname(slave_fd)

    return master_fd, slave_name, slave_fd


@pytest.fixture(scope="function")
def virtual_board(request):
    """提供已启动的虚拟板和对应的从端串口路径。

    可通过 `pytest.mark.parametrize` 注入 error_rate/silent_rate：
        @pytest.mark.parametrize("virtual_board", [dict(error_rate=0.3)], indirect=True)
    """
    params = getattr(request, "param", {})
    error_rate = params.get("error_rate", 0.0)
    silent_rate = params.get("silent_rate", 0.0)

    master_fd, slave_name, slave_fd = create_pty_pair()

    # 关闭 slave_fd，让测试客户端通过设备名重新打开 slave 端
    os.close(slave_fd)

    board = VirtualBoard(error_rate=error_rate, silent_rate=silent_rate)
    thread = threading.Thread(target=board.run_fd, args=(master_fd, MH10_MODBUS_BAUDRATE), daemon=True)
    thread.start()
    time.sleep(0.2)  # 等待从机启动

    yield {
        "board": board,
        "master_fd": master_fd,
        "slave_port": slave_name,
    }

    board.stop()
    os.close(master_fd)
