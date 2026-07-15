#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MH10 Modbus 协议功能测试。

验证：
- 前后板在线检测
- 读/写保持寄存器
- 系统版本/协议版本寄存器
- 复位魔数机制
- 前后板周期轮询
- 负压值缩放
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from mh10_protocol import (
    MH10_MB_REG_CONST,
    MH10_MB_REG_REBOOT,
    MH10_MB_REG_HW_VERSION,
    MH10_MB_REG_SW_VERSION,
    MH10_MB_REG_SVN_NUM,
    MH10_MB_REG_PROTOCOL_VERSION,
    MH10_MB_FO_TOOLHEAD_STATE_RO,
    MH10_MB_FO_TOOLHEAD_SPEED_RO,
    MH10_MB_FO_TOOLHEAD_COUNT_RO,
    MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW,
    MH10_MB_FO_TOOLHEAD_READY_TO_START_WO,
    MH10_MB_BK_VERSION_RO,
    MH10_MB_BK_NP_IS_RO,
    MH10_MB_BK_NP_OS_RO,
    MH10_MB_BK_TARGET_STATE_WO,
    MH10_MODBUS_ONLINE_CONST,
    MH10_MODBUS_REBOOT_MAGIC,
    MH10_PROTOCOL_VERSION,
    MH10_SLAVE_ID_BACK_BOARD,
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_TOOLHEAD_STATE_ONLINE_READY,
    MH10_BACKBOARD_STATE_OPEN,
    MH10_NP_SCALE_FACTOR,
    MH10_RUN_READY,
)

try:
    from pymodbus.client import ModbusSerialClient
except ImportError as exc:  # pragma: no cover
    raise ImportError("请先安装依赖: pip install pymodbus") from exc


def _open_client(port: str):
    client = ModbusSerialClient(
        port=port,
        baudrate=115200,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=0.2,
    )
    assert client.connect(), f"无法连接到串口 {port}"
    return client


class TestFrontBoardOnline:
    def test_online_const(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        rr = client.read_holding_registers(MH10_MB_REG_CONST, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr is not None, "前板在线检测无响应"
        assert rr.registers[0] == MH10_MODBUS_ONLINE_CONST, "在线常量不匹配"

    def test_version_registers(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        rr = client.read_holding_registers(MH10_MB_REG_HW_VERSION, count=5, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr is not None
        assert rr.registers[0] == 0x0100
        assert rr.registers[1] == 0x0110
        assert rr.registers[2] == 1234
        assert rr.registers[3] == MH10_PROTOCOL_VERSION

    def test_toolhead_state(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        rr = client.read_holding_registers(MH10_MB_FO_TOOLHEAD_STATE_RO, count=6, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr is not None
        assert rr.registers[0] == MH10_TOOLHEAD_STATE_ONLINE_READY
        assert rr.registers[2] == 0x01
        assert rr.registers[3] > 0
        assert rr.registers[4] >= 42

    def test_write_target_speed(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        wr = client.write_register(MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW, 1200, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert wr is not None
        rr = client.read_holding_registers(MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr.registers[0] == 1200

    def test_write_ready_to_start(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        wr = client.write_register(MH10_MB_FO_TOOLHEAD_READY_TO_START_WO, MH10_RUN_READY, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert wr is not None
        rr = client.read_holding_registers(MH10_MB_FO_TOOLHEAD_READY_TO_START_WO, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr.registers[0] == MH10_RUN_READY


class TestBackBoardOnline:
    def test_version_register_initialized(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        rr = client.read_holding_registers(MH10_MB_BK_VERSION_RO, count=1, slave=MH10_SLAVE_ID_BACK_BOARD)
        assert rr is not None
        assert rr.registers[0] == 0x0101, "后板版本寄存器未初始化"

    def test_pressure_registers(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        rr = client.read_holding_registers(MH10_MB_BK_NP_IS_RO, count=2, slave=MH10_SLAVE_ID_BACK_BOARD)
        assert rr is not None
        p1 = rr.registers[0] / -MH10_NP_SCALE_FACTOR
        p2 = rr.registers[1] / -MH10_NP_SCALE_FACTOR
        assert 40 <= p1 <= 60
        assert 40 <= p2 <= 60

    def test_write_target_state(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        wr = client.write_register(MH10_MB_BK_TARGET_STATE_WO, MH10_BACKBOARD_STATE_OPEN, slave=MH10_SLAVE_ID_BACK_BOARD)
        assert wr is not None
        rr = client.read_holding_registers(MH10_MB_BK_TARGET_STATE_WO, count=1, slave=MH10_SLAVE_ID_BACK_BOARD)
        assert rr.registers[0] == MH10_BACKBOARD_STATE_OPEN


class TestRebootMagic:
    def test_reboot_with_magic(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        # 先写入目标速度，确认动态寄存器有值
        client.write_register(MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW, 999, slave=MH10_SLAVE_ID_FRONT_BOARD)
        time.sleep(0.05)

        wr = client.write_register(MH10_MB_REG_REBOOT, MH10_MODBUS_REBOOT_MAGIC, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert wr is not None
        time.sleep(0.2)  # 等待复位

        rr = client.read_holding_registers(MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr.registers[0] == 0, "复位后动态寄存器应被清零"

        # 版本寄存器应保留
        rr = client.read_holding_registers(MH10_MB_REG_PROTOCOL_VERSION, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr.registers[0] == MH10_PROTOCOL_VERSION

    def test_reboot_with_invalid_value_ignored(self, virtual_board):
        client = _open_client(virtual_board["slave_port"])
        wr = client.write_register(MH10_MB_REG_REBOOT, 0x0001, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert wr is not None
        time.sleep(0.15)
        # 常量寄存器应仍然可读，说明没有复位
        rr = client.read_holding_registers(MH10_MB_REG_CONST, count=1, slave=MH10_SLAVE_ID_FRONT_BOARD)
        assert rr.registers[0] == MH10_MODBUS_ONLINE_CONST


class TestPollSequence:
    def test_front_and_back_poll(self, virtual_board):
        """模拟主控板周期轮询前后板。"""
        client = _open_client(virtual_board["slave_port"])

        for _ in range(5):
            front = client.read_holding_registers(0, count=16, slave=MH10_SLAVE_ID_FRONT_BOARD)
            assert front is not None
            assert front.registers[MH10_MB_FO_TOOLHEAD_STATE_RO] == MH10_TOOLHEAD_STATE_ONLINE_READY

            back = client.read_holding_registers(0, count=4, slave=MH10_SLAVE_ID_BACK_BOARD)
            assert back is not None
            assert back.registers[MH10_MB_BK_VERSION_RO] == 0x0101
            time.sleep(0.05)
