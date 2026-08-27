#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xunjin MH10 Modbus 协议 Python 绑定。

本文件是 `include/mh10_protocol.h` 的 Python 等价物，用于虚拟测试、
仿真器和协议文档示例。所有常量与 C 头文件保持严格一致。
"""

# 协议版本（V1.5.0：新增前板转速/驱动器异常检测屏蔽寄存器 0x12）
MH10_PROTOCOL_VERSION_MAJOR = 1
MH10_PROTOCOL_VERSION_MINOR = 5
MH10_PROTOCOL_VERSION_PATCH = 0
MH10_PROTOCOL_VERSION = (MH10_PROTOCOL_VERSION_MAJOR << 8) | \
                        (MH10_PROTOCOL_VERSION_MINOR << 4)  | \
                        MH10_PROTOCOL_VERSION_PATCH

# Modbus 物理层参数
MH10_MODBUS_BAUDRATE = 115200
MH10_MODBUS_DATA_BITS = 8
MH10_MODBUS_PARITY = 'N'
MH10_MODBUS_STOP_BITS = 1
MH10_MODBUS_DEFAULT_TIMEOUT_MS = 100
MH10_MODBUS_DEFAULT_RETRIES = 2

# 在线检测与复位魔数
MH10_MODBUS_ONLINE_CONST = 0xA0A0
MH10_MODBUS_REBOOT_MAGIC = 0x5A5A

# 进入 IAP bootloader 的安全魔数：
# 向 MH10_MB_REG_IAP_ENTER 写入该值，下位机复位后由 bootloader 接管串口
MH10_MODBUS_IAP_MAGIC = 0xB007

# 从机地址
MH10_SLAVE_ID_BROADCAST = 0x00
MH10_SLAVE_ID_MOTOR = 0x01
MH10_SLAVE_ID_FRONT_BOARD = 0x02
MH10_SLAVE_ID_BACK_BOARD = 0x03
MH10_SLAVE_ID_ATTACH_MOTOR = 0x04

# 功能码
MH10_MB_FC_READ_HOLDING_REGISTERS = 0x03
MH10_MB_FC_WRITE_SINGLE_REGISTER = 0x06
MH10_MB_FC_WRITE_MULTIPLE_REGISTERS = 0x10

# 系统公共寄存器
MH10_MB_REG_IAP_ENTER = 0x11
# 前板专用寄存器，占用系统区 0x11 与 0x18 之间的空闲地址（后板不实现）
# bit0=1 屏蔽转速/驱动器异常检测，上电默认 0=检测开启，易失不擦 flash
MH10_MB_FO_ALARM_SUPPRESS_RW = 0x12
MH10_MB_REG_CONST = 0x18
MH10_MB_REG_REBOOT = 0x19
MH10_MB_REG_HW_VERSION = 0x1A
MH10_MB_REG_SW_VERSION = 0x1B
MH10_MB_REG_SVN_NUM = 0x1C
MH10_MB_REG_PROTOCOL_VERSION = 0x1D
MH10_MB_REG_GIT_HASH_HI = 0x1E
MH10_MB_REG_GIT_HASH_LO = 0x1F

# 前板寄存器
MH10_MB_FO_TOOLHEAD_STATE_RO = 0x00
MH10_MB_FO_TOOLHEAD_EXCEPTION_RW = 0x01
MH10_MB_FO_TOOLHEAD_INFO_RO = 0x02
MH10_MB_FO_TOOLHEAD_SPEED_RO = 0x03
MH10_MB_FO_TOOLHEAD_COUNT_RO = 0x04
MH10_MB_FO_TOOLHEAD_POS_RO = 0x05
MH10_MB_FO_PEDAL_INSERT_RO = 0x06
MH10_MB_FO_PEDAL_SWITCH_RO = 0x07
MH10_MB_FO_TOOLHEAD_INSERT_RO = 0x08
MH10_MB_FO_TOOLHEAD_SWITCH_RO = 0x09
MH10_MB_FO_TOOLHEAD_STATE_RW = 0x0A
MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW = 0x0B
MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW = 0x0C
MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO = 0x0D
MH10_MB_FO_TOOLHEAD_READY_TO_START_WO = 0x0E
MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO = 0x0F
MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW = 0x10

# 前板切割模式（写 MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW，V1.4.0 定义）
# 语义变化：V1.3.0 固件中 0/1 表示"往复起始方向"，V1.4.0 起
# 0/1 为连续旋转方向，2 才是往复；box 与固件须同步升级，默认 0（正转）
MH10_TOOLHEAD_CUT_MODE_FORWARD = 0  # 正转（连续旋转，默认）
MH10_TOOLHEAD_CUT_MODE_REVERSE = 1  # 反转（连续旋转）
MH10_TOOLHEAD_CUT_MODE_RECIP = 2    # 往复（速度规划往复切割）

# 寄存器数组大小（V1.3.0 起 0x20 -> 0x50）
MH10_MB_REG_COUNT = 0x50

# 前板电机/往复运动调参寄存器区（V1.3.0，0x20~0x4F）
# 档位 i=0~7：jog rpm 300/600/900/1200/1500/2000/2500/3000，设定值=jog×3
MH10_MB_FO_TUNE_GEAR_SPEED_BASE = 0x20    # RW 档位全速段设定转速（8 个）
MH10_MB_FO_TUNE_GEAR_ZONE_BASE = 0x28     # RW 档位近顶减速区步数（8 个）
MH10_MB_FO_TUNE_GEAR_CURRENT_BASE = 0x30  # RW 档位峰值电流 0.1A（8 个）
MH10_MB_FO_TUNE_GEAR_ACCEL_BASE = 0x38    # RW 档位加速时间 ms/1000rpm（8 个）
MH10_MB_FO_TUNE_DECEL = 0x40              # RW 减速时间 ms/1000rpm（全局），默认 30
MH10_MB_FO_TUNE_START_SPEED = 0x41        # RW 起步段设定转速，默认 900
MH10_MB_FO_TUNE_START_STEPS = 0x42        # RW 起步段步数，默认 12
MH10_MB_FO_TUNE_SLOW_SPEED = 0x43         # RW 近顶爬行设定转速，默认 450
MH10_MB_FO_TUNE_REV_EXTRA = 0x44          # RW 沿采信后延迟换向步数，默认 4
MH10_MB_FO_TUNE_CRAWL_ADJ_MAX = 0x45      # RW 爬行自适应最大加步，默认 8
MH10_MB_FO_TUNE_ESTOP_MS = 0x46           # RW 急停减速时间 ms，默认 60
MH10_MB_FO_TUNE_CMD = 0x48                # WO 1=自动标定 2=手动运行启动 3=停止 4=恢复默认
MH10_MB_FO_TUNE_GEAR = 0x49               # RW 手动运行档位号 0~7
MH10_MB_FO_TUNE_STATUS = 0x4A             # RO 0 空闲 1 标定中 2 手动运行中 3 标定完成 4 失败
MH10_MB_FO_TUNE_CYCLE_COUNTS_RO = 0x4B    # RO 标定测得的往复周期计数
MH10_MB_FO_TUNE_ZONE_WIDTH_RO = 0x4C      # RO 标定测得的闭合区宽度（步）
MH10_MB_FO_TUNE_LAST_CYCLE_MS_RO = 0x4D   # RO 最近一个往复实测耗时 ms
MH10_MB_FO_TUNE_REV_STAT_RO = 0x4E        # RO 近 20 往复换向质量 bit0-4 E/bit5-9 F/bit10-14 O
MH10_MB_FO_TUNE_ERROR_RO = 0x4F           # RO 0 无 1 未插刀 2 堵转 3 超时 4 找不到闭合区

# 调参默认值（与固件定版一致）
MH10_TUNE_DEFAULT_GEAR_SPEED = [900, 1800, 2700, 3600, 4500, 6000, 7500, 9000]
MH10_TUNE_DEFAULT_GEAR_ZONE = [6, 6, 6, 10, 16, 26, 50, 68]
MH10_TUNE_DEFAULT_GEAR_CURRENT = [16, 18, 18, 18, 20, 20, 22, 22]
MH10_TUNE_DEFAULT_GEAR_ACCEL = [80] * 8

# 调参命令
MH10_TUNE_CMD_AUTO_CALIB = 1
MH10_TUNE_CMD_MANUAL_START = 2
MH10_TUNE_CMD_MANUAL_STOP = 3
MH10_TUNE_CMD_RESTORE_DEFAULT = 4

# 调参状态
MH10_TUNE_STATUS_IDLE = 0
MH10_TUNE_STATUS_CALIBRATING = 1
MH10_TUNE_STATUS_MANUAL_RUN = 2
MH10_TUNE_STATUS_CALIB_DONE = 3
MH10_TUNE_STATUS_FAILED = 4

# 调参失败原因
MH10_TUNE_ERROR_NONE = 0
MH10_TUNE_ERROR_NO_CUTTER = 1
MH10_TUNE_ERROR_STALL = 2
MH10_TUNE_ERROR_TIMEOUT = 3
MH10_TUNE_ERROR_NO_ZONE = 4

# 后板寄存器
MH10_MB_BK_VERSION_RO = 0x00
MH10_MB_BK_NP_IS_RO = 0x01
MH10_MB_BK_NP_OS_RO = 0x02
MH10_MB_BK_TARGET_STATE_WO = 0x03

# 前板状态枚举
MH10_TOOLHEAD_STATE_OFFLINE = 0
MH10_TOOLHEAD_STATE_PEDAL_ONLY = 1
MH10_TOOLHEAD_STATE_TOOLHEAD_ONLY = 2
MH10_TOOLHEAD_STATE_ONLINE_WAIT_SELFCHECK = 3
MH10_TOOLHEAD_STATE_SELF_CHECK = 4
MH10_TOOLHEAD_STATE_ONLINE_READY = 5
MH10_TOOLHEAD_STATE_WAITTING = 6
MH10_TOOLHEAD_STATE_RUNNING = 7
MH10_TOOLHEAD_STATE_ATTRACTING = 8
MH10_TOOLHEAD_STATE_EXCEPTION = 9

# 异常码
MH10_TOOLHEAD_EXP_NONE = 0
MH10_TOOLHEAD_EXP_READ_CARD = 1
MH10_TOOLHEAD_EXP_TOOLHEAD_OFFLINE = 2
MH10_TOOLHEAD_EXP_TOOLHEAD_SWITCH = 3
MH10_TOOLHEAD_EXP_PEDAL_OFFLINE = 4
MH10_TOOLHEAD_EXP_MOTOR_STOP = 5
MH10_TOOLHEAD_EXP_MOTOR_SPEED = 6
MH10_TOOLHEAD_EXP_MOTOR_DIR = 7

# 后板状态
MH10_BACKBOARD_STATE_CALIBRATION = 0
MH10_BACKBOARD_STATE_CLOSED = 1
MH10_BACKBOARD_STATE_OPEN = 2

# 自检/运行确认
MH10_SELFCHECK_NOT_READY = 0
MH10_SELFCHECK_READY = 1
MH10_SELFCHECK_SKIP = 2
MH10_RUN_NOT_READY = 0
MH10_RUN_READY = 1
MH10_ATTACH_READY = 2

# 缩放因子
MH10_NP_SCALE_FACTOR = -100.0
MH10_TOOLHEAD_SPEED_SCALE = 100

# Flash 布局（STM32F103C8，64 KB，页 1 KB）
MH10_FLASH_BASE = 0x08000000
MH10_BL_BASE = 0x08000000
MH10_BL_SIZE = 0x2000            # 8 KB
MH10_APP_BASE = 0x08002000
MH10_APP_END = 0x0800F7FF        # app 区最后一字节（含版本块）
MH10_APP_MAX_SIZE = 0x0800F800 - MH10_APP_BASE   # 55296 B
MH10_VERSION_BLOCK_ADDR = 0x0800F7C0             # app 区末尾 64 B
MH10_VERSION_BLOCK_SIZE = 64
MH10_VERSION_BLOCK_MAGIC = 0x4D483130            # ASCII "MH10"
MH10_DEVICE_ID_PAGE_ADDR = 0x0800F800            # 最后一页，IAP 不得擦除

# 版本块在 app 镜像内的偏移
MH10_VERSION_BLOCK_IMAGE_OFFSET = MH10_VERSION_BLOCK_ADDR - MH10_APP_BASE  # 0xD7C0

# bootloader 模式寄存器映射（仅在 bootloader 运行时有效，
# 与 app 模式寄存器是相互独立的命名空间）
MH10_BL_REG_MAGIC = 0x00     # RO bootloader 标识，固定 MH10_BL_MAGIC
MH10_BL_REG_STATUS = 0x01    # RO mh10_bl_status_t
MH10_BL_REG_ERROR = 0x02     # RO mh10_bl_error_t
MH10_BL_REG_CMD = 0x03       # WO mh10_bl_cmd_t
MH10_BL_REG_LENGTH = 0x04    # WO 固件总长度（字节），≤ MH10_APP_MAX_SIZE
MH10_BL_REG_CRC16 = 0x05     # WO 整图 CRC16（Modbus 多项式，初值 0xFFFF）
MH10_BL_REG_BLOCK = 0x06     # WO 数据窗口目标块号（128 B/块）
MH10_BL_REG_PROGRESS = 0x07  # RO 已成功烧写的块数
MH10_BL_REG_DATA = 0x10      # WO 数据窗口起始地址，64 个寄存器 = 128 B

MH10_BL_MAGIC = 0xB010       # bootloader 运行标识
MH10_BL_BLOCK_SIZE = 128     # 数据窗口字节数（64 个寄存器）
MH10_BL_REG_DATA_COUNT = 64  # 数据窗口寄存器数（0x10~0x4F）

# bootloader 状态
MH10_BL_STATUS_IDLE = 0      # 上电/等待命令
MH10_BL_STATUS_ERASING = 1   # 正在擦除 app 区
MH10_BL_STATUS_READY = 2     # 擦除完成，可接收数据
MH10_BL_STATUS_DONE = 3      # 校验通过，可跳转
MH10_BL_STATUS_ERROR = 4     # 出错，见 MH10_BL_REG_ERROR

# bootloader 错误码
MH10_BL_ERROR_NONE = 0
MH10_BL_ERROR_BAD_STATE = 1  # 当前状态不允许该命令
MH10_BL_ERROR_BAD_LEN = 2    # 长度越界
MH10_BL_ERROR_FLASH = 3      # 擦除/烧写失败
MH10_BL_ERROR_BAD_CRC = 4    # 整图 CRC16 校验失败

# bootloader 命令
MH10_BL_CMD_ERASE = 0x0001   # 按 0x04 长度擦除 app 区
MH10_BL_CMD_VERIFY = 0x0002  # 按 0x04/0x05 校验整图 CRC16
MH10_BL_CMD_JUMP = 0x5A5A    # 跳转 app（复用复位魔数）


import struct as _struct
from typing import Optional as _Optional

# mh10_version_block_t：magic u32 + board/sw/svn/git_hi/git_lo/struct_ver 6×u16
# + reserved 24×u16（填充 0xFF），小端，共 64 B
_VERSION_BLOCK_FMT = "<I6H24H"
_VERSION_BLOCK_STRUCT_VER = 1


def build_version_block(board_id: int, sw_version: int, svn_num: int,
                        git_hash_hi: int, git_hash_lo: int) -> bytes:
    """构造 64 字节 app 版本块（含 MH10_VERSION_BLOCK_MAGIC，reserved 填充 0xFF）。"""
    return _struct.pack(
        _VERSION_BLOCK_FMT,
        MH10_VERSION_BLOCK_MAGIC, board_id, sw_version, svn_num,
        git_hash_hi, git_hash_lo, _VERSION_BLOCK_STRUCT_VER,
        *([0xFFFF] * 24),
    )


def parse_version_block(data: bytes) -> dict:
    """解析 64 字节 app 版本块；magic 不匹配时抛出 ValueError。"""
    if len(data) != MH10_VERSION_BLOCK_SIZE:
        raise ValueError(f"版本块长度应为 {MH10_VERSION_BLOCK_SIZE} 字节，实际 {len(data)}")
    fields = _struct.unpack(_VERSION_BLOCK_FMT, data)
    if fields[0] != MH10_VERSION_BLOCK_MAGIC:
        raise ValueError(f"版本块 magic 不匹配：0x{fields[0]:08X}")
    return {
        "magic": fields[0],
        "board_id": fields[1],
        "sw_version": fields[2],
        "svn_num": fields[3],
        "git_hash_hi": fields[4],
        "git_hash_lo": fields[5],
        "struct_ver": fields[6],
    }


class MH10RegisterMap:
    """提供寄存器地址到名称的反向查找，便于测试日志输出。"""

    _SYSTEM = {
        MH10_MB_REG_IAP_ENTER: "MB_REG_IAP_ENTER",
        MH10_MB_REG_CONST: "MB_REG_CONST",
        MH10_MB_REG_REBOOT: "MB_REG_REBOOT",
        MH10_MB_REG_HW_VERSION: "MB_REG_HW_VERSION",
        MH10_MB_REG_SW_VERSION: "MB_REG_SW_VERSION",
        MH10_MB_REG_SVN_NUM: "MB_REG_SVN_NUM",
        MH10_MB_REG_PROTOCOL_VERSION: "MB_REG_PROTOCOL_VERSION",
        MH10_MB_REG_GIT_HASH_HI: "MB_REG_GIT_HASH_HI",
        MH10_MB_REG_GIT_HASH_LO: "MB_REG_GIT_HASH_LO",
    }

    _FRONT = {
        MH10_MB_FO_TOOLHEAD_STATE_RO: "MB_FO_TOOLHEAD_STATE_RO",
        MH10_MB_FO_TOOLHEAD_EXCEPTION_RW: "MB_FO_TOOLHEAD_EXCEPTION_RW",
        MH10_MB_FO_TOOLHEAD_INFO_RO: "MB_FO_TOOLHEAD_INFO_RO",
        MH10_MB_FO_TOOLHEAD_SPEED_RO: "MB_FO_TOOLHEAD_SPEED_RO",
        MH10_MB_FO_TOOLHEAD_COUNT_RO: "MB_FO_TOOLHEAD_COUNT_RO",
        MH10_MB_FO_TOOLHEAD_POS_RO: "MB_FO_TOOLHEAD_POS_RO",
        MH10_MB_FO_PEDAL_INSERT_RO: "MB_FO_PEDAL_INSERT_RO",
        MH10_MB_FO_PEDAL_SWITCH_RO: "MB_FO_PEDAL_SWITCH_RO",
        MH10_MB_FO_TOOLHEAD_INSERT_RO: "MB_FO_TOOLHEAD_INSERT_RO",
        MH10_MB_FO_TOOLHEAD_SWITCH_RO: "MB_FO_TOOLHEAD_SWITCH_RO",
        MH10_MB_FO_TOOLHEAD_STATE_RW: "MB_FO_TOOLHEAD_STATE_RW",
        MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW: "MB_FO_TOOLHEAD_TARGET_SPEED_RW",
        MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW: "MB_FO_TOOLHEAD_TARGET_DIR_RW",
        MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO: "MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO",
        MH10_MB_FO_TOOLHEAD_READY_TO_START_WO: "MB_FO_TOOLHEAD_READY_TO_START_WO",
        MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO: "MB_FO_TOOLHEAD_PEDAL_DELAY_WO",
        MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW: "MB_FO_TOOLHEAD_CYCLE_COUNTS_RW",
        MH10_MB_FO_TUNE_DECEL: "MB_FO_TUNE_DECEL",
        MH10_MB_FO_TUNE_START_SPEED: "MB_FO_TUNE_START_SPEED",
        MH10_MB_FO_TUNE_START_STEPS: "MB_FO_TUNE_START_STEPS",
        MH10_MB_FO_TUNE_SLOW_SPEED: "MB_FO_TUNE_SLOW_SPEED",
        MH10_MB_FO_TUNE_REV_EXTRA: "MB_FO_TUNE_REV_EXTRA",
        MH10_MB_FO_TUNE_CRAWL_ADJ_MAX: "MB_FO_TUNE_CRAWL_ADJ_MAX",
        MH10_MB_FO_TUNE_ESTOP_MS: "MB_FO_TUNE_ESTOP_MS",
        MH10_MB_FO_TUNE_CMD: "MB_FO_TUNE_CMD",
        MH10_MB_FO_TUNE_GEAR: "MB_FO_TUNE_GEAR",
        MH10_MB_FO_TUNE_STATUS: "MB_FO_TUNE_STATUS",
        MH10_MB_FO_TUNE_CYCLE_COUNTS_RO: "MB_FO_TUNE_CYCLE_COUNTS_RO",
        MH10_MB_FO_TUNE_ZONE_WIDTH_RO: "MB_FO_TUNE_ZONE_WIDTH_RO",
        MH10_MB_FO_TUNE_LAST_CYCLE_MS_RO: "MB_FO_TUNE_LAST_CYCLE_MS_RO",
        MH10_MB_FO_TUNE_REV_STAT_RO: "MB_FO_TUNE_REV_STAT_RO",
        MH10_MB_FO_TUNE_ERROR_RO: "MB_FO_TUNE_ERROR_RO",
    }

    _BACK = {
        MH10_MB_BK_VERSION_RO: "MB_BK_VERSION_RO",
        MH10_MB_BK_NP_IS_RO: "MB_BK_NP_IS_RO",
        MH10_MB_BK_NP_OS_RO: "MB_BK_NP_OS_RO",
        MH10_MB_BK_TARGET_STATE_WO: "MB_BK_TARGET_STATE_WO",
    }

    _BOOTLOADER = {
        MH10_BL_REG_MAGIC: "BL_REG_MAGIC",
        MH10_BL_REG_STATUS: "BL_REG_STATUS",
        MH10_BL_REG_ERROR: "BL_REG_ERROR",
        MH10_BL_REG_CMD: "BL_REG_CMD",
        MH10_BL_REG_LENGTH: "BL_REG_LENGTH",
        MH10_BL_REG_CRC16: "BL_REG_CRC16",
        MH10_BL_REG_BLOCK: "BL_REG_BLOCK",
        MH10_BL_REG_PROGRESS: "BL_REG_PROGRESS",
        MH10_BL_REG_DATA: "BL_REG_DATA",
    }

    @classmethod
    def _front_name(cls, address: int) -> _Optional[str]:
        """前板寄存器名：先查固定表，再按 V1.3.0 档位数组区间生成索引名。"""
        name = cls._FRONT.get(address)
        if name is not None:
            return name
        for base, label in (
            (MH10_MB_FO_TUNE_GEAR_SPEED_BASE, "MB_FO_TUNE_GEAR_SPEED"),
            (MH10_MB_FO_TUNE_GEAR_ZONE_BASE, "MB_FO_TUNE_GEAR_ZONE"),
            (MH10_MB_FO_TUNE_GEAR_CURRENT_BASE, "MB_FO_TUNE_GEAR_CURRENT"),
            (MH10_MB_FO_TUNE_GEAR_ACCEL_BASE, "MB_FO_TUNE_GEAR_ACCEL"),
        ):
            if base <= address < base + 8:
                return f"{label}[{address - base}]"
        return None

    @classmethod
    def name(cls, slave_id: int, address: int) -> str:
        if slave_id == MH10_SLAVE_ID_FRONT_BOARD:
            return cls._front_name(address) or cls._SYSTEM.get(address, f"REG_0x{address:02X}")
        if slave_id == MH10_SLAVE_ID_BACK_BOARD:
            return cls._BACK.get(address, cls._SYSTEM.get(address, f"REG_0x{address:02X}"))
        return cls._SYSTEM.get(address, f"REG_0x{address:02X}")

    @classmethod
    def bl_name(cls, address: int) -> str:
        """bootloader 模式寄存器名（与 app 模式相互独立的命名空间）。

        数据窗口 0x10~0x4F 与系统寄存器 0x18/0x19/0x1D 重叠，
        后者优先显示（bootloader 对它们读时返回系统值）。
        """
        if address in cls._SYSTEM:
            return cls._SYSTEM[address]
        if MH10_BL_REG_DATA <= address < MH10_BL_REG_DATA + MH10_BL_REG_DATA_COUNT:
            return f"BL_REG_DATA+{address - MH10_BL_REG_DATA}"
        return cls._BOOTLOADER.get(address, f"REG_0x{address:02X}")
