#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MH10 总线流量分析核心（与 GUI 解耦，可独立测试）。

职责：
- 请求/响应配对（单主半双工状态机），计算响应延迟；
- 超时（未响应/丢包）、重试、CRC 错误、异常响应统计；
- 设备存活判定与上/下线事件；
- 各板寄存器镜像维护与传感器物理量解码（缩放 + 枚举名）；
- 总线负载、帧率等链路质量指标；
- 帧日志与事件日志（定长环形缓冲）。
"""

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from mh10_protocol import (
    MH10_MB_FC_READ_HOLDING_REGISTERS,
    MH10_MB_FC_WRITE_SINGLE_REGISTER,
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS,
    MH10_MB_REG_IAP_ENTER,
    MH10_MB_REG_CONST,
    MH10_MB_REG_REBOOT,
    MH10_MB_REG_HW_VERSION,
    MH10_MB_REG_SW_VERSION,
    MH10_MB_REG_SVN_NUM,
    MH10_MB_REG_PROTOCOL_VERSION,
    MH10_BL_REG_MAGIC,
    MH10_BL_REG_STATUS,
    MH10_BL_REG_ERROR,
    MH10_BL_REG_CMD,
    MH10_BL_REG_DATA,
    MH10_BL_MAGIC,
    MH10_BL_CMD_ERASE,
    MH10_BL_CMD_VERIFY,
    MH10_BL_CMD_JUMP,
    MH10_MB_FO_TOOLHEAD_STATE_RO,
    MH10_MB_FO_TOOLHEAD_EXCEPTION_RW,
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
    MH10_MB_BK_VERSION_RO,
    MH10_MB_BK_NP_IS_RO,
    MH10_MB_BK_NP_OS_RO,
    MH10_MB_BK_TARGET_STATE_WO,
    MH10_MODBUS_BAUDRATE,
    MH10_MODBUS_DEFAULT_TIMEOUT_MS,
    MH10_MODBUS_ONLINE_CONST,
    MH10_MODBUS_REBOOT_MAGIC,
    MH10_MODBUS_IAP_MAGIC,
    MH10_PROTOCOL_VERSION,
    MH10_SLAVE_ID_BROADCAST,
    MH10_SLAVE_ID_MOTOR,
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_SLAVE_ID_BACK_BOARD,
    MH10_SLAVE_ID_ATTACH_MOTOR,
    MH10_NP_SCALE_FACTOR,
    MH10_TOOLHEAD_SPEED_SCALE,
    MH10RegisterMap,
)

from .frames import Frame, EXCEPTION_CODES

DEVICE_NAMES = {
    MH10_SLAVE_ID_BROADCAST: "广播",
    MH10_SLAVE_ID_MOTOR: "电机驱动器 DM2C",
    MH10_SLAVE_ID_FRONT_BOARD: "前板",
    MH10_SLAVE_ID_BACK_BOARD: "后板",
    MH10_SLAVE_ID_ATTACH_MOTOR: "附加电机(预留)",
}

# 需要展示存活状态的从机（不含广播）
MONITORED_SLAVES = (
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_SLAVE_ID_BACK_BOARD,
    MH10_SLAVE_ID_MOTOR,
    MH10_SLAVE_ID_ATTACH_MOTOR,
)

FC_NAMES = {
    MH10_MB_FC_READ_HOLDING_REGISTERS: "读保持寄存器(0x03)",
    MH10_MB_FC_WRITE_SINGLE_REGISTER: "写单寄存器(0x06)",
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS: "写多寄存器(0x10)",
}

TOOLHEAD_STATES = {
    0: "OFFLINE",
    1: "PEDAL_ONLY",
    2: "TOOLHEAD_ONLY",
    3: "ONLINE_WAIT_SELFCHECK",
    4: "SELF_CHECK",
    5: "ONLINE_READY",
    6: "WAITTING",
    7: "RUNNING",
    8: "ATTRACTING",
    9: "EXCEPTION",
}

TOOLHEAD_EXCEPTIONS = {
    0: "NO_EXCEPTION",
    1: "EXP_READ_CARD",
    2: "EXP_TOOLHEAD_OFFLINE",
    3: "EXP_TOOLHEAD_SWITCH",
    4: "EXP_PEDAL_OFFLINE",
    5: "EXP_MOTOR_STOP",
    6: "EXP_MOTOR_SPEED",
    7: "EXP_MOTOR_DIR",
}

BACKBOARD_STATES = {
    0: "CALIBRATION",
    1: "CLOSED",
    2: "OPEN",
}

BL_STATUS_NAMES = {
    0: "IDLE",
    1: "ERASING",
    2: "READY",
    3: "DONE",
    4: "ERROR",
}

BL_ERROR_NAMES = {
    0: "NONE",
    1: "BAD_STATE",
    2: "BAD_LEN",
    3: "FLASH",
    4: "BAD_CRC",
}

BL_CMD_NAMES = {
    MH10_BL_CMD_ERASE: "ERASE",
    MH10_BL_CMD_VERIFY: "VERIFY",
    MH10_BL_CMD_JUMP: "JUMP",
}


@dataclass
class Event:
    ts: float
    level: str  # info / warn / error
    message: str


@dataclass
class FrameRecord:
    """帧日志条目：原始帧 + 解码摘要。"""

    ts: float
    direction: str  # REQ / RESP / ERR(无法解析或 CRC 错)
    slave: int
    summary: str
    hex: str
    ok: bool


@dataclass
class DeviceStats:
    slave: int
    name: str
    alive: bool = False
    ever_seen: bool = False
    last_seen: Optional[float] = None      # 最后一次合法响应时间
    last_request: Optional[float] = None
    requests: int = 0
    responses: int = 0
    timeouts: int = 0
    retries: int = 0
    exceptions: int = 0
    crc_errors: int = 0
    consecutive_failures: int = 0
    bootloader: bool = False                   # 是否处于 IAP bootloader 模式
    latency_sum: float = 0.0
    latency_count: int = 0
    latency_min: Optional[float] = None
    latency_max: Optional[float] = None
    registers: Dict[int, int] = field(default_factory=dict)

    @property
    def latency_avg(self) -> Optional[float]:
        if self.latency_count == 0:
            return None
        return self.latency_sum / self.latency_count

    @property
    def success_rate(self) -> Optional[float]:
        total = self.responses + self.timeouts
        if total == 0:
            return None
        return self.responses / total * 100.0

    def reg(self, address: int) -> Optional[int]:
        return self.registers.get(address)


@dataclass
class _PendingRequest:
    frame: Frame
    is_retry: bool


class BusAnalyzer:
    """总线分析器：feed() 消费帧，poll() 驱动超时/离线判定。"""

    def __init__(
        self,
        response_timeout_s: float = MH10_MODBUS_DEFAULT_TIMEOUT_MS / 1000.0,
        offline_after_s: float = 3.0,
        baudrate: int = MH10_MODBUS_BAUDRATE,
        history_len: int = 1800,
        log_len: int = 2000,
    ):
        self.response_timeout_s = response_timeout_s
        self.offline_after_s = offline_after_s
        self.baudrate = baudrate

        self.lock = threading.Lock()
        self.start_ts: Optional[float] = None
        self.last_frame_ts: Optional[float] = None

        self.devices: Dict[int, DeviceStats] = {
            sid: DeviceStats(slave=sid, name=DEVICE_NAMES[sid]) for sid in MONITORED_SLAVES
        }

        # 全局计数
        self.total_requests = 0
        self.total_responses = 0
        self.total_timeouts = 0
        self.total_retries = 0
        self.total_crc_errors = 0
        self.total_exceptions = 0
        self.total_orphan_responses = 0
        self.total_bytes = 0
        self.total_frames = 0

        self._pending: Optional[_PendingRequest] = None
        self._last_timed_out_key = None

        self.events: Deque[Event] = deque(maxlen=log_len)
        self.frame_log: Deque[FrameRecord] = deque(maxlen=log_len)

        # 趋势历史：(ts, value)
        self.hist_np_is: Deque[Tuple[float, float]] = deque(maxlen=history_len)
        self.hist_np_os: Deque[Tuple[float, float]] = deque(maxlen=history_len)
        self.hist_speed: Deque[Tuple[float, float]] = deque(maxlen=history_len)

        # 最近 5 秒流量窗口：(ts, bytes)，用于帧率/总线负载
        self._traffic: Deque[Tuple[float, int]] = deque()

    # ------------------------------------------------------------------
    # 帧摄入
    # ------------------------------------------------------------------

    def feed(self, frame: Frame) -> None:
        with self.lock:
            self._feed_locked(frame)

    def _feed_locked(self, frame: Frame) -> None:
        now = frame.ts_end
        if self.start_ts is None:
            self.start_ts = frame.ts_start
            self._event("info", "开始监听总线")
        self.last_frame_ts = now
        self.total_frames += 1
        self.total_bytes += len(frame.raw)
        self._traffic.append((now, len(frame.raw)))

        if not frame.crc_ok:
            self.total_crc_errors += 1
            dev = self.devices.get(frame.slave)
            if dev is not None:
                dev.crc_errors += 1
            self._log_frame(frame, "ERR", f"CRC 错误/残缺帧（{len(frame.raw)} 字节）")
            self._event("warn", f"收到 CRC 错误帧（地址 0x{frame.slave:02X}）")
            return

        if self._is_response_to_pending(frame):
            self._handle_response(frame)
            return

        # 新请求到达：若上一请求仍未闭合，判超时
        if self._pending is not None:
            self._close_timeout_locked(frame.ts_start)

        if frame.fc in (MH10_MB_FC_READ_HOLDING_REGISTERS,
                        MH10_MB_FC_WRITE_SINGLE_REGISTER,
                        MH10_MB_FC_WRITE_MULTIPLE_REGISTERS):
            # 无 pending 时按帧长区分请求与响应（监听中途接入总线时，
            # 可能先看到响应）：0x03 请求恒为 8 字节、响应为 5+2N（≠8）；
            # 0x10 响应恒为 8 字节、请求 ≥ 11；0x06 请求响应同构，按请求处理。
            looks_like_response = (
                (frame.fc == MH10_MB_FC_READ_HOLDING_REGISTERS and len(frame.raw) != 8) or
                (frame.fc == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS and len(frame.raw) == 8)
            )
            if looks_like_response:
                self.total_orphan_responses += 1
                self._log_frame(frame, "RESP", "孤立响应（接入总线前已存在的交易）")
            else:
                self._handle_request(frame)
        else:
            # 无法归类的合法帧（未知功能码）
            self.total_orphan_responses += 1
            self._log_frame(frame, "ERR", f"孤立帧，功能码 0x{frame.fc:02X}")

    # ------------------------------------------------------------------
    # 请求 / 响应处理
    # ------------------------------------------------------------------

    def _is_response_to_pending(self, frame: Frame) -> bool:
        p = self._pending
        if p is None:
            return False
        req = p.frame
        if frame.slave != req.slave:
            return False
        if frame.fc == (req.fc | 0x80):
            return True  # 异常响应
        if frame.fc != req.fc:
            return False
        # 按响应帧长约束区分“响应”与“同一请求的重试”：
        # 0x03 响应长度 5+2N 必为奇数，请求固定 8；0x10 响应 8，请求 ≥ 11；
        # 0x06 请求与响应（回显）同构，无法区分，按响应处理。
        if req.fc == MH10_MB_FC_READ_HOLDING_REGISTERS:
            byte_count = frame.payload[0] if frame.payload else -1
            return len(frame.raw) == 5 + byte_count
        if req.fc == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            return len(frame.raw) == 8
        return True

    def _handle_request(self, frame: Frame) -> None:
        self.total_requests += 1
        key = frame.request_key()
        is_retry = self._last_timed_out_key == key
        if is_retry:
            self.total_retries += 1
            dev = self.devices.get(frame.slave)
            if dev is not None:
                dev.retries += 1
        self._last_timed_out_key = None

        summary = self._decode_request(frame)
        self._log_frame(frame, "REQ", summary + ("（重试）" if is_retry else ""))

        if frame.fc in (MH10_MB_FC_WRITE_SINGLE_REGISTER, MH10_MB_FC_WRITE_MULTIPLE_REGISTERS):
            self._apply_write(frame)  # 写请求即更新镜像，反映主站意图

        if frame.slave == MH10_SLAVE_ID_BROADCAST:
            self._pending = None      # 广播无响应，不计超时
            return

        dev = self.devices.get(frame.slave)
        if dev is not None:
            dev.requests += 1
            dev.last_request = frame.ts_end
        self._pending = _PendingRequest(frame=frame, is_retry=is_retry)

    def _handle_response(self, frame: Frame) -> None:
        pending, self._pending = self._pending, None
        req = pending.frame
        latency = frame.ts_start - req.ts_end
        self.total_responses += 1

        dev = self.devices.get(frame.slave)
        if frame.is_exception:
            self.total_exceptions += 1
            code = frame.exception_code()
            code_name = EXCEPTION_CODES.get(code, f"未知异常码 0x{code:02X}" if code is not None else "?")
            if dev is not None:
                dev.exceptions += 1
                dev.consecutive_failures += 1
            self._log_frame(frame, "RESP", f"异常响应：{code_name}")
            self._event("error", f"{DEVICE_NAMES.get(frame.slave, hex(frame.slave))} 异常响应：{code_name}")
        else:
            if dev is not None:
                dev.responses += 1
                dev.consecutive_failures = 0
                dev.latency_sum += latency
                dev.latency_count += 1
                dev.latency_min = latency if dev.latency_min is None else min(dev.latency_min, latency)
                dev.latency_max = latency if dev.latency_max is None else max(dev.latency_max, latency)
                self._touch_alive(dev, frame.ts_end)
            self._apply_read_result(req, frame)
            self._log_frame(frame, "RESP", self._decode_response(req, frame))

    def _close_timeout_locked(self, now: float) -> None:
        p = self._pending
        if p is None:
            return
        self._pending = None
        req = p.frame
        self.total_timeouts += 1
        self._last_timed_out_key = req.request_key()
        dev = self.devices.get(req.slave)
        name = DEVICE_NAMES.get(req.slave, hex(req.slave))
        if dev is not None:
            dev.timeouts += 1
            dev.consecutive_failures += 1
        if not p.is_retry:
            self._event("warn", f"{name} 未响应 {FC_NAMES.get(req.fc, hex(req.fc))}（超时）")

    # ------------------------------------------------------------------
    # 周期驱动：超时与离线判定
    # ------------------------------------------------------------------

    def poll(self, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        with self.lock:
            if self._pending is not None and (now - self._pending.frame.ts_end) > self.response_timeout_s:
                self._close_timeout_locked(now)
            cutoff = now - self.offline_after_s
            for dev in self.devices.values():
                if dev.alive and dev.last_seen is not None and dev.last_seen < cutoff:
                    dev.alive = False
                    self._event("error", f"{dev.name} 离线（{self.offline_after_s:.0f}s 无响应）")
            # 流量窗口只保留 5s
            while self._traffic and self._traffic[0][0] < now - 5.0:
                self._traffic.popleft()

    # ------------------------------------------------------------------
    # 寄存器镜像与传感器解码
    # ------------------------------------------------------------------

    def _touch_alive(self, dev: DeviceStats, ts: float) -> None:
        dev.last_seen = ts
        if not dev.ever_seen:
            dev.ever_seen = True
            self._event("info", f"{dev.name} 上线")
        if not dev.alive:
            dev.alive = True
            self._event("info", f"{dev.name} 恢复通信")

    def _apply_write(self, req: Frame) -> None:
        """按写请求更新寄存器镜像（写响应到达前即可反映主站意图）。"""
        dev = self.devices.get(req.slave)
        if dev is None:
            return
        addr = req.req_address()
        if addr is None:
            return
        if req.fc == MH10_MB_FC_WRITE_SINGLE_REGISTER:
            value = req.req_write_value()
            if value is None:
                return
            old = dev.registers.get(addr)
            dev.registers[addr] = value
            self._after_register_change(dev, addr, old, value)
        elif req.fc == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            for i, value in enumerate(req.req_write_values()):
                old = dev.registers.get(addr + i)
                dev.registers[addr + i] = value
                self._after_register_change(dev, addr + i, old, value)

    def _apply_read_result(self, req: Frame, resp: Frame) -> None:
        if resp.fc != MH10_MB_FC_READ_HOLDING_REGISTERS:
            return
        dev = self.devices.get(resp.slave)
        if dev is None:
            return
        addr = req.req_address()
        if addr is None:
            return
        for i, value in enumerate(resp.resp_values()):
            old = dev.registers.get(addr + i)
            dev.registers[addr + i] = value
            self._after_register_change(dev, addr + i, old, value, resp.ts_end)

    def _after_register_change(self, dev: DeviceStats, addr: int, old: Optional[int],
                               value: int, ts: Optional[float] = None) -> None:
        if old == value:
            return
        sid = dev.slave
        if sid == MH10_SLAVE_ID_FRONT_BOARD and addr == MH10_MB_FO_TOOLHEAD_STATE_RO:
            self._event("info", f"工具头状态：{TOOLHEAD_STATES.get(old, old)} → {TOOLHEAD_STATES.get(value, value)}")
        elif sid == MH10_SLAVE_ID_FRONT_BOARD and addr == MH10_MB_FO_TOOLHEAD_EXCEPTION_RW:
            if value != 0:
                self._event("error", f"工具头异常：{TOOLHEAD_EXCEPTIONS.get(value, value)}")
            elif old:
                self._event("info", "工具头异常已清除")
        elif sid == MH10_SLAVE_ID_BACK_BOARD and addr == MH10_MB_BK_TARGET_STATE_WO:
            self._event("info", f"负压目标状态 → {BACKBOARD_STATES.get(value, value)}")
        elif addr == MH10_MB_REG_REBOOT and value == MH10_MODBUS_REBOOT_MAGIC:
            self._event("error", f"检测到下发给{dev.name}的复位魔数 0x5A5A")
        elif addr == MH10_MB_REG_IAP_ENTER and value == MH10_MODBUS_IAP_MAGIC:
            dev.bootloader = True
            self._event("error", f"检测到下发给{dev.name}的 IAP 魔数 0xB007（复位进入 bootloader）")
        elif dev.bootloader and addr == MH10_BL_REG_CMD:
            cmd = BL_CMD_NAMES.get(value, f"未知命令 0x{value:04X}")
            self._event("info", f"{dev.name} bootloader 命令：{cmd}")
            if value == MH10_BL_CMD_JUMP:
                dev.bootloader = False  # 主站意图跳转 app（若 app 无效板子会自行留在 BL）
        elif dev.bootloader and addr == MH10_BL_REG_ERROR and value != 0:
            self._event("error", f"{dev.name} bootloader 错误：{BL_ERROR_NAMES.get(value, value)}")
        elif addr == MH10_BL_REG_MAGIC and value == MH10_BL_MAGIC and not dev.bootloader:
            dev.bootloader = True
            self._event("warn", f"{dev.name} 处于 bootloader 模式（读到 BL 标识 0xB010）")
        elif addr == MH10_MB_REG_PROTOCOL_VERSION:
            if value != MH10_PROTOCOL_VERSION:
                self._event("warn",
                            f"{dev.name} 协议版本 0x{value:04X} 与本仓库 V{MH10_PROTOCOL_VERSION >> 8}."
                            f"{(MH10_PROTOCOL_VERSION >> 4) & 0xF}.{MH10_PROTOCOL_VERSION & 0xF} 不匹配")

    # ------------------------------------------------------------------
    # 帧解码（日志摘要）
    # ------------------------------------------------------------------

    def _reg_name(self, slave: int, addr: int) -> str:
        dev = self.devices.get(slave)
        if dev is not None and dev.bootloader:
            return MH10RegisterMap.bl_name(addr)
        return MH10RegisterMap.name(slave, addr)

    def _decode_request(self, frame: Frame) -> str:
        fc_name = FC_NAMES.get(frame.fc, f"功能码 0x{frame.fc:02X}")
        addr = frame.req_address()
        if addr is None:
            return f"{fc_name}（帧过短）"
        name = self._reg_name(frame.slave, addr)
        if frame.fc == MH10_MB_FC_READ_HOLDING_REGISTERS:
            return f"{fc_name} {name} 起始0x{addr:02X} 数量{frame.req_count()}"
        if frame.fc == MH10_MB_FC_WRITE_SINGLE_REGISTER:
            value = frame.req_write_value()
            if value is None:
                return f"{fc_name} {name}（帧过短）"
            extra = self._decode_value_semantic(frame.slave, addr, value)
            return f"{fc_name} {name} = 0x{value:04X}{extra}"
        if frame.fc == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            return f"{fc_name} 起始0x{addr:02X} 数量{frame.req_count()}"
        return fc_name

    def _decode_response(self, req: Frame, resp: Frame) -> str:
        if resp.fc == MH10_MB_FC_READ_HOLDING_REGISTERS:
            addr = req.req_address() or 0
            parts = []
            for i, v in enumerate(resp.resp_values()):
                parts.append(f"{self._reg_name(resp.slave, addr + i)}=0x{v:04X}{self._decode_value_semantic(resp.slave, addr + i, v)}")
            return "读取结果 " + " ".join(parts)
        if resp.fc == MH10_MB_FC_WRITE_SINGLE_REGISTER:
            addr = resp.req_address()
            return f"写确认 {self._reg_name(resp.slave, addr) if addr is not None else '?'}"
        if resp.fc == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            addr = resp.req_address()
            if addr is None:
                return "写确认（帧过短）"
            return f"写确认 起始0x{addr:02X} 数量{resp.req_count()}"
        return f"响应 功能码 0x{resp.fc:02X}"

    def _decode_value_semantic(self, slave: int, addr: int, value: Optional[int]) -> str:
        """附加物理量/枚举注释，如 '(RUNNING)' '(-50.0kPa)'。"""
        if value is None:
            return ""
        dev = self.devices.get(slave)
        if dev is not None and dev.bootloader:
            if addr == MH10_BL_REG_STATUS:
                return f"({BL_STATUS_NAMES.get(value, '?')})"
            if addr == MH10_BL_REG_ERROR:
                return f"({BL_ERROR_NAMES.get(value, '?')})"
            if addr == MH10_BL_REG_CMD:
                return f"({BL_CMD_NAMES.get(value, '?')})"
            return ""
        if slave == MH10_SLAVE_ID_FRONT_BOARD:
            if addr == MH10_MB_FO_TOOLHEAD_STATE_RO:
                return f"({TOOLHEAD_STATES.get(value, '?')})"
            if addr == MH10_MB_FO_TOOLHEAD_EXCEPTION_RW:
                return f"({TOOLHEAD_EXCEPTIONS.get(value, '?')})"
            if addr == MH10_MB_FO_TOOLHEAD_SPEED_RO:
                return f"({value * MH10_TOOLHEAD_SPEED_SCALE}RPM)"
        if slave == MH10_SLAVE_ID_BACK_BOARD:
            if addr in (MH10_MB_BK_NP_IS_RO, MH10_MB_BK_NP_OS_RO):
                return f"({value / MH10_NP_SCALE_FACTOR:.2f}kPa)"
            if addr == MH10_MB_BK_TARGET_STATE_WO:
                return f"({BACKBOARD_STATES.get(value, '?')})"
        return ""

    # ------------------------------------------------------------------
    # 日志与事件
    # ------------------------------------------------------------------

    def _log_frame(self, frame: Frame, direction: str, summary: str) -> None:
        self.frame_log.append(FrameRecord(
            ts=frame.ts_end, direction=direction, slave=frame.slave,
            summary=summary, hex=frame.hex, ok=frame.crc_ok,
        ))

    def _event(self, level: str, message: str) -> None:
        self.events.append(Event(ts=time.time(), level=level, message=message))

    # ------------------------------------------------------------------
    # 快照（供 UI 读取，调用方需持锁或使用 snapshot()）
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """线程安全地导出当前全部状态，供 GUI 定时刷新。"""
        with self.lock:
            now = time.time()
            duration = (now - self.start_ts) if self.start_ts else 0.0
            fps, bps = self._rates_locked(now)

            front = self.devices[MH10_SLAVE_ID_FRONT_BOARD]
            back = self.devices[MH10_SLAVE_ID_BACK_BOARD]

            def g(dev, addr):
                return dev.registers.get(addr)

            return {
                "now": now,
                "duration": duration,
                "fps": fps,
                "bps": bps,
                "bus_load": bps / (self.baudrate / 10.0) * 100.0 if self.baudrate else 0.0,
                "totals": {
                    "requests": self.total_requests,
                    "responses": self.total_responses,
                    "timeouts": self.total_timeouts,
                    "retries": self.total_retries,
                    "crc_errors": self.total_crc_errors,
                    "exceptions": self.total_exceptions,
                    "orphans": self.total_orphan_responses,
                    "frames": self.total_frames,
                    "bytes": self.total_bytes,
                    "loss_rate": (self.total_timeouts / (self.total_responses + self.total_timeouts) * 100.0)
                                 if (self.total_responses + self.total_timeouts) else 0.0,
                },
                "devices": {
                    sid: {
                        "name": d.name, "alive": d.alive, "ever_seen": d.ever_seen,
                        "last_seen": d.last_seen,
                        "requests": d.requests, "responses": d.responses,
                        "timeouts": d.timeouts, "retries": d.retries,
                        "exceptions": d.exceptions, "crc_errors": d.crc_errors,
                        "consecutive_failures": d.consecutive_failures,
                        "success_rate": d.success_rate,
                        "latency_avg": d.latency_avg,
                        "latency_min": d.latency_min, "latency_max": d.latency_max,
                        "versions": {
                            "hw": g(d, MH10_MB_REG_HW_VERSION),
                            "sw": g(d, MH10_MB_REG_SW_VERSION),
                            "svn": g(d, MH10_MB_REG_SVN_NUM),
                            "protocol": g(d, MH10_MB_REG_PROTOCOL_VERSION),
                            "const": g(d, MH10_MB_REG_CONST),
                        },
                    } for sid, d in self.devices.items()
                },
                "front": {
                    "state": g(front, MH10_MB_FO_TOOLHEAD_STATE_RO),
                    "state_name": TOOLHEAD_STATES.get(g(front, MH10_MB_FO_TOOLHEAD_STATE_RO), "—")
                                  if g(front, MH10_MB_FO_TOOLHEAD_STATE_RO) is not None else "—",
                    "exception": g(front, MH10_MB_FO_TOOLHEAD_EXCEPTION_RW),
                    "exception_name": TOOLHEAD_EXCEPTIONS.get(g(front, MH10_MB_FO_TOOLHEAD_EXCEPTION_RW), "—")
                                      if g(front, MH10_MB_FO_TOOLHEAD_EXCEPTION_RW) is not None else "—",
                    "info": g(front, MH10_MB_FO_TOOLHEAD_INFO_RO),
                    "speed_raw": g(front, MH10_MB_FO_TOOLHEAD_SPEED_RO),
                    "speed_rpm": (g(front, MH10_MB_FO_TOOLHEAD_SPEED_RO) or 0) * MH10_TOOLHEAD_SPEED_SCALE
                                 if g(front, MH10_MB_FO_TOOLHEAD_SPEED_RO) is not None else None,
                    "count": g(front, MH10_MB_FO_TOOLHEAD_COUNT_RO),
                    "position": g(front, MH10_MB_FO_TOOLHEAD_POS_RO),
                    "pedal_insert": g(front, MH10_MB_FO_PEDAL_INSERT_RO),
                    "pedal_switch": g(front, MH10_MB_FO_PEDAL_SWITCH_RO),
                    "toolhead_insert": g(front, MH10_MB_FO_TOOLHEAD_INSERT_RO),
                    "toolhead_switch": g(front, MH10_MB_FO_TOOLHEAD_SWITCH_RO),
                    "target_state": g(front, MH10_MB_FO_TOOLHEAD_STATE_RW),
                    "target_speed": g(front, MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW),
                    "target_dir": g(front, MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW),
                },
                "back": {
                    "version": g(back, MH10_MB_BK_VERSION_RO),
                    "np_is_raw": g(back, MH10_MB_BK_NP_IS_RO),
                    "np_os_raw": g(back, MH10_MB_BK_NP_OS_RO),
                    "np_is_kpa": g(back, MH10_MB_BK_NP_IS_RO) / MH10_NP_SCALE_FACTOR
                                 if g(back, MH10_MB_BK_NP_IS_RO) is not None else None,
                    "np_os_kpa": g(back, MH10_MB_BK_NP_OS_RO) / MH10_NP_SCALE_FACTOR
                                 if g(back, MH10_MB_BK_NP_OS_RO) is not None else None,
                    "target_state": g(back, MH10_MB_BK_TARGET_STATE_WO),
                    "target_state_name": BACKBOARD_STATES.get(g(back, MH10_MB_BK_TARGET_STATE_WO), "—")
                                         if g(back, MH10_MB_BK_TARGET_STATE_WO) is not None else "—",
                },
                "history": {
                    "np_is": list(self.hist_np_is),
                    "np_os": list(self.hist_np_os),
                    "speed": list(self.hist_speed),
                },
                "frame_log": list(self.frame_log),
                "events": list(self.events),
            }

    def record_sensor_history(self, now: Optional[float] = None) -> None:
        """按 UI 刷新节奏采样一次传感器历史（趋势图数据源）。"""
        if now is None:
            now = time.time()
        with self.lock:
            front = self.devices[MH10_SLAVE_ID_FRONT_BOARD]
            back = self.devices[MH10_SLAVE_ID_BACK_BOARD]
            if back.registers.get(MH10_MB_BK_NP_IS_RO) is not None:
                self.hist_np_is.append((now, back.registers[MH10_MB_BK_NP_IS_RO] / MH10_NP_SCALE_FACTOR))
            if back.registers.get(MH10_MB_BK_NP_OS_RO) is not None:
                self.hist_np_os.append((now, back.registers[MH10_MB_BK_NP_OS_RO] / MH10_NP_SCALE_FACTOR))
            if front.registers.get(MH10_MB_FO_TOOLHEAD_SPEED_RO) is not None:
                self.hist_speed.append((now, front.registers[MH10_MB_FO_TOOLHEAD_SPEED_RO] * MH10_TOOLHEAD_SPEED_SCALE))

    def _rates_locked(self, now: float) -> Tuple[float, float]:
        window = [e for e in self._traffic if e[0] > now - 2.0]
        if not window:
            return 0.0, 0.0
        span = max(now - window[0][0], 0.05)
        return len(window) / span, sum(b for _, b in window) / span

    def reset(self) -> None:
        """清空全部统计（保留连接）。"""
        with self.lock:
            self.__init__(self.response_timeout_s, self.offline_after_s,
                          self.baudrate, self.hist_np_is.maxlen, self.events.maxlen)
