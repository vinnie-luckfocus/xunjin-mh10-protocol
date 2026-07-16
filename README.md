# Xunjin MH10 Modbus RTU 协议仓库

本仓库是 Xunjin MH10 项目主控板与前后工控板之间 Modbus RTU 通信协议的**单一事实来源**。

## 仓库定位

- 主控板仓库：`xunjin-mh10-mainboard-app`
- 工控板仓库：`xunjin-mh10-miniboard-app`
- 协议仓库：`xunjin-mh10-modbus-protocol`（本仓库）

**约定**：主控板和工控板的参考固件必须引用本仓库的协议代码，不得私自升版协议。

## 当前协议版本

**V1.1.0**（对应寄存器 `MH10_MB_REG_PROTOCOL_VERSION` 值 `0x0110`）

主要变更：
- 统一前后板与主控板的寄存器定义到本仓库。
- 新增协议版本寄存器 `0x1D`。
- 复位寄存器 `0x19` 仅识别魔数 `0x5A5A`，防止误触发。
- 明确后板版本寄存器 `0x00` 必须初始化。

## 目录结构

```
.
├── include/
│   └── mh10_protocol.h          # C/C++ 共享协议头文件
├── python/
│   └── mh10_protocol.py         # Python 协议绑定
├── monitor/
│   ├── frames.py                # Modbus RTU 分帧（长度+CRC）与解析
│   ├── analyzer.py              # 总线流量分析核心（配对/统计/解码/事件）
│   ├── serial_source.py         # 串口/TCP 被动监听线程
│   ├── main_window.py           # 监控器主窗口
│   ├── widgets.py               # 设备卡片/传感器面板/统计/日志组件
│   └── charts.py                # 趋势图（pyqtgraph）
├── simulator/
│   └── virtual_board.py         # 虚拟前后板 Modbus RTU 从机
├── tools/
│   ├── bus_tap.py               # 三通总线桥（pty×2 + TCP 监控端，本地演示用）
│   └── virtual_master.py        # 虚拟主控板（按协议节奏产生流量）
├── tests/
│   ├── conftest.py              # pytest fixture
│   ├── test_protocol.py         # 功能测试
│   ├── test_reliability.py      # 可靠性测试
│   └── test_monitor.py          # 监控分析核心测试
├── docs/
│   └── protocol.md              # 协议规范文档
├── requirements.txt             # Python 依赖（协议测试）
├── requirements-monitor.txt     # 监控器 GUI 追加依赖
└── README.md
```

## 快速开始

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 运行虚拟测试

```bash
pytest tests/ -v
```

### 启动独立虚拟从机

```bash
# 使用 socat 创建串口对（Linux/macOS）
socat -d -d pty,rawer,echo=0 pty,rawer,echo=0

# 在从端启动虚拟板
python simulator/virtual_board.py --port /dev/ttysXXX

# 主编端可用 pymodbus/minicom 等工具连接另一个 ttysXXX
```

## 总线监控器（GUI）

`monitor/` 是一个被动监听式 Modbus RTU 总线监控分析器：PC 通过 USB 转
RS-485 工具并接在总线上（只收不发，对主控板与前后板完全透明），实时
解码并统计全部流量。

功能：

- **系统运行质量**：各从机（前板 0x02 / 后板 0x03 / 电机 0x01 / 预留 0x04）
  在线状态、最近通信时间、通信成功率、响应延迟（avg/min/max）、版本信息
  （HW/SW/SVN/协议版本，不匹配告警）；
- **传感器实时数据**：工具头状态机/异常码/速度 RPM/位置/往复次数/踏板与
  工具头插拔开关、入口/出口负压 kPa、负压目标状态，附趋势曲线；
- **丢包与错误统计**：未响应（超时）次数与丢包率、重试检测、CRC 错误帧、
  异常响应（异常码解码）、孤立帧、帧率/吞吐量/总线负载；
- **帧日志与事件日志**：原始 hex + 协议解码（寄存器名、枚举名、缩放后物理
  值），支持按设备/方向过滤、暂停滚动、导出 CSV；事件日志记录设备上下线、
  工具头状态迁移、异常出现/清除、复位魔数（0x19←0x5A5A）等。

### 安装与启动

```bash
pip install -r requirements.txt -r requirements-monitor.txt

# 接好 USB 转 RS-485 后启动（Windows 端口如 COM5）
python -m monitor                 # 启动后在界面选择端口并连接
python -m monitor --port COM5     # 启动即连接
```

### 无硬件本地演示

```bash
# 1. 启动三通总线桥（会打印 A/B/C 三个端点）
python tools/bus_tap.py

# 2. B 端接虚拟前后板（可注入错误演示丢包统计）
python simulator/virtual_board.py --port /dev/ttysXXX --error-rate 0.05 --silent-rate 0.03

# 3. A 端接虚拟主控板（产生轮询流量）
python tools/virtual_master.py --port /dev/ttysYYY

# 4. C 端接监控器
python -m monitor --port socket://127.0.0.1:7301
```

无头验证（CI/截图）：

```bash
QT_QPA_PLATFORM=offscreen python -m monitor --port socket://127.0.0.1:7301 \
    --screenshot monitor.png --screenshot-delay 10
```

## 引用方式

### 主控板（Qt/C++）

建议以 git submodule 形式引入：

```bash
cd xunjin-mh10-mainboard-app
mkdir -p 3rd
git submodule add https://github.com/vinnie-luckfocus/xunjin-mh10-protocol.git 3rd/xunjin-mh10-protocol
```

在 `.pro` 文件中增加：

```qmake
INCLUDEPATH += $$PWD/3rd/xunjin-mh10-protocol/include
```

代码中：

```cpp
#include "mh10_protocol.h"
```

### 工控板（Keil/C）

建议以 git submodule 形式引入：

```bash
cd xunjin-mh10-miniboard-app
mkdir -p 3rd
git submodule add https://github.com/vinnie-luckfocus/xunjin-mh10-protocol.git 3rd/xunjin-mh10-protocol
```

在 Keil 工程中将 `3rd/xunjin-mh10-protocol/include/mh10_protocol.h` 加入 include path。

代码中：

```c
#include "mh10_protocol.h"
```

## 协议规范

详见 [docs/protocol.md](docs/protocol.md)。
