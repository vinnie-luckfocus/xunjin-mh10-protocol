#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xunjin MH10 虚拟前后板 Modbus RTU 从机（手动帧处理版）。

本程序在一个串口上同时模拟前板（Slave ID=2）和后板（Slave ID=3），
支持功能码 0x03/0x06/0x10，并可通过参数注入 CRC 错误和无响应，
用于主控板协议的功能测试与可靠性测试。

依赖：pyserial
"""

import argparse
import logging
import random
import struct
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from mh10_protocol import (
    MH10_MB_REG_IAP_ENTER,
    MH10_MB_REG_CONST,
    MH10_MB_REG_REBOOT,
    MH10_MB_REG_HW_VERSION,
    MH10_MB_REG_SW_VERSION,
    MH10_MB_REG_SVN_NUM,
    MH10_MB_REG_PROTOCOL_VERSION,
    MH10_MB_REG_GIT_HASH_HI,
    MH10_MB_REG_GIT_HASH_LO,
    MH10_MB_FO_TOOLHEAD_STATE_RO,
    MH10_MB_FO_TOOLHEAD_INFO_RO,
    MH10_MB_FO_TOOLHEAD_SPEED_RO,
    MH10_MB_FO_TOOLHEAD_COUNT_RO,
    MH10_MB_FO_TOOLHEAD_POS_RO,
    MH10_MB_FO_PEDAL_INSERT_RO,
    MH10_MB_FO_PEDAL_SWITCH_RO,
    MH10_MB_FO_TOOLHEAD_INSERT_RO,
    MH10_MB_FO_TOOLHEAD_SWITCH_RO,
    MH10_MB_FO_TOOLHEAD_STATE_RW,
    MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW,
    MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW,
    MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO,
    MH10_MB_FO_TOOLHEAD_READY_TO_START_WO,
    MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO,
    MH10_MB_BK_VERSION_RO,
    MH10_MB_BK_NP_IS_RO,
    MH10_MB_BK_NP_OS_RO,
    MH10_MB_BK_TARGET_STATE_WO,
    MH10_MODBUS_ONLINE_CONST,
    MH10_MODBUS_REBOOT_MAGIC,
    MH10_MODBUS_IAP_MAGIC,
    MH10_PROTOCOL_VERSION,
    MH10_SLAVE_ID_BACK_BOARD,
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_TOOLHEAD_STATE_ONLINE_READY,
    MH10_BACKBOARD_STATE_CLOSED,
    MH10_MB_FC_READ_HOLDING_REGISTERS,
    MH10_MB_FC_WRITE_SINGLE_REGISTER,
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS,
    MH10_APP_MAX_SIZE,
    MH10_VERSION_BLOCK_IMAGE_OFFSET,
    MH10_VERSION_BLOCK_SIZE,
    MH10_BL_REG_MAGIC,
    MH10_BL_REG_STATUS,
    MH10_BL_REG_ERROR,
    MH10_BL_REG_CMD,
    MH10_BL_REG_LENGTH,
    MH10_BL_REG_CRC16,
    MH10_BL_REG_BLOCK,
    MH10_BL_REG_PROGRESS,
    MH10_BL_REG_DATA,
    MH10_BL_MAGIC,
    MH10_BL_BLOCK_SIZE,
    MH10_BL_REG_DATA_COUNT,
    MH10_BL_STATUS_IDLE,
    MH10_BL_STATUS_ERASING,
    MH10_BL_STATUS_READY,
    MH10_BL_STATUS_DONE,
    MH10_BL_STATUS_ERROR,
    MH10_BL_ERROR_NONE,
    MH10_BL_ERROR_BAD_STATE,
    MH10_BL_ERROR_BAD_LEN,
    MH10_BL_ERROR_BAD_CRC,
    MH10_BL_CMD_ERASE,
    MH10_BL_CMD_VERIFY,
    MH10_BL_CMD_JUMP,
    parse_version_block,
)

try:
    import serial
except ImportError as exc:  # pragma: no cover
    raise ImportError("请先安装依赖: pip install pyserial") from exc


def _crc16(data: bytes) -> int:
    """计算 Modbus RTU CRC-16。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _crc_bytes(data: bytes) -> bytes:
    crc = _crc16(data)
    return struct.pack("<H", crc)


class VirtualBoard:
    """虚拟工控板：维护两套寄存器并处理 Modbus RTU 帧。"""

    FRAME_TIMEOUT_S = 0.005  # 5ms，用于帧结束检测

    def __init__(self, error_rate: float = 0.0, silent_rate: float = 0.0):
        self.error_rate = max(0.0, min(1.0, error_rate))
        self.silent_rate = max(0.0, min(1.0, silent_rate))
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self.front = self._init_front_board()
        self.back = self._init_back_board()

        # IAP bootloader 模拟状态（按板）：模式标志、BL 寄存器、app 镜像缓冲
        self._bl_mode = {
            MH10_SLAVE_ID_FRONT_BOARD: False,
            MH10_SLAVE_ID_BACK_BOARD: False,
        }
        self._bl = {sid: self._init_bl_state() for sid in self._bl_mode}
        # app 镜像（模拟 flash app 区）：None 表示未烧写/已擦除无效
        self._image = {sid: None for sid in self._bl_mode}

    @staticmethod
    def _init_bl_state():
        return {
            "status": MH10_BL_STATUS_IDLE,
            "error": MH10_BL_ERROR_NONE,
            "length": 0,
            "crc16": 0,
            "block": 0,
            "progress": 0,
        }

    def _init_front_board(self):
        regs = [0] * 0x20
        regs[MH10_MB_REG_CONST] = MH10_MODBUS_ONLINE_CONST
        regs[MH10_MB_REG_HW_VERSION] = 0x0100
        regs[MH10_MB_REG_SW_VERSION] = 0x0110
        regs[MH10_MB_REG_SVN_NUM] = 1234
        regs[MH10_MB_REG_PROTOCOL_VERSION] = MH10_PROTOCOL_VERSION

        regs[MH10_MB_FO_TOOLHEAD_STATE_RO] = MH10_TOOLHEAD_STATE_ONLINE_READY
        regs[MH10_MB_FO_TOOLHEAD_INFO_RO] = 0x01
        regs[MH10_MB_FO_TOOLHEAD_SPEED_RO] = 500
        regs[MH10_MB_FO_TOOLHEAD_COUNT_RO] = 42
        regs[MH10_MB_FO_TOOLHEAD_POS_RO] = 50
        regs[MH10_MB_FO_PEDAL_INSERT_RO] = 1
        regs[MH10_MB_FO_PEDAL_SWITCH_RO] = 0
        regs[MH10_MB_FO_TOOLHEAD_INSERT_RO] = 1
        regs[MH10_MB_FO_TOOLHEAD_SWITCH_RO] = 0
        return regs

    def _init_back_board(self):
        regs = [0] * 0x20
        regs[MH10_MB_REG_CONST] = MH10_MODBUS_ONLINE_CONST
        regs[MH10_MB_REG_HW_VERSION] = 0x0100
        regs[MH10_MB_REG_SW_VERSION] = 0x0110
        regs[MH10_MB_REG_SVN_NUM] = 1234
        regs[MH10_MB_REG_PROTOCOL_VERSION] = MH10_PROTOCOL_VERSION
        regs[MH10_MB_BK_VERSION_RO] = 0x0101
        regs[MH10_MB_BK_NP_IS_RO] = 5000
        regs[MH10_MB_BK_NP_OS_RO] = 4800
        regs[MH10_MB_BK_TARGET_STATE_WO] = MH10_BACKBOARD_STATE_CLOSED
        return regs

    def _board_regs(self, slave_id: int):
        if slave_id == MH10_SLAVE_ID_FRONT_BOARD:
            return self.front
        if slave_id == MH10_SLAVE_ID_BACK_BOARD:
            return self.back
        return None

    def _simulate(self):
        """后台线程：周期性更新虚拟传感器数值。"""
        while not self._stop.is_set():
            with self._lock:
                self.front[MH10_MB_FO_TOOLHEAD_SPEED_RO] = max(
                    0, self.front[MH10_MB_FO_TOOLHEAD_SPEED_RO] + random.randint(-30, 30)
                )
                self.front[MH10_MB_FO_TOOLHEAD_COUNT_RO] += random.randint(0, 1)
                self.front[MH10_MB_FO_TOOLHEAD_POS_RO] = (
                    self.front[MH10_MB_FO_TOOLHEAD_POS_RO] + 3
                ) % 100
                self.back[MH10_MB_BK_NP_IS_RO] = max(
                    0, self.back[MH10_MB_BK_NP_IS_RO] + random.randint(-15, 15)
                )
                self.back[MH10_MB_BK_NP_OS_RO] = max(
                    0, self.back[MH10_MB_BK_NP_OS_RO] + random.randint(-15, 15)
                )
            time.sleep(0.2)

    def _handle_read(self, slave_id: int, pdu: bytes) -> bytes:
        if len(pdu) < 5:
            return self._exception(slave_id, pdu[0], 0x03)  # illegal data value
        address, count = struct.unpack(">HH", pdu[1:5])
        if self._bl_mode.get(slave_id):
            return self._bl_handle_read(slave_id, pdu, address, count)
        regs = self._board_regs(slave_id)
        if regs is None:
            return self._exception(slave_id, pdu[0], 0x02)  # illegal data address
        if address + count > len(regs):
            return self._exception(slave_id, pdu[0], 0x02)
        data = struct.pack(">B", count * 2)
        for i in range(count):
            data += struct.pack(">H", regs[address + i])
        return bytes([slave_id, pdu[0]]) + data

    def _handle_write_single(self, slave_id: int, pdu: bytes) -> bytes:
        if len(pdu) < 5:
            return self._exception(slave_id, pdu[0], 0x03)
        address, value = struct.unpack(">HH", pdu[1:5])
        if self._bl_mode.get(slave_id):
            return self._bl_handle_write_single(slave_id, pdu, address, value)
        regs = self._board_regs(slave_id)
        if regs is None or address >= len(regs):
            return self._exception(slave_id, pdu[0], 0x02)
        with self._lock:
            regs[address] = value
            if address == MH10_MB_REG_REBOOT and value == MH10_MODBUS_REBOOT_MAGIC:
                logging.warning("[%02X] 收到复位魔数，100ms 后复位", slave_id)
                threading.Timer(0.1, self._reset_board, args=(slave_id,)).start()
            elif address == MH10_MB_REG_REBOOT and value != 0:
                logging.warning("[%02X] 收到非魔数复位值 0x%04X，忽略", slave_id, value)
            elif address == MH10_MB_REG_IAP_ENTER and value == MH10_MODBUS_IAP_MAGIC:
                logging.warning("[%02X] 收到 IAP 魔数，100ms 后复位进入 bootloader", slave_id)
                threading.Timer(0.1, self._enter_bootloader, args=(slave_id,)).start()
            elif address == MH10_MB_REG_IAP_ENTER and value != 0:
                logging.warning("[%02X] 收到非魔数 IAP 值 0x%04X，忽略", slave_id, value)
        return bytes([slave_id, pdu[0]]) + struct.pack(">HH", address, value)

    def _handle_write_multiple(self, slave_id: int, pdu: bytes) -> bytes:
        if len(pdu) < 6:
            return self._exception(slave_id, pdu[0], 0x03)
        address, count, byte_count = struct.unpack(">HHB", pdu[1:6])
        expected = 6 + byte_count
        if len(pdu) < expected:
            return self._exception(slave_id, pdu[0], 0x03)
        if self._bl_mode.get(slave_id):
            return self._bl_handle_write_multiple(slave_id, pdu, address, count)
        regs = self._board_regs(slave_id)
        if regs is None or address + count > len(regs):
            return self._exception(slave_id, pdu[0], 0x02)
        with self._lock:
            for i in range(count):
                regs[address + i] = struct.unpack(">H", pdu[6 + 2 * i:8 + 2 * i])[0]
        return bytes([slave_id, pdu[0]]) + struct.pack(">HH", address, count)

    def _exception(self, slave_id: int, function: int, code: int) -> bytes:
        return bytes([slave_id, function | 0x80, code])

    def _reset_board(self, slave_id: int):
        """模拟下位机复位：保留版本信息，清空动态寄存器。"""
        regs = self._board_regs(slave_id)
        if regs is None:
            return
        with self._lock:
            for i in range(len(regs)):
                if i not in (
                    MH10_MB_REG_CONST,
                    MH10_MB_REG_HW_VERSION,
                    MH10_MB_REG_SW_VERSION,
                    MH10_MB_REG_SVN_NUM,
                    MH10_MB_REG_PROTOCOL_VERSION,
                    MH10_MB_REG_GIT_HASH_HI,
                    MH10_MB_REG_GIT_HASH_LO,
                    MH10_MB_BK_VERSION_RO,
                ):
                    regs[i] = 0
        logging.info("[%02X] 虚拟板已复位", slave_id)

    # ------------------------------------------------------------------
    # IAP bootloader 模拟
    # ------------------------------------------------------------------

    def _enter_bootloader(self, slave_id: int):
        """app 模式下收到 IAP 魔数：复位并由 bootloader 接管。"""
        with self._lock:
            self._bl_mode[slave_id] = True
            self._bl[slave_id] = self._init_bl_state()
        logging.info("[%02X] 已进入 bootloader 下载模式", slave_id)

    def _boot_board(self, slave_id: int):
        """模拟上电/跳转启动：app 版本块有效则启动 app，否则停留在 bootloader。"""
        with self._lock:
            image = self._image[slave_id]
            block = None
            if image is not None:
                off = MH10_VERSION_BLOCK_IMAGE_OFFSET
                try:
                    block = parse_version_block(bytes(image[off:off + MH10_VERSION_BLOCK_SIZE]))
                except ValueError:
                    block = None
            if block is None:
                self._bl_mode[slave_id] = True
                self._bl[slave_id] = self._init_bl_state()
                logging.warning("[%02X] app 版本块无效，停留在 bootloader 下载模式", slave_id)
                return
            self._bl_mode[slave_id] = False
            if slave_id == MH10_SLAVE_ID_FRONT_BOARD:
                self.front = self._init_front_board()
                regs = self.front
            else:
                self.back = self._init_back_board()
                regs = self.back
            # app 版本/ git 寄存器来自版本块
            regs[MH10_MB_REG_SW_VERSION] = block["sw_version"]
            regs[MH10_MB_REG_SVN_NUM] = block["svn_num"]
            regs[MH10_MB_REG_GIT_HASH_HI] = block["git_hash_hi"]
            regs[MH10_MB_REG_GIT_HASH_LO] = block["git_hash_lo"]
        logging.info("[%02X] 已启动 app（SW=0x%04X）", slave_id, block["sw_version"])

    def _bl_read_reg(self, slave_id: int, address: int) -> int:
        st = self._bl[slave_id]
        if address == MH10_BL_REG_MAGIC:
            return MH10_BL_MAGIC
        if address == MH10_BL_REG_STATUS:
            return st["status"]
        if address == MH10_BL_REG_ERROR:
            return st["error"]
        if address == MH10_BL_REG_LENGTH:
            return st["length"]
        if address == MH10_BL_REG_CRC16:
            return st["crc16"]
        if address == MH10_BL_REG_BLOCK:
            return st["block"]
        if address == MH10_BL_REG_PROGRESS:
            return st["progress"]
        # bootloader 模式下仍应答部分系统寄存器
        if address == MH10_MB_REG_CONST:
            return MH10_MODBUS_ONLINE_CONST
        if address == MH10_MB_REG_SW_VERSION:
            return 0x0000  # 触发主控板版本不一致判定
        if address == MH10_MB_REG_PROTOCOL_VERSION:
            return MH10_PROTOCOL_VERSION
        return 0

    def _bl_handle_read(self, slave_id: int, pdu: bytes, address: int, count: int) -> bytes:
        if address + count > MH10_BL_REG_DATA + MH10_BL_REG_DATA_COUNT:
            return self._exception(slave_id, pdu[0], 0x02)
        with self._lock:
            data = struct.pack(">B", count * 2)
            for i in range(count):
                data += struct.pack(">H", self._bl_read_reg(slave_id, address + i))
        return bytes([slave_id, pdu[0]]) + data

    def _bl_handle_write_single(self, slave_id: int, pdu: bytes, address: int, value: int) -> bytes:
        resp = bytes([slave_id, pdu[0]]) + struct.pack(">HH", address, value)
        with self._lock:
            st = self._bl[slave_id]
            if address == MH10_BL_REG_LENGTH:
                if value == 0 or value > MH10_APP_MAX_SIZE:
                    st["status"] = MH10_BL_STATUS_ERROR
                    st["error"] = MH10_BL_ERROR_BAD_LEN
                else:
                    st["length"] = value
            elif address == MH10_BL_REG_CRC16:
                st["crc16"] = value
            elif address == MH10_BL_REG_BLOCK:
                st["block"] = value
            elif address == MH10_BL_REG_CMD:
                self._bl_handle_cmd(slave_id, value)
            elif address == MH10_MB_REG_REBOOT and value == MH10_MODBUS_REBOOT_MAGIC:
                logging.warning("[%02X] bootloader 收到复位魔数，100ms 后重新启动", slave_id)
                threading.Timer(0.1, self._boot_board, args=(slave_id,)).start()
            elif address == MH10_MB_REG_IAP_ENTER and value == MH10_MODBUS_IAP_MAGIC:
                pass  # 已在 bootloader，忽略
        return resp

    def _bl_handle_cmd(self, slave_id: int, value: int):
        """处理 bootloader 命令（调用方须持锁）。"""
        st = self._bl[slave_id]
        if value == MH10_BL_CMD_ERASE:
            if st["length"] == 0:
                st["status"] = MH10_BL_STATUS_ERROR
                st["error"] = MH10_BL_ERROR_BAD_LEN
                return
            st["status"] = MH10_BL_STATUS_ERASING
            st["error"] = MH10_BL_ERROR_NONE
            logging.info("[%02X] 擦除 app 区（%d 字节）", slave_id, st["length"])
            threading.Timer(0.05, self._bl_finish_erase, args=(slave_id,)).start()
        elif value == MH10_BL_CMD_VERIFY:
            if st["status"] not in (MH10_BL_STATUS_READY, MH10_BL_STATUS_DONE):
                st["status"] = MH10_BL_STATUS_ERROR
                st["error"] = MH10_BL_ERROR_BAD_STATE
                return
            image = self._image[slave_id]
            actual = _crc16(bytes(image[0:st["length"]])) if image is not None else None
            if actual is not None and actual == st["crc16"]:
                st["status"] = MH10_BL_STATUS_DONE
                st["error"] = MH10_BL_ERROR_NONE
                logging.info("[%02X] 整图 CRC16 校验通过（0x%04X）", slave_id, actual)
            else:
                st["status"] = MH10_BL_STATUS_ERROR
                st["error"] = MH10_BL_ERROR_BAD_CRC
                logging.warning("[%02X] 整图 CRC16 校验失败：期望 0x%04X 实际 %s",
                                slave_id, st["crc16"],
                                f"0x{actual:04X}" if actual is not None else "无镜像")
        elif value == MH10_BL_CMD_JUMP:
            logging.info("[%02X] 收到 JUMP 命令，100ms 后启动", slave_id)
            threading.Timer(0.1, self._boot_board, args=(slave_id,)).start()
        else:
            logging.warning("[%02X] 未知 bootloader 命令 0x%04X，忽略", slave_id, value)

    def _bl_finish_erase(self, slave_id: int):
        with self._lock:
            st = self._bl[slave_id]
            # 擦除后 flash 为全 0xFF
            self._image[slave_id] = bytearray(b"\xFF" * MH10_APP_MAX_SIZE)
            st["progress"] = 0
            st["status"] = MH10_BL_STATUS_READY
        logging.info("[%02X] 擦除完成，等待数据", slave_id)

    def _bl_handle_write_multiple(self, slave_id: int, pdu: bytes, address: int, count: int) -> bytes:
        with self._lock:
            st = self._bl[slave_id]
            ok = (address == MH10_BL_REG_DATA
                  and count == MH10_BL_REG_DATA_COUNT
                  and st["status"] == MH10_BL_STATUS_READY)
            if ok:
                offset = st["block"] * MH10_BL_BLOCK_SIZE
                ok = (self._image[slave_id] is not None
                      and offset + MH10_BL_BLOCK_SIZE <= st["length"])
            if not ok:
                if st["status"] != MH10_BL_STATUS_READY:
                    st["status"] = MH10_BL_STATUS_ERROR
                    st["error"] = MH10_BL_ERROR_BAD_STATE
                else:
                    st["status"] = MH10_BL_STATUS_ERROR
                    st["error"] = MH10_BL_ERROR_BAD_LEN
                return self._exception(slave_id, pdu[0], 0x03)
            data = bytearray()
            for i in range(count):
                # 与真实 bootloader 一致（bl_main.c flash_write_halfword）：
                # 寄存器值按半字写入 flash，字节序为小端
                value = struct.unpack(">H", pdu[6 + 2 * i:8 + 2 * i])[0]
                data += struct.pack("<H", value)
            self._image[slave_id][offset:offset + MH10_BL_BLOCK_SIZE] = data
            st["progress"] = st["block"] + 1  # 与真实 bootloader 一致：已烧块号+1
        return bytes([slave_id, pdu[0]]) + struct.pack(">HH", address, count)

    def _process_frame(self, frame: bytes, write_fn):
        """处理一帧 Modbus RTU 请求并通过 write_fn 发送响应。"""
        if len(frame) < 4:
            return

        # 无响应注入
        if random.random() < self.silent_rate:
            logging.debug("注入无响应：%s", frame.hex())
            return

        slave_id, function = frame[0], frame[1]
        pdu = frame[1:-2]
        expected_crc = _crc_bytes(frame[:-2])
        if frame[-2:] != expected_crc:
            logging.warning("CRC 错误：期望 %s 实际 %s", expected_crc.hex(), frame[-2:].hex())
            return

        if slave_id not in (MH10_SLAVE_ID_FRONT_BOARD, MH10_SLAVE_ID_BACK_BOARD):
            return

        if function == MH10_MB_FC_READ_HOLDING_REGISTERS:
            resp = self._handle_read(slave_id, pdu)
        elif function == MH10_MB_FC_WRITE_SINGLE_REGISTER:
            resp = self._handle_write_single(slave_id, pdu)
        elif function == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            resp = self._handle_write_multiple(slave_id, pdu)
        else:
            resp = self._exception(slave_id, function, 0x01)  # illegal function

        # CRC 错误注入（仅对响应）
        if random.random() < self.error_rate:
            logging.debug("注入响应 CRC 错误")
            resp += b"\xDE\xAD"
        else:
            resp += _crc_bytes(resp)
        write_fn(resp)
        logging.debug("-> %s", resp.hex())

    def _run_loop(self, read_fn, write_fn, name: str):
        """通用运行循环。"""
        sim_thread = threading.Thread(target=self._simulate, daemon=True)
        sim_thread.start()
        logging.info("虚拟板已启动 on %s", name)

        buffer = bytearray()
        last_byte_time = time.time()

        while not self._stop.is_set():
            data = read_fn(256)
            if data:
                buffer.extend(data)
                last_byte_time = time.time()

            if buffer and (time.time() - last_byte_time) > self.FRAME_TIMEOUT_S:
                frame = bytes(buffer)
                buffer.clear()
                logging.debug("<- %s", frame.hex())
                self._process_frame(frame, write_fn)

    def run(self, port: str, baudrate: int = 115200):
        """启动虚拟从机主循环（基于 pyserial 设备名）。"""
        ser = serial.Serial(port, baudrate, bytesize=8, parity='N', stopbits=1, timeout=0.01)
        try:
            self._run_loop(ser.read, ser.write, f"{port}@{baudrate}")
        finally:
            ser.close()

    def run_fd(self, fd: int, baudrate: int = 115200):
        """启动虚拟从机主循环（基于已打开的文件描述符）。"""
        import os
        import select

        def read_fn(size):
            try:
                ready, _, _ = select.select([fd], [], [], 0.01)
                if ready:
                    return os.read(fd, size)
            except OSError:
                pass
            return b""

        def write_fn(data):
            try:
                os.write(fd, data)
            except OSError:
                pass

        self._run_loop(read_fn, write_fn, f"fd:{fd}@{baudrate}")

    def stop(self):
        self._stop.set()


def main():
    parser = argparse.ArgumentParser(description="MH10 虚拟前后板 Modbus RTU 从机")
    parser.add_argument("--port", required=True, help="串口设备路径")
    parser.add_argument("--baudrate", type=int, default=115200, help="波特率")
    parser.add_argument("--error-rate", type=float, default=0.0, help="响应 CRC 错误注入概率")
    parser.add_argument("--silent-rate", type=float, default=0.0, help="无响应注入概率")
    parser.add_argument("--verbose", action="store_true", help="输出 DEBUG 日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    board = VirtualBoard(error_rate=args.error_rate, silent_rate=args.silent_rate)
    try:
        board.run(args.port, args.baudrate)
    except KeyboardInterrupt:
        board.stop()
        logging.info("已停止")


if __name__ == "__main__":
    main()
