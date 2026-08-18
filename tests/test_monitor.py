#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控分析核心测试：分帧、CRC、请求-响应配对、超时/重试/异常统计、
传感器解码，以及基于虚拟板的 headless 端到端统计验证。
"""

import os
import struct
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "python"))
sys.path.insert(0, str(REPO_ROOT / "simulator"))

from conftest import create_pty_pair  # noqa: E402
from virtual_board import VirtualBoard, _crc16 as board_crc16  # noqa: E402

from monitor.analyzer import (  # noqa: E402
    BusAnalyzer,
    MH10_PROTOCOL_VERSION,
    MH10_SLAVE_ID_FRONT_BOARD,
    MH10_SLAVE_ID_BACK_BOARD,
    MH10_SLAVE_ID_BROADCAST,
    MH10RegisterMap,
)
from monitor.frames import Frame, FrameSegmenter, append_crc, crc16  # noqa: E402

import serial  # noqa: E402


def make_read_req(slave: int, addr: int, count: int) -> bytes:
    return append_crc(bytes([slave, 0x03]) + struct.pack(">HH", addr, count))


def make_read_resp(slave: int, values) -> bytes:
    body = bytes([slave, 0x03, len(values) * 2])
    for v in values:
        body += struct.pack(">H", v)
    return append_crc(body)


def make_write_single(slave: int, addr: int, value: int) -> bytes:
    return append_crc(bytes([slave, 0x06]) + struct.pack(">HH", addr, value))


def feed_raw(analyzer: BusAnalyzer, raw: bytes, ts: float):
    analyzer.feed(Frame(ts_start=ts, ts_end=ts, raw=raw))


# ----------------------------------------------------------------------
# CRC 与分帧
# ----------------------------------------------------------------------

class TestCrc:
    def test_crc_matches_virtual_board(self):
        data = bytes([0x02, 0x03, 0x00, 0x00, 0x00, 0x10])
        assert crc16(data) == board_crc16(data)

    def test_append_crc_roundtrip(self):
        frame = Frame(ts_start=0.0, ts_end=0.0, raw=make_read_req(2, 0, 16))
        assert frame.crc_ok
        assert frame.slave == 2
        assert frame.fc == 0x03
        assert frame.req_address() == 0
        assert frame.req_count() == 16

    def test_bad_crc_detected(self):
        raw = bytearray(make_read_req(2, 0, 16))
        raw[-1] ^= 0xFF
        frame = Frame(ts_start=0.0, ts_end=0.0, raw=bytes(raw))
        assert not frame.crc_ok


class TestSegmenter:
    def test_wellformed_frame_emitted_immediately(self):
        seg = FrameSegmenter()
        req = make_read_req(2, 0, 16)
        frames = seg.feed(req, ts=1.000)
        assert len(frames) == 1
        assert frames[0].raw == req
        assert frames[0].crc_ok

    def test_glued_frames_split_by_length_and_crc(self):
        """粘连帧（主站连续轮询）按长度+CRC 正确切分。"""
        seg = FrameSegmenter()
        req = make_read_req(2, 0, 16)
        resp = make_read_resp(2, [0] * 16)
        frames = seg.feed(req + resp, ts=1.000)  # 同一块数据，无时间间隔
        assert [f.raw for f in frames] == [req, resp]

    def test_chunked_delivery_reassembles(self):
        seg = FrameSegmenter()
        req = make_read_req(2, 0, 16)
        assert seg.feed(req[:4], ts=1.000) == []
        frames = seg.feed(req[4:], ts=1.0005)
        assert len(frames) == 1
        assert frames[0].raw == req

    def test_noise_resync(self):
        """前导噪声字节汇成坏帧，后续有效帧正常解析。"""
        seg = FrameSegmenter()
        req = make_read_req(2, 0, 16)
        frames = seg.feed(b"\xFF\xAA\x55" + req, ts=1.000)
        assert len(frames) == 2
        assert not frames[0].crc_ok
        assert frames[0].raw == b"\xFF\xAA\x55"
        assert frames[1].raw == req
        assert frames[1].crc_ok

    def test_poll_flushes_unparseable_tail(self):
        seg = FrameSegmenter(gap_s=0.002)
        assert seg.feed(b"\x02\x99\x01\x02\x03", ts=1.000) == []
        frames = seg.poll(now=1.010)
        assert len(frames) >= 1
        assert all(not f.crc_ok for f in frames)
        assert b"".join(f.raw for f in frames) == b"\x02\x99\x01\x02\x03"

    def test_v130_full_region_read_segmented(self):
        """V1.3.0 寄存器区扩至 0x50：整区读响应（bc=160）可正确分帧。"""
        seg = FrameSegmenter()
        req = make_read_req(2, 0, 0x50)
        resp = make_read_resp(2, [0] * 0x50)
        frames = seg.feed(req + resp, ts=1.000)
        assert [f.raw for f in frames] == [req, resp]

    def test_v130_long_write_multiple_segmented(self):
        """V1.3.0 调参区批量写（0x20 起 40 个寄存器，bc=80）可正确分帧。"""
        seg = FrameSegmenter()
        values = [0] * 0x28
        body = bytes([2, 0x10]) + struct.pack(">HHB", 0x20, len(values), len(values) * 2)
        for v in values:
            body += struct.pack(">H", v)
        req = append_crc(body)
        resp = append_crc(bytes([2, 0x10]) + struct.pack(">HH", 0x20, len(values)))
        frames = seg.feed(req + resp, ts=1.000)
        assert [f.raw for f in frames] == [req, resp]


# ----------------------------------------------------------------------
# 配对与统计
# ----------------------------------------------------------------------

class TestPairing:
    def test_request_response_paired(self):
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        feed_raw(an, make_read_resp(2, [7] * 16), ts=1.020)
        snap = an.snapshot()
        assert snap["totals"]["requests"] == 1
        assert snap["totals"]["responses"] == 1
        assert snap["totals"]["timeouts"] == 0
        dev = snap["devices"][2]
        assert dev["alive"] and dev["ever_seen"]
        assert dev["latency_avg"] == pytest.approx(0.020, abs=1e-6)
        assert dev["success_rate"] == 100.0
        assert snap["front"]["state"] == 7
        assert snap["front"]["state_name"] == "RUNNING"

    def test_timeout_then_retry(self):
        an = BusAnalyzer()
        req = make_read_req(2, 0, 16)
        feed_raw(an, req, ts=1.000)
        an.poll(now=1.200)  # 超过 100ms 无响应
        assert an.snapshot()["totals"]["timeouts"] == 1
        # 主站重试同一请求
        feed_raw(an, req, ts=1.300)
        snap = an.snapshot()
        assert snap["totals"]["retries"] == 1
        assert snap["devices"][2]["retries"] == 1
        # 重试成功
        feed_raw(an, make_read_resp(2, [0] * 16), ts=1.320)
        snap = an.snapshot()
        assert snap["totals"]["loss_rate"] == pytest.approx(50.0)

    def test_retry_request_not_mistaken_for_response(self):
        """重试的请求帧（与 pending 同地址同功能码）不能被误判为响应。"""
        an = BusAnalyzer()
        req = make_read_req(2, 0, 16)
        feed_raw(an, req, ts=1.000)
        feed_raw(an, req, ts=1.150)  # 主站超时后重发同一请求
        snap = an.snapshot()
        assert snap["totals"]["responses"] == 0
        assert snap["totals"]["timeouts"] == 1
        assert snap["totals"]["retries"] == 1

    def test_next_request_closes_pending_as_timeout(self):
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        feed_raw(an, make_read_req(3, 0, 4), ts=1.150)  # 新请求到达，上一请求判超时
        snap = an.snapshot()
        assert snap["totals"]["timeouts"] == 1
        assert snap["devices"][2]["timeouts"] == 1

    def test_exception_response(self):
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        feed_raw(an, append_crc(bytes([0x02, 0x83, 0x02])), ts=1.010)
        snap = an.snapshot()
        assert snap["totals"]["exceptions"] == 1
        assert snap["devices"][2]["exceptions"] == 1
        assert any("非法数据地址" in e.message for e in snap["events"])

    def test_crc_error_counted(self):
        an = BusAnalyzer()
        raw = bytearray(make_read_resp(2, [0] * 16))
        raw[3] ^= 0x55
        feed_raw(an, bytes(raw), ts=1.0)
        snap = an.snapshot()
        assert snap["totals"]["crc_errors"] == 1
        assert snap["devices"][2]["crc_errors"] == 1

    def test_broadcast_write_no_timeout(self):
        an = BusAnalyzer()
        feed_raw(an, make_write_single(MH10_SLAVE_ID_BROADCAST, 0x0A, 5), ts=1.0)
        an.poll(now=2.0)
        snap = an.snapshot()
        assert snap["totals"]["requests"] == 1
        assert snap["totals"]["timeouts"] == 0

    def test_device_offline_after_silence(self):
        an = BusAnalyzer(offline_after_s=1.0)
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        feed_raw(an, make_read_resp(2, [0] * 16), ts=1.010)
        assert an.snapshot()["devices"][2]["alive"]
        an.poll(now=3.0)
        snap = an.snapshot()
        assert not snap["devices"][2]["alive"]
        assert any("离线" in e.message for e in snap["events"])


# ----------------------------------------------------------------------
# 解码语义
# ----------------------------------------------------------------------

class TestDecode:
    def test_scaling_and_events(self):
        an = BusAnalyzer()
        # 前板：速度寄存器 500 → 50000 RPM；状态 RUNNING
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        values = [0] * 16
        values[0x00] = 7      # RUNNING
        values[0x03] = 500    # 速度
        values[0x06] = 1      # 踏板插入
        feed_raw(an, make_read_resp(2, values), ts=1.010)
        # 后板：负压 5000 → -50.0 kPa
        feed_raw(an, make_read_req(3, 0, 4), ts=1.100)
        feed_raw(an, make_read_resp(3, [0x0101, 5000, 4800, 1]), ts=1.110)
        snap = an.snapshot()
        assert snap["front"]["speed_rpm"] == 50000
        assert snap["front"]["pedal_insert"] == 1
        assert snap["back"]["np_is_kpa"] == pytest.approx(-50.0)
        assert snap["back"]["np_os_kpa"] == pytest.approx(-48.0)
        assert snap["back"]["target_state_name"] == "CLOSED"
        assert any("RUNNING" in e.message for e in snap["events"])

    def test_reboot_magic_event(self):
        an = BusAnalyzer()
        feed_raw(an, make_write_single(2, 0x19, 0x5A5A), ts=1.0)
        feed_raw(an, make_write_single(2, 0x19, 0x5A5A), ts=1.005)  # 0x06 响应回显
        snap = an.snapshot()
        assert any("复位魔数" in e.message for e in snap["events"])

    def test_toolhead_exception_event(self):
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        values = [0] * 16
        values[0x01] = 5  # EXP_MOTOR_STOP
        feed_raw(an, make_read_resp(2, values), ts=1.010)
        snap = an.snapshot()
        assert snap["front"]["exception_name"] == "EXP_MOTOR_STOP"
        assert any(e.level == "error" and "EXP_MOTOR_STOP" in e.message for e in snap["events"])

    def test_frame_log_records(self):
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 16), ts=1.000)
        feed_raw(an, make_read_resp(2, [0] * 16), ts=1.010)
        log = an.snapshot()["frame_log"]
        assert len(log) == 2
        assert log[0].direction == "REQ" and "读保持寄存器" in log[0].summary
        assert log[1].direction == "RESP"

    def test_tune_gear_array_names(self):
        """V1.3.0 档位数组寄存器按索引命名。"""
        assert MH10RegisterMap.name(2, 0x20) == "MB_FO_TUNE_GEAR_SPEED[0]"
        assert MH10RegisterMap.name(2, 0x27) == "MB_FO_TUNE_GEAR_SPEED[7]"
        assert MH10RegisterMap.name(2, 0x28) == "MB_FO_TUNE_GEAR_ZONE[0]"
        assert MH10RegisterMap.name(2, 0x3F) == "MB_FO_TUNE_GEAR_ACCEL[7]"
        assert MH10RegisterMap.name(2, 0x4A) == "MB_FO_TUNE_STATUS"

    def test_tune_registers_decode(self):
        """V1.3.0 调参区：快照字段、语义注释与事件。"""
        an = BusAnalyzer()
        feed_raw(an, make_read_req(2, 0, 0x50), ts=1.000)
        values = [0] * 0x50
        values[0x20] = 900    # 档0 转速
        values[0x30] = 16     # 档0 电流 1.6A
        values[0x49] = 3      # 手动运行档位
        values[0x4A] = 3      # 标定完成
        values[0x4B] = 216    # 周期计数
        values[0x4C] = 6      # 闭合区宽度
        values[0x4D] = 594    # 最近往复耗时
        values[0x4E] = (2 << 10) | (3 << 5) | 15  # 沿采信15 固定闭合3 固定未闭合2
        feed_raw(an, make_read_resp(2, values), ts=1.010)
        snap = an.snapshot()
        front = snap["front"]
        assert front["tune_status_name"] == "标定完成"
        assert front["tune_cycle_counts"] == 216
        assert front["tune_zone_width"] == 6
        assert front["tune_last_cycle_ms"] == 594
        assert any("调参状态：— → 标定完成" in e.message for e in snap["events"])
        resp_summary = snap["frame_log"][1].summary
        assert "MB_FO_TUNE_GEAR_SPEED[0]=0x0384(档0 900RPM)" in resp_summary
        assert "(档0 1.6A)" in resp_summary
        assert "(标定完成)" in resp_summary
        assert "(近20往复 沿采信15 固定闭合3 固定未闭合2)" in resp_summary

    def test_tune_cmd_and_error_events(self):
        an = BusAnalyzer()
        feed_raw(an, make_write_single(2, 0x48, 1), ts=1.0)
        feed_raw(an, make_write_single(2, 0x48, 1), ts=1.005)  # 0x06 响应回显
        # 标定失败：状态 0→4，失败原因 4（找不到闭合区）
        feed_raw(an, make_read_req(2, 0x4A, 6), ts=2.0)
        feed_raw(an, make_read_resp(2, [4, 0, 0, 0, 0, 4]), ts=2.010)
        snap = an.snapshot()
        assert any("调参命令：自动标定" in e.message for e in snap["events"])
        assert any(e.level == "error" and "调参状态：— → 标定失败" in e.message
                   for e in snap["events"])
        assert any(e.level == "error" and "调参失败原因：找不到闭合区" in e.message
                   for e in snap["events"])


# ----------------------------------------------------------------------
# headless 端到端：虚拟板 + 真实串口帧 + tee 进分析器
# ----------------------------------------------------------------------

class _TeeMaster:
    """最小主站：发请求收响应，把双向流量 tee 进分析器。"""

    def __init__(self, port: str, analyzer: BusAnalyzer):
        self.ser = serial.Serial(port, 115200, timeout=0.15)
        self.analyzer = analyzer
        self.segmenter = FrameSegmenter()

    def request(self, raw: bytes, resp_len: int = 37) -> bytes:
        t0 = time.time()
        self.ser.write(raw)
        resp = self.ser.read(resp_len)  # 读满响应长度即返回，避免粘帧
        t1 = time.time()
        for frame in self.segmenter.feed(raw, t0):
            self.analyzer.feed(frame)
        for frame in self.segmenter.feed(resp, t1):
            self.analyzer.feed(frame)
        # 显式用稍后的时间戳闭合响应帧（真实间隔在响应帧结束之后）
        for frame in self.segmenter.poll(t1 + 0.01):
            self.analyzer.feed(frame)
        self.analyzer.poll(t1)
        return resp

    def close(self):
        self.ser.close()


@pytest.fixture
def pty_board():
    import os
    import threading
    master_fd, slave_name, slave_fd = create_pty_pair()
    os.close(slave_fd)
    board = VirtualBoard()
    thread = threading.Thread(target=board.run_fd, args=(master_fd, 115200), daemon=True)
    thread.start()
    time.sleep(0.2)
    yield board, slave_name
    board.stop()
    os.close(master_fd)


class TestEndToEnd:
    def test_healthy_bus_no_loss(self, pty_board):
        _, slave_name = pty_board
        an = BusAnalyzer()
        master = _TeeMaster(slave_name, an)
        try:
            # 先读一次系统寄存器（上电在线检测流程），再进入正常轮询
            assert master.request(make_read_req(2, 0x18, 6), resp_len=5 + 12)
            for _ in range(10):
                assert master.request(make_read_req(2, 0x00, 16), resp_len=5 + 32)
                assert master.request(make_read_req(3, 0x00, 4), resp_len=5 + 8)
        finally:
            master.close()
        snap = an.snapshot()
        assert snap["totals"]["requests"] == 21
        assert snap["totals"]["responses"] == 21
        assert snap["totals"]["timeouts"] == 0
        assert snap["totals"]["loss_rate"] == 0.0
        assert snap["devices"][2]["alive"] and snap["devices"][3]["alive"]
        assert snap["front"]["speed_rpm"] is not None
        assert snap["back"]["np_is_kpa"] is not None
        assert snap["devices"][2]["versions"]["protocol"] == MH10_PROTOCOL_VERSION

    def test_silent_board_full_loss(self, pty_board):
        board, slave_name = pty_board
        board.silent_rate = 1.0  # 全部不响应
        an = BusAnalyzer()
        master = _TeeMaster(slave_name, an)
        try:
            for _ in range(3):
                assert master.request(make_read_req(2, 0x00, 16)) == b""
        finally:
            master.close()
        snap = an.snapshot()
        assert snap["totals"]["timeouts"] == 3
        assert snap["totals"]["responses"] == 0
        assert snap["totals"]["loss_rate"] == 100.0
        assert not snap["devices"][2]["alive"]


# ----------------------------------------------------------------------
# GUI 冒烟测试（offscreen）
# ----------------------------------------------------------------------

class TestGuiSmoke:
    @pytest.fixture
    def window(self):
        pytest.importorskip("PySide6")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        from monitor.app import create_app
        from monitor.main_window import MainWindow
        if QtWidgets.QApplication.instance() is None:
            create_app([])
        win = MainWindow()
        yield win
        win.close()

    def test_window_renders_and_updates(self, window):
        an = window.analyzer
        feed_raw(an, make_read_req(2, 0, 16), ts=time.time())
        feed_raw(an, make_read_resp(2, [7] * 16), ts=time.time() + 0.01)
        window._refresh()
        assert window.front_panel.state_label.text() == "RUNNING"
        assert window.quality_panel._values["requests"].text() == "1"
        assert window.frame_log.table.rowCount() == 2

    def test_single_sniffer_on_connect(self, window):
        """_connect 不得因 toggled 信号重入而创建多个监听线程。"""
        import threading
        master_fd, slave_name, slave_fd = create_pty_pair()
        os.close(slave_fd)
        try:
            window._connect(slave_name)
            sniffers = [t for t in threading.enumerate() if t.name.startswith("sniffer-")]
            assert len(sniffers) == 1
            window._disconnect()
            sniffers = [t for t in threading.enumerate() if t.name.startswith("sniffer-")]
            assert len(sniffers) == 0
        finally:
            os.close(master_fd)

    def test_timeline_view(self, window):
        an = window.analyzer
        now = time.time()
        # 前板 REQ/RESP、后板 RESP、广播各若干
        feed_raw(an, make_read_req(2, 0, 16), ts=now - 2.0)
        feed_raw(an, make_read_resp(2, [0] * 16), ts=now - 1.9)
        feed_raw(an, make_read_req(3, 0, 4), ts=now - 1.0)
        feed_raw(an, make_read_resp(3, [0x0101, 0, 0, 1]), ts=now - 0.9)
        feed_raw(an, make_write_single(0, 0x0A, 100), ts=now - 0.5)
        window._refresh()

        tl = window.timeline
        assert len(tl._points) == 5
        # 车道归属：前板/后板各自 REQ/RESP 车道，广播独立车道
        lane_of = {(rec.slave, rec.direction): key for _, key, rec in tl._points}
        assert lane_of[(2, "REQ")] == (2, "REQ")
        assert lane_of[(2, "RESP")] == (2, "RESP")
        assert lane_of[(3, "RESP")] == (3, "RESP")
        assert lane_of[(0, "REQ")] == (0, "REQ")
        # 窗口外（>120s）的点不上屏；窗口内每车道点数正确
        feed_raw(an, make_read_req(2, 0, 16), ts=now - 200.0)
        window._refresh()
        front_req = tl._visible[(2, "REQ")]
        assert len(front_req) == 1 and front_req[0].slave == 2
        # 清空
        tl.clear()
        assert len(tl._points) == 0

    def test_frame_log_keeps_updating_past_deque_maxlen(self, window):
        """帧数超过分析器环形队列上限后，实时帧表格必须持续更新（绕圈同步）。"""
        an = window.analyzer
        an.frame_log = an.frame_log.__class__(maxlen=100)  # 缩小上限模拟绕圈
        ts = time.time()
        for i in range(250):
            feed_raw(an, make_read_req(2, 0, 16), ts=ts + i * 0.001)
        window._refresh()
        assert window._frames_seen == 250
        assert window.frame_log.table.rowCount() == 100  # 表格截断到队列内最新 100 条
        first_hex = window.frame_log.table.item(0, 4).text()
        assert first_hex == make_read_req(2, 0, 16).hex(" ").upper()
        # 再来 50 条：表格必须继续滚动而不是停住
        for i in range(250, 300):
            feed_raw(an, make_read_req(3, 0, 4), ts=ts + i * 0.001)
        window._refresh()
        assert window._frames_seen == 300
        # 表格上限 1000 > 已同步 150，新 50 条全部追加成功
        assert window.frame_log.table.rowCount() == 150
        assert window.frame_log.table.item(0, 2).text() == "0x02"
        assert window.frame_log.table.item(149, 2).text() == "0x03"
        rows_03 = sum(1 for r in range(150)
                      if window.frame_log.table.item(r, 2).text() == "0x03")
        assert rows_03 == 50
