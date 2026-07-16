#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地验证用虚拟主控板：按协议第 8 节节奏产生总线流量。

- 上电：读前/后板 0x18~0x1D 系统寄存器（在线检测）；
- 正常轮询：读前板 0x00~0x0F、读后板 0x00~0x03；
- 按概率下发写命令（目标速度、负压目标状态）；
- 超时 100ms，指数退避重试 3 次（5/10/20ms），与主控板可靠性设计一致。

依赖：pyserial
"""

import argparse
import logging
import random
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mh10_protocol import (  # noqa: E402
    MH10_MODBUS_DEFAULT_TIMEOUT_MS,
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_SLAVE_ID_BACK_BOARD,
)
from monitor.frames import append_crc, crc16  # noqa: E402

try:
    import serial
except ImportError as exc:  # pragma: no cover
    raise ImportError("请先安装依赖: pip install pyserial") from exc

RESP_TIMEOUT_S = MH10_MODBUS_DEFAULT_TIMEOUT_MS / 1000.0
BACKOFF_S = (0.005, 0.010, 0.020)


def read_request(slave: int, addr: int, count: int) -> bytes:
    return append_crc(bytes([slave, 0x03]) + struct.pack(">HH", addr, count))


def write_single(slave: int, addr: int, value: int) -> bytes:
    return append_crc(bytes([slave, 0x06]) + struct.pack(">HH", addr, value))


def read_response(ser: serial.Serial, timeout_s: float) -> bytes:
    """按 Modbus 帧结构读取一个完整响应，超时返回已收到部分。"""
    deadline = time.time() + timeout_s
    head = ser.read(3)
    if len(head) < 3:
        return head
    fc = head[1]
    if fc & 0x80:
        need = 2          # 异常响应：异常码 + CRC
    elif fc == 0x03:
        need = head[2] + 2  # 数据 + CRC
    else:
        need = 5          # 0x06/0x10：固定 8 字节帧
    ser.timeout = max(0.0, deadline - time.time())
    return head + ser.read(need)


def transact(ser: serial.Serial, req: bytes, label: str) -> bool:
    """发送请求并按指数退避重试（CRC 校验失败同样重试），返回是否成功。"""
    for attempt in range(len(BACKOFF_S)):
        ser.write(req)
        resp = read_response(ser, RESP_TIMEOUT_S)
        if resp and len(resp) >= 5:
            body, crc_bytes = resp[:-2], resp[-2:]
            if crc16(body) == int.from_bytes(crc_bytes, "little"):
                logging.debug("%s <- %s", label, resp.hex())
                return True
            logging.debug("%s 响应 CRC 错误，重试 %d", label, attempt + 1)
        else:
            logging.debug("%s 超时，重试 %d", label, attempt + 1)
        time.sleep(BACKOFF_S[attempt])
    logging.warning("%s 连续 %d 次未响应", label, len(BACKOFF_S))
    return False


def main():
    parser = argparse.ArgumentParser(description="MH10 虚拟主控板（本地验证用）")
    parser.add_argument("--port", required=True, help="串口设备路径（bus_tap 的 A 端）")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--interval", type=float, default=0.1, help="轮询周期（秒）")
    parser.add_argument("--write-prob", type=float, default=0.05, help="每周期下发写命令概率")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ser = serial.Serial(args.port, args.baudrate, timeout=RESP_TIMEOUT_S)
    logging.info("虚拟主控板已启动 on %s@%d", args.port, args.baudrate)

    # 上电在线检测
    for slave, name in ((MH10_SLAVE_ID_FRONT_BOARD, "前板"), (MH10_SLAVE_ID_BACK_BOARD, "后板")):
        ok = transact(ser, read_request(slave, 0x18, 6), f"{name} 系统寄存器")
        logging.info("%s 在线检测：%s", name, "OK" if ok else "失败")

    try:
        while True:
            cycle_start = time.time()
            transact(ser, read_request(MH10_SLAVE_ID_FRONT_BOARD, 0x00, 16), "前板 0x00-0x0F")
            transact(ser, read_request(MH10_SLAVE_ID_BACK_BOARD, 0x00, 4), "后板 0x00-0x03")

            if random.random() < args.write_prob:
                if random.random() < 0.5:
                    value = random.randint(200, 800)
                    transact(ser, write_single(MH10_SLAVE_ID_FRONT_BOARD, 0x0B, value),
                             f"写目标速度 {value}")
                else:
                    value = random.choice((0, 1, 2))
                    transact(ser, write_single(MH10_SLAVE_ID_BACK_BOARD, 0x03, value),
                             f"写负压目标状态 {value}")

            elapsed = time.time() - cycle_start
            time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        logging.info("已停止")


if __name__ == "__main__":
    main()
