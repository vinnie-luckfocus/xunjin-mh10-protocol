#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MH10 IAP/bootloader 协议测试（V1.2.0 新增）。

验证：
- python/mh10_protocol.py 与 include/mh10_protocol.h 的新增常量一致性
- 版本块 build/parse 辅助函数
- 基于虚拟板的端到端模拟升级：
  进入 BL → 擦除 → 分块烧写（含版本块）→ 校验 → 跳转 → app 上报新版本
- 负向用例：CRC 错误进入 ERROR；无有效版本块复位后停留在 BL
"""

import re
import struct
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))

import mh10_protocol as m  # noqa: E402

try:
    from pymodbus.client import ModbusSerialClient
except ImportError as exc:  # pragma: no cover
    raise ImportError("请先安装依赖: pip install pymodbus") from exc

HEADER_PATH = REPO_ROOT / "include" / "mh10_protocol.h"


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


def _read(client, slave, address, count=1):
    rr = client.read_holding_registers(address, count=count, slave=slave)
    assert rr is not None and not rr.isError(), f"读 0x{address:02X} 失败"
    return rr.registers


def _poll_status(client, slave, expected, timeout_s=2.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _read(client, slave, m.MH10_BL_REG_STATUS)[0]
        if status == expected:
            return status
        if status == m.MH10_BL_STATUS_ERROR:
            pytest.fail(f"bootloader 进入 ERROR 状态，错误码 "
                        f"{_read(client, slave, m.MH10_BL_REG_ERROR)[0]}")
        time.sleep(0.02)
    pytest.fail(f"等待状态 {expected} 超时")


# ----------------------------------------------------------------------
# 头文件一致性
# ----------------------------------------------------------------------

def _parse_header():
    """提取头文件中的 #define 常量与枚举值。"""
    text = HEADER_PATH.read_text(encoding="utf-8")
    values = {}
    for name, val in re.findall(
            r"#define\s+(MH10_\w+)\s+(0x[0-9A-Fa-f]+|\d+)U?L?\b", text):
        values[name] = int(val, 0)
    for name, val in re.findall(
            r"^\s*(MH10_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\s*,", text, re.MULTILINE):
        values[name] = int(val, 0)
    return values


class TestHeaderConsistency:
    """python/mh10_protocol.py 必须与 include/mh10_protocol.h 严格一致。"""

    HEADER_SYMBOLS = [
        "MH10_PROTOCOL_VERSION_MAJOR",
        "MH10_PROTOCOL_VERSION_MINOR",
        "MH10_PROTOCOL_VERSION_PATCH",
        "MH10_MODBUS_IAP_MAGIC",
        "MH10_MB_REG_IAP_ENTER",
        "MH10_MB_FO_ALARM_SUPPRESS_RW",
        "MH10_MB_FO_AUTO_RETRACT_RW",
        "MH10_MB_FO_FULL_POWER_SPEED_RW",
        "MH10_MB_FO_FULL_POWER_RISE_RW",
        "MH10_MB_FO_ACCEL_RISE_RW",
        "MH10_MB_FO_RAMP_STABLE_MS_RW",
        "MH10_MB_REG_COUNT",
        "MH10_MB_FO_CURVE_FWD_522_BASE",
        "MH10_MB_FO_CURVE_REV_522_BASE",
        "MH10_MB_FO_CURVE_FWD_556_BASE",
        "MH10_MB_FO_CURVE_REV_556_BASE",
        "MH10_MB_FO_CURVE_SUPPORT_RO",
        "MH10_MB_FO_CURVE_CUR_NUM",
        "MH10_MB_FO_CURVE_REG_NUM",
        "MH10_MB_FO_CURVE_SEG_RPM",
        "MH10_MB_FO_CURVE_SEG_NUM",
        "MH10_MB_FO_CURVE_CUR_MIN",
        "MH10_MB_FO_CURVE_CUR_MAX_522",
        "MH10_MB_FO_CURVE_CUR_MAX_556",
        "MH10_CURVE_SUPPORT_MAGIC",
        "MH10_MB_FO_DEBUG_SPEED_RW",
        "MH10_MB_FO_DEBUG_DIR_RW",
        "MH10_MB_FO_DEBUG_CMD_WO",
        "MH10_DEBUG_CMD_START",
        "MH10_DEBUG_CMD_STOP",
        "MH10_FLASH_BASE",
        "MH10_BL_BASE",
        "MH10_BL_SIZE",
        "MH10_APP_BASE",
        "MH10_APP_END",
        "MH10_VERSION_BLOCK_ADDR",
        "MH10_VERSION_BLOCK_SIZE",
        "MH10_VERSION_BLOCK_MAGIC",
        "MH10_DEVICE_ID_PAGE_ADDR",
        "MH10_BL_REG_MAGIC",
        "MH10_BL_REG_STATUS",
        "MH10_BL_REG_ERROR",
        "MH10_BL_REG_CMD",
        "MH10_BL_REG_LENGTH",
        "MH10_BL_REG_CRC16",
        "MH10_BL_REG_BLOCK",
        "MH10_BL_REG_PROGRESS",
        "MH10_BL_REG_DATA",
        "MH10_BL_MAGIC",
        "MH10_BL_BLOCK_SIZE",
        "MH10_BL_REG_DATA_COUNT",
        "MH10_BL_STATUS_IDLE",
        "MH10_BL_STATUS_ERASING",
        "MH10_BL_STATUS_READY",
        "MH10_BL_STATUS_DONE",
        "MH10_BL_STATUS_ERROR",
        "MH10_BL_ERROR_NONE",
        "MH10_BL_ERROR_BAD_STATE",
        "MH10_BL_ERROR_BAD_LEN",
        "MH10_BL_ERROR_FLASH",
        "MH10_BL_ERROR_BAD_CRC",
        "MH10_BL_CMD_ERASE",
        "MH10_BL_CMD_VERIFY",
        "MH10_BL_CMD_JUMP",
        "MH10_TOOLHEAD_CUT_MODE_FORWARD",
        "MH10_TOOLHEAD_CUT_MODE_REVERSE",
        "MH10_TOOLHEAD_CUT_MODE_RECIP",
    ]

    def test_constants_match_header(self):
        header = _parse_header()
        missing = [n for n in self.HEADER_SYMBOLS if n not in header]
        assert not missing, f"头文件中未找到: {missing}"
        for name in self.HEADER_SYMBOLS:
            py_val = getattr(m, name, None)
            assert py_val is not None, f"Python 绑定缺少 {name}"
            assert py_val == header[name], \
                f"{name}: Python 0x{py_val:X} != 头文件 0x{header[name]:X}"

    def test_derived_constants(self):
        header = _parse_header()
        assert m.MH10_PROTOCOL_VERSION == (
            (header["MH10_PROTOCOL_VERSION_MAJOR"] << 8)
            | (header["MH10_PROTOCOL_VERSION_MINOR"] << 4)
            | header["MH10_PROTOCOL_VERSION_PATCH"]
        ) == 0x01B0
        assert m.MH10_MB_REG_COUNT == 0x9C
        assert m.MH10_MB_FO_CURVE_SUPPORT_RO < m.MH10_MB_REG_COUNT
        assert m.MH10_MB_FO_DEBUG_CMD_WO < m.MH10_MB_REG_COUNT
        assert m.MH10_APP_MAX_SIZE == 55296
        assert m.MH10_APP_MAX_SIZE == m.MH10_DEVICE_ID_PAGE_ADDR - m.MH10_APP_BASE
        assert m.MH10_VERSION_BLOCK_IMAGE_OFFSET == \
            m.MH10_VERSION_BLOCK_ADDR - m.MH10_APP_BASE == 0xD7C0
        assert m.MH10_VERSION_BLOCK_IMAGE_OFFSET + m.MH10_VERSION_BLOCK_SIZE \
            == m.MH10_APP_MAX_SIZE

    def test_curve_region_layout(self):
        """V1.10.0 曲线区布局：四套 18 段曲线首尾相接，调试区紧随其后。"""
        assert m.MH10_MB_FO_CURVE_CUR_NUM == 18
        assert m.MH10_MB_FO_CURVE_REG_NUM == 18
        assert m.MH10_MB_FO_CURVE_SEG_RPM == 500
        assert m.MH10_MB_FO_CURVE_SEG_NUM == 18
        assert m.MH10_MB_FO_CURVE_SEG_RPM * m.MH10_MB_FO_CURVE_SEG_NUM == 9000
        assert m.MH10_MB_FO_CURVE_FWD_522_BASE == 0x50
        assert m.MH10_MB_FO_CURVE_REV_522_BASE == 0x62
        assert m.MH10_MB_FO_CURVE_FWD_556_BASE == 0x74
        assert m.MH10_MB_FO_CURVE_REV_556_BASE == 0x86
        assert m.MH10_MB_FO_CURVE_SUPPORT_RO == 0x98
        bases = (m.MH10_MB_FO_CURVE_FWD_522_BASE, m.MH10_MB_FO_CURVE_REV_522_BASE,
                 m.MH10_MB_FO_CURVE_FWD_556_BASE, m.MH10_MB_FO_CURVE_REV_556_BASE)
        for a, b in zip(bases, bases[1:]):
            assert b - a == m.MH10_MB_FO_CURVE_CUR_NUM
        assert bases[-1] + m.MH10_MB_FO_CURVE_CUR_NUM == m.MH10_MB_FO_CURVE_SUPPORT_RO
        assert m.MH10_MB_FO_CURVE_SUPPORT_RO + 1 == m.MH10_MB_FO_DEBUG_SPEED_RW
        assert m.MH10_MB_FO_DEBUG_SPEED_RW == 0x99
        assert m.MH10_MB_FO_DEBUG_CMD_WO == 0x9B
        # 曲线区/调试区全部落在寄存器数组内
        assert m.MH10_MB_FO_DEBUG_CMD_WO < m.MH10_MB_REG_COUNT

    def test_curve_defaults_match_header(self):
        """Python 默认电流列表必须与头文件 MH10_CURVE_DEF_CUR_* 数组宏一致。"""
        text = HEADER_PATH.read_text(encoding="utf-8")
        for name, py_list in (("MH10_CURVE_DEF_CUR_522", m.MH10_CURVE_DEFAULT_CUR_522),
                              ("MH10_CURVE_DEF_CUR_556", m.MH10_CURVE_DEFAULT_CUR_556)):
            mm = re.search(r"#define\s+" + name + r"\s*\{([^}]*)\}", text, re.DOTALL)
            assert mm, f"头文件中未找到 {name} 数组宏"
            header_arr = [int(v, 0) for v in re.findall(r"0x[0-9A-Fa-f]+|\d+", mm.group(1))]
            assert header_arr == py_list, f"{name}: 头文件 {header_arr} != Python {py_list}"
            assert len(py_list) == m.MH10_MB_FO_CURVE_CUR_NUM
            assert all(m.MH10_MB_FO_CURVE_CUR_MIN <= c <= 26 for c in py_list)

    def test_curve_seg_lookup(self):
        """V1.10.0 查表：seg = min(speed//500, 17)，段 i 覆盖 [500i, 500(i+1))。"""
        assert m.mh10_curve_seg_index(0) == 0
        assert m.mh10_curve_seg_index(499) == 0
        assert m.mh10_curve_seg_index(500) == 1
        assert m.mh10_curve_seg_index(1000) == 2
        assert m.mh10_curve_seg_index(8999) == 17
        assert m.mh10_curve_seg_index(9000) == 17
        assert m.mh10_curve_seg_index(100000) == 17
        for speed in range(0, 9000, 137):
            seg = m.mh10_curve_seg_index(speed)
            assert 500 * seg <= speed < 500 * (seg + 1)

    def test_version_block_helper(self):
        block = m.build_version_block(
            board_id=m.MH10_SLAVE_ID_FRONT_BOARD,
            sw_version=0x0120, svn_num=4321,
            git_hash_hi=0xABCD, git_hash_lo=0x1234,
        )
        assert len(block) == m.MH10_VERSION_BLOCK_SIZE
        parsed = m.parse_version_block(block)
        assert parsed["board_id"] == m.MH10_SLAVE_ID_FRONT_BOARD
        assert parsed["sw_version"] == 0x0120
        assert parsed["svn_num"] == 4321
        assert parsed["git_hash_hi"] == 0xABCD
        assert parsed["git_hash_lo"] == 0x1234
        assert parsed["struct_ver"] == 1
        with pytest.raises(ValueError):
            m.parse_version_block(b"\xFF" * m.MH10_VERSION_BLOCK_SIZE)
        with pytest.raises(ValueError):
            m.parse_version_block(block[:32])


# ----------------------------------------------------------------------
# 端到端模拟升级
# ----------------------------------------------------------------------

def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x0001 else crc >> 1
    return crc


def _make_image(with_version_block: bool = True,
                sw_version: int = 0x0121, svn_num: int = 4321,
                git_hi: int = 0xABCD, git_lo: int = 0x1234) -> bytes:
    """合成固件镜像：块 0 放伪代码，末尾放版本块，其余 0xFF。"""
    image = bytearray(b"\xFF" * m.MH10_APP_MAX_SIZE)
    image[0:16] = bytes(range(16))  # 伪代码段
    if with_version_block:
        block = m.build_version_block(m.MH10_SLAVE_ID_FRONT_BOARD,
                                      sw_version, svn_num, git_hi, git_lo)
        off = m.MH10_VERSION_BLOCK_IMAGE_OFFSET
        image[off:off + m.MH10_VERSION_BLOCK_SIZE] = block
    return bytes(image)


def _write_block(client, slave, image: bytes, block_no: int):
    """写一个 128B 数据块：先写 BLOCK 寄存器，再 FC16 写 64 个寄存器。"""
    chunk = image[block_no * m.MH10_BL_BLOCK_SIZE:
                  (block_no + 1) * m.MH10_BL_BLOCK_SIZE]
    assert len(chunk) == m.MH10_BL_BLOCK_SIZE
    # 寄存器值 = 小端字节对（与 box BoardUpdater 及真实 bootloader 一致）
    regs = list(struct.unpack(f"<{m.MH10_BL_REG_DATA_COUNT}H", chunk))
    wr = client.write_register(m.MH10_BL_REG_BLOCK, block_no, slave=slave)
    assert wr is not None and not wr.isError()
    wr = client.write_registers(m.MH10_BL_REG_DATA, regs, slave=slave)
    assert wr is not None and not wr.isError(), f"块 {block_no} 烧写被拒"


def _enter_bootloader(client, slave):
    """app 模式写 IAP 魔数并确认已进入 bootloader。"""
    wr = client.write_register(m.MH10_MB_REG_IAP_ENTER,
                               m.MH10_MODBUS_IAP_MAGIC, slave=slave)
    assert wr is not None and not wr.isError()
    time.sleep(0.3)  # 等待 100ms 复位延迟
    assert _read(client, slave, m.MH10_BL_REG_MAGIC)[0] == m.MH10_BL_MAGIC


def _erase_and_stream(client, slave, image: bytes, crc=None, blocks=(0, 431)):
    """擦除并烧写指定数据块（默认只写非 0xFF 的首块与含版本块的末块）。"""
    client.write_register(m.MH10_BL_REG_LENGTH, len(image), slave=slave)
    client.write_register(m.MH10_BL_REG_CRC16,
                          _crc16(image) if crc is None else crc, slave=slave)
    client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_ERASE, slave=slave)
    _poll_status(client, slave, m.MH10_BL_STATUS_READY)
    for b in blocks:
        _write_block(client, slave, image, b)
    return len(blocks)


class TestIapUpgrade:
    def test_end_to_end_upgrade(self, virtual_board):
        """完整升级流程：进入 BL → 擦除 → 烧写 → 校验 → 跳转 → 新版本 app。"""
        client = _open_client(virtual_board["slave_port"])
        slave = m.MH10_SLAVE_ID_FRONT_BOARD

        # 升级前：app 模式，0x00 不是 BL 标识
        assert _read(client, slave, 0x00)[0] != m.MH10_BL_MAGIC

        _enter_bootloader(client, slave)

        # bootloader 模式下的系统寄存器应答
        assert _read(client, slave, m.MH10_MB_REG_CONST)[0] == m.MH10_MODBUS_ONLINE_CONST
        assert _read(client, slave, m.MH10_MB_REG_SW_VERSION)[0] == 0x0000
        assert _read(client, slave, m.MH10_MB_REG_PROTOCOL_VERSION)[0] == m.MH10_PROTOCOL_VERSION

        image = _make_image()
        assert _erase_and_stream(client, slave, image) == 2
        # 与真实 bootloader 一致：PROGRESS = 最近成功块号 + 1
        assert _read(client, slave, m.MH10_BL_REG_PROGRESS)[0] == 432

        client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_VERIFY, slave=slave)
        _poll_status(client, slave, m.MH10_BL_STATUS_DONE)

        client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_JUMP, slave=slave)
        time.sleep(0.3)

        # 回到 app 模式，版本寄存器来自新版本块
        assert _read(client, slave, 0x00)[0] != m.MH10_BL_MAGIC
        assert _read(client, slave, m.MH10_MB_REG_SW_VERSION)[0] == 0x0121
        assert _read(client, slave, m.MH10_MB_REG_SVN_NUM)[0] == 4321
        assert _read(client, slave, m.MH10_MB_REG_GIT_HASH_HI)[0] == 0xABCD
        assert _read(client, slave, m.MH10_MB_REG_GIT_HASH_LO)[0] == 0x1234

    def test_verify_bad_crc_goes_error(self, virtual_board):
        """整图 CRC16 不匹配：VERIFY 后进入 ERROR/BAD_CRC。"""
        client = _open_client(virtual_board["slave_port"])
        slave = m.MH10_SLAVE_ID_FRONT_BOARD

        _enter_bootloader(client, slave)
        image = _make_image()
        _erase_and_stream(client, slave, image, crc=(_crc16(image) ^ 0xFFFF) & 0xFFFF)

        client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_VERIFY, slave=slave)
        time.sleep(0.1)
        assert _read(client, slave, m.MH10_BL_REG_STATUS)[0] == m.MH10_BL_STATUS_ERROR
        assert _read(client, slave, m.MH10_BL_REG_ERROR)[0] == m.MH10_BL_ERROR_BAD_CRC

    def test_jump_without_valid_app_stays_in_bootloader(self, virtual_board):
        """镜像无有效版本块：JUMP（复位）后仍停留在 bootloader 下载模式。"""
        client = _open_client(virtual_board["slave_port"])
        slave = m.MH10_SLAVE_ID_FRONT_BOARD

        _enter_bootloader(client, slave)
        image = _make_image(with_version_block=False)
        _erase_and_stream(client, slave, image, blocks=(0,))

        client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_VERIFY, slave=slave)
        _poll_status(client, slave, m.MH10_BL_STATUS_DONE)

        client.write_register(m.MH10_BL_REG_CMD, m.MH10_BL_CMD_JUMP, slave=slave)
        time.sleep(0.3)

        # app 无效 → 仍在 bootloader
        assert _read(client, slave, m.MH10_BL_REG_MAGIC)[0] == m.MH10_BL_MAGIC
        assert _read(client, slave, m.MH10_MB_REG_SW_VERSION)[0] == 0x0000

    def test_reboot_in_bootloader_without_image_stays(self, virtual_board):
        """bootloader 下 0x19=0x5A5A 复位：无镜像时仍回到 bootloader。"""
        client = _open_client(virtual_board["slave_port"])
        slave = m.MH10_SLAVE_ID_FRONT_BOARD

        _enter_bootloader(client, slave)
        wr = client.write_register(m.MH10_MB_REG_REBOOT,
                                   m.MH10_MODBUS_REBOOT_MAGIC, slave=slave)
        assert wr is not None and not wr.isError()
        time.sleep(0.3)
        assert _read(client, slave, m.MH10_BL_REG_MAGIC)[0] == m.MH10_BL_MAGIC
