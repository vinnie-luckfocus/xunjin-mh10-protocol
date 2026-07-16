#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus RTU 帧切分与解析。

主机通过 USB 转串口监听时，数据以块方式交付，主机侧时间戳精度
（毫秒级）无法分辨 t3.5 帧间隔（115200 下约 0.3ms）——主站连续
轮询时多帧会粘连在一个数据块中。因此本分帧器采用混合策略：

1. **长度预测 + CRC 校验**：Modbus 帧长按功能码可推导（0x03 请求
   8 字节、0x03 响应 5+2N、0x06/0x10 响应 8、0x10 请求 9+2N、异常
   响应 5），对每个候选长度做 CRC 验证，命中即出帧，可正确切分
   粘连帧并在噪声中重新同步；
2. **时间间隔兜底**：无法推导长度的残余字节（线路噪声），在接收
   间隔超时后按坏帧闭合，计入 CRC 错误统计。

每帧附带 CRC-16 校验结果，供上层统计误帧率。
"""

import struct
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from mh10_protocol import (
    MH10_MB_FC_READ_HOLDING_REGISTERS,
    MH10_MB_FC_WRITE_SINGLE_REGISTER,
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS,
    MH10_MODBUS_BAUDRATE,
)

KNOWN_FUNCTION_CODES = (
    MH10_MB_FC_READ_HOLDING_REGISTERS,
    MH10_MB_FC_WRITE_SINGLE_REGISTER,
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS,
)

# 异常码
EXCEPTION_CODES = {
    0x01: "非法功能码",
    0x02: "非法数据地址",
    0x03: "非法数据值",
}


def crc16(data: bytes) -> int:
    """计算 Modbus RTU CRC-16（多项式 0xA001，初值 0xFFFF）。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def append_crc(data: bytes) -> bytes:
    """附加小端 CRC，用于测试构造帧。"""
    return data + struct.pack("<H", crc16(data))


@dataclass
class Frame:
    """一帧 Modbus RTU 报文。

    ts_start 为首字节到达时间，ts_end 为末字节到达时间（time.time()）。
    """

    ts_start: float
    ts_end: float
    raw: bytes
    crc_ok: bool = False
    slave: int = -1
    fc: int = -1
    payload: bytes = b""  # 功能码之后、CRC 之前的数据

    def __post_init__(self):
        if len(self.raw) >= 4:
            body, crc_bytes = self.raw[:-2], self.raw[-2:]
            self.crc_ok = struct.pack("<H", crc16(body)) == crc_bytes
            self.slave = self.raw[0]
            self.fc = self.raw[1]
            self.payload = self.raw[2:-2]
        elif len(self.raw) >= 2:
            self.slave = self.raw[0]
            self.fc = self.raw[1]
            self.payload = self.raw[2:]

    @property
    def is_exception(self) -> bool:
        return bool(self.fc & 0x80)

    @property
    def base_fc(self) -> int:
        return self.fc & 0x7F

    @property
    def hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.raw)

    # ---- 请求字段解析 ----

    def req_address(self) -> Optional[int]:
        if len(self.payload) >= 2:
            return struct.unpack(">H", self.payload[0:2])[0]
        return None

    def req_count(self) -> Optional[int]:
        if len(self.payload) >= 4:
            return struct.unpack(">H", self.payload[2:4])[0]
        return None

    def req_write_value(self) -> Optional[int]:
        """0x06 写入值。"""
        if len(self.payload) >= 4:
            return struct.unpack(">H", self.payload[2:4])[0]
        return None

    def req_write_values(self) -> List[int]:
        """0x10 写入值列表。"""
        if len(self.payload) < 5:
            return []
        count = struct.unpack(">H", self.payload[2:4])[0]
        values = []
        for i in range(count):
            off = 5 + 2 * i
            if off + 2 <= len(self.payload):
                values.append(struct.unpack(">H", self.payload[off:off + 2])[0])
        return values

    # ---- 响应字段解析 ----

    def resp_values(self) -> List[int]:
        """0x03 响应的寄存器值列表。"""
        if len(self.payload) < 1:
            return []
        byte_count = self.payload[0]
        values = []
        for i in range(byte_count // 2):
            off = 1 + 2 * i
            if off + 2 <= len(self.payload):
                values.append(struct.unpack(">H", self.payload[off:off + 2])[0])
        return values

    def exception_code(self) -> Optional[int]:
        if self.is_exception and len(self.payload) >= 1:
            return self.payload[0]
        return None

    def request_key(self):
        """请求指纹：用于重试判定（同一请求重复发送）。"""
        return (self.slave, self.fc, self.payload)


class FrameSegmenter:
    """长度预测 + CRC 校验的流式分帧器，时间间隔兜底。

    feed() 送入带时间戳的字节块，返回本次解析出的完整帧；
    poll() 在接收静默超时后把无法解析的残余字节按坏帧闭合。
    """

    MIN_FRAME_LEN = 4

    def __init__(self, gap_s: Optional[float] = None, max_frame_len: int = 256):
        if gap_s is None:
            gap_s = max(3.5 * 11.0 / MH10_MODBUS_BAUDRATE, 0.002)
        self.gap_s = gap_s
        self.max_frame_len = max_frame_len
        self._buf = bytearray()
        self._noise = bytearray()  # 重同步过程中丢弃的噪声字节
        self._marks = deque()  # (字节数, 时间戳)，定位帧的首末字节时间
        self._last_ts: Optional[float] = None

    # ------------------------------------------------------------------

    def feed(self, data: bytes, ts: Optional[float] = None) -> List[Frame]:
        if ts is None:
            ts = time.time()
        if not data:
            return []
        self._buf.extend(data)
        self._marks.append((len(data), ts))
        self._last_ts = ts
        return self._drain()

    def poll(self, now: Optional[float] = None) -> List[Frame]:
        """静默超时：闭合残余字节（坏帧或长度无法推导的帧）。"""
        if now is None:
            now = time.time()
        if self._last_ts is None:
            return []
        if (now - self._last_ts) <= self.gap_s:
            return []
        frames = self._drain()
        frames.extend(self._flush_noise())  # 噪声字节在时序上先于残余
        if self._buf:  # 解析不出完整帧的残余 → 坏帧闭合
            frames.append(self._emit(len(self._buf)))
        return frames

    # ------------------------------------------------------------------

    def _candidate_lengths(self) -> Optional[List[int]]:
        """按缓冲首部的功能码推导候选帧长；None 表示需等待更多字节。"""
        n = len(self._buf)
        if n < self.MIN_FRAME_LEN:
            return None
        fc = self._buf[1]
        base = fc & 0x7F
        cands: List[int] = []
        if fc & 0x80:
            cands.append(5)  # 异常响应固定 5 字节
        if base == MH10_MB_FC_READ_HOLDING_REGISTERS:
            cands.append(8)  # 请求
            bc = self._buf[2]
            if bc and bc % 2 == 0 and bc <= 64:  # 响应：5 + 字节数
                cands.append(5 + bc)
        elif base == MH10_MB_FC_WRITE_SINGLE_REGISTER:
            cands.append(8)  # 请求/响应同构
        elif base == MH10_MB_FC_WRITE_MULTIPLE_REGISTERS:
            cands.append(8)  # 响应
            if n >= 7:
                bc = self._buf[6]
                if bc and bc % 2 == 0 and bc <= 64:  # 请求：9 + 字节数
                    cands.append(9 + bc)
        return sorted(set(cands))

    def _drain(self) -> List[Frame]:
        frames: List[Frame] = []
        while len(self._buf) >= self.MIN_FRAME_LEN:
            cands = self._candidate_lengths()
            if cands is None:
                break  # 字节不足，等待（理论不可达）
            if not cands:
                # 未知功能码：首字节按噪声丢弃，逐字节重新同步
                self._discard(1)
                continue
            matched = False
            decidable = True  # 所有候选长度都已有足够字节可判定
            for length in cands:
                if len(self._buf) < length:
                    decidable = False
                    continue
                body = bytes(self._buf[:length])
                if struct.pack("<H", crc16(body[:-2])) == body[-2:]:
                    frames.extend(self._flush_noise())  # 有效帧之前先补记噪声坏帧
                    frames.append(self._emit(length))
                    matched = True
                    break
            if matched:
                continue
            if not decidable:
                break  # 等更多字节再判定
            # 所有候选都 CRC 失败 → 首字节是噪声，丢弃一个字节重新同步
            self._discard(1)
        return frames

    def _emit(self, length: int) -> Frame:
        raw = bytes(self._buf[:length])
        del self._buf[:length]
        ts_start, ts_end = self._consume_marks(length)
        return Frame(ts_start=ts_start, ts_end=ts_end, raw=raw)

    def _discard(self, length: int) -> None:
        self._noise.extend(self._buf[:length])
        del self._buf[:length]
        self._consume_marks(length)

    def _flush_noise(self) -> List[Frame]:
        """把重同步丢弃的噪声字节汇成一帧坏帧（计入 CRC 错误统计）。"""
        if not self._noise:
            return []
        raw = bytes(self._noise)
        self._noise.clear()
        ts = self._last_ts if self._last_ts is not None else time.time()
        frame = Frame(ts_start=ts, ts_end=ts, raw=raw)
        frame.crc_ok = False  # 重同步丢弃的字节必然按坏帧统计
        return [frame]

    def _consume_marks(self, length: int):
        ts_start: Optional[float] = None
        ts_end: Optional[float] = self._last_ts
        remaining = length
        while remaining > 0 and self._marks:
            n, ts = self._marks[0]
            if ts_start is None:
                ts_start = ts
            ts_end = ts
            take = min(n, remaining)
            remaining -= take
            if take == n:
                self._marks.popleft()
            else:
                self._marks[0] = (n - take, ts)
        if ts_start is None:
            ts_start = ts_end if ts_end is not None else time.time()
        if ts_end is None:
            ts_end = ts_start
        return ts_start, ts_end
