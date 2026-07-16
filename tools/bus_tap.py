#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地验证用三通总线桥。

创建两对伪终端 + 一个 TCP 监听端口：
  A ── 主控板（或 virtual_master.py）接入（pty）
  B ── 前后板（或 simulator/virtual_board.py）接入（pty）
  C ── 监控器接入：python -m monitor --port socket://127.0.0.1:7301

A<->B 双向转发，全部流量原样 tee 到所有已连接的 TCP 客户端，
模拟监控器在真实 RS-485 总线上的被动监听效果。

实现要点（macOS pty 的实测行为）：
- A/B 的 slave fd 在本进程中保持打开：pty 的 slave 端一旦全部关闭，
  master 端会进入 EOF/HUP 状态，之后重开 slave 时可能不可恢复；
- 监控端不用 pty：多 opener 下 pty 输入队列归属不稳定，且队列写满
  会拖死主链路；TCP 客户端写入失败直接丢弃，绝不影响 A<->B。
"""

import argparse
import ctypes
import fcntl
import os
import pty
import select
import socket
import sys

DEFAULT_TAP_PORT = 7301


def create_pty_pair():
    """返回 (master_fd, slave_fd, slave_name)。"""
    master_fd, slave_fd = pty.openpty()
    if sys.platform == "darwin":
        TIOCPTYGNAME = 0x40807453
        buf = ctypes.create_string_buffer(128)
        fcntl.ioctl(master_fd, TIOCPTYGNAME, buf)
        slave_name = buf.value.decode()
    else:
        slave_name = os.ttyname(slave_fd)
    return master_fd, slave_fd, slave_name


def main():
    parser = argparse.ArgumentParser(description="MH10 三通总线桥（本地验证用）")
    parser.add_argument("--tap-port", type=int, default=DEFAULT_TAP_PORT,
                        help="监控端 TCP 监听端口（默认 %(default)s）")
    args = parser.parse_args()

    a_master, a_slave, a_name = create_pty_pair()
    b_master, b_slave, b_name = create_pty_pair()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.tap_port))
    server.listen(4)
    server.setblocking(False)

    print("总线桥已启动，端口分配：")
    print(f"  A 主控板端 : {a_name}")
    print(f"  B 前后板端 : {b_name}")
    print(f"  C 监控端   : socket://127.0.0.1:{args.tap_port}")
    print("Ctrl+C 退出", flush=True)

    clients = []
    try:
        while True:
            ready, _, _ = select.select([a_master, b_master, server], [], [], 1.0)
            for fd in ready:
                if fd is server:
                    try:
                        conn, addr = server.accept()
                        conn.setblocking(False)
                        clients.append(conn)
                        print(f"监控端已接入: {addr}", flush=True)
                    except OSError:
                        pass
                    continue
                try:
                    data = os.read(fd, 512)
                except OSError:
                    continue
                if not data:
                    continue
                peer = b_master if fd == a_master else a_master
                try:
                    os.write(peer, data)
                except OSError:
                    pass
                for conn in clients[:]:
                    try:
                        conn.sendall(data)
                    except OSError:
                        clients.remove(conn)
                        try:
                            conn.close()
                        except OSError:
                            pass
    except KeyboardInterrupt:
        pass
    finally:
        for conn in clients:
            conn.close()
        server.close()
        for fd in (a_master, b_master, a_slave, b_slave):
            os.close(fd)


if __name__ == "__main__":
    main()
