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
├── simulator/
│   └── virtual_board.py         # 虚拟前后板 Modbus RTU 从机
├── tests/
│   ├── conftest.py              # pytest fixture
│   ├── test_protocol.py         # 功能测试
│   └── test_reliability.py      # 可靠性测试
├── docs/
│   └── protocol.md              # 协议规范文档
├── requirements.txt             # Python 依赖
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
