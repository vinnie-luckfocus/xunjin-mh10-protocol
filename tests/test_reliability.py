#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MH10 Modbus 协议可靠性测试。

验证：
- 响应 CRC 错误注入下的读重试
- 无响应注入下的读重试
- 异常响应处理
- 连续失败后通信丢失判定
"""

import logging
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from mh10_protocol import (
    MH10_MB_REG_CONST,
    MH10_MB_FO_TOOLHEAD_STATE_RO,
    MH10_MODBUS_ONLINE_CONST,
    MH10_SLAVE_ID_FRONT_BOARD,
)

try:
    from pymodbus.client import ModbusSerialClient
    import serial
except ImportError as exc:  # pragma: no cover
    raise ImportError("请先安装依赖: pip install pymodbus pyserial") from exc


def _open_client(port: str, retries: int = 0):
    client = ModbusSerialClient(
        port=port,
        baudrate=115200,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=0.15,
        retries=retries,
    )
    assert client.connect(), f"无法连接到串口 {port}"
    return client


def _read_with_retry(client, slave_id, address, count, retries=5):
    for attempt in range(retries):
        try:
            rr = client.read_holding_registers(address, count=count, slave=slave_id)
            if rr is not None and not rr.isError():
                return rr
        except Exception as exc:
            logging.debug("read attempt %d failed: %s", attempt, exc)
        time.sleep(0.01 * (1 << attempt))
        # 连接可能被 pymodbus 标记为丢失，尝试重连
        if not client.is_socket_open():
            try:
                client.connect()
            except Exception:
                pass
    return None


class TestCrcErrors:
    @pytest.mark.parametrize(
        "virtual_board",
        [{"error_rate": 0.3, "silent_rate": 0.0}],
        indirect=True,
    )
    def test_read_with_crc_error_recovery(self, virtual_board):
        """在 30% CRC 错误率下，带重试的读取应最终成功。"""
        client = _open_client(virtual_board["slave_port"])
        success = 0
        for _ in range(20):
            rr = _read_with_retry(client, MH10_SLAVE_ID_FRONT_BOARD, MH10_MB_REG_CONST, 1)
            if rr and rr.registers[0] == MH10_MODBUS_ONLINE_CONST:
                success += 1
        assert success >= 18, f"CRC 错误下成功率过低: {success}/20"


class TestSilentErrors:
    @pytest.mark.parametrize(
        "virtual_board",
        [{"error_rate": 0.0, "silent_rate": 0.3}],
        indirect=True,
    )
    def test_read_with_silent_recovery(self, virtual_board):
        """在 30% 无响应率下，带重试的读取应最终成功。"""
        client = _open_client(virtual_board["slave_port"])
        success = 0
        for _ in range(20):
            rr = _read_with_retry(client, MH10_SLAVE_ID_FRONT_BOARD, MH10_MB_FO_TOOLHEAD_STATE_RO, 1)
            if rr:
                success += 1
        assert success >= 18, f"无响应下成功率过低: {success}/20"


class TestCommunicationLost:
    @pytest.mark.parametrize(
        "virtual_board",
        [{"error_rate": 0.0, "silent_rate": 1.0}],
        indirect=True,
    )
    def test_communication_lost_after_consecutive_failures(self, virtual_board):
        """模拟下位机完全断线，连续失败后应判定通信丢失。"""
        client = _open_client(virtual_board["slave_port"], retries=0)
        failures = 0
        for _ in range(12):
            try:
                rr = client.read_holding_registers(MH10_MB_REG_CONST, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
                if rr is None or rr.isError():
                    failures += 1
            except Exception:
                failures += 1
        assert failures >= 10, f"期望大量失败，实际失败次数: {failures}"


class TestExceptionResponse:
    def test_illegal_function_exception(self, virtual_board):
        """发送非法功能码，从机应返回异常响应。"""
        port = serial.Serial(
            virtual_board["slave_port"],
            115200,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=0.2,
        )

        def crc(data):
            crc_val = 0xFFFF
            for b in data:
                crc_val ^= b
                for _ in range(8):
                    if crc_val & 1:
                        crc_val = (crc_val >> 1) ^ 0xA001
                    else:
                        crc_val >>= 1
            return crc_val.to_bytes(2, 'little')

        frame = bytes([MH10_SLAVE_ID_FRONT_BOARD, 0x7F, 0x00, 0x00, 0x00, 0x01]) + crc(
            bytes([MH10_SLAVE_ID_FRONT_BOARD, 0x7F, 0x00, 0x00, 0x00, 0x01])
        )
        port.write(frame)
        time.sleep(0.01)
        resp = port.read(32)
        port.close()

        assert len(resp) >= 5
        assert resp[0] == MH10_SLAVE_ID_FRONT_BOARD
        assert (resp[1] & 0x80) != 0
        assert resp[2] == 0x01  # illegal function
