# Xunjin MH10 Modbus RTU 通信协议规范 V1.2.0

## 1. 概述

本规范定义 Xunjin MH10 项目中主控板（A-Box）与两块工控小板（前板/后板）之间的 Modbus RTU 通信协议。

- **协议**：Modbus RTU
- **波特率 / 数据位 / 校验 / 停止位**：115200 / 8 / N / 1
- **总线拓扑**：半双工 RS-485，单主多从
- **主控板角色**：Modbus Master
- **前板角色**：Modbus Slave，地址 0x02
- **后板角色**：Modbus Slave，地址 0x03
- **电机驱动器（DM2C）角色**：Modbus Slave，地址 0x01（前板作为 Master 访问）

本规范的 C/C++ 定义位于 `include/mh10_protocol.h`，Python 绑定位于 `python/mh10_protocol.py`。

## 2. 物理层与链路层

| 参数 | 值 |
|------|-----|
| 波特率 | 115200 baud |
| 数据位 | 8 |
| 校验 | None |
| 停止位 | 1 |
| 帧结束检测（T35） | ≥ 3.5 字符时间（约 0.35 ms） |
| 默认响应超时 | 100 ms |
| 默认重试次数 | 2 次（实际尝试 3 次） |

主控板串口：
- ARM 目标板：`/dev/ttyS2`
- Windows 本地开发：`COM5`

## 3. 从机地址分配

| 地址 | 设备 |
|------|------|
| 0x00 | 广播地址 |
| 0x01 | 电机驱动器 DM2C |
| 0x02 | 前板（Front Board） |
| 0x03 | 后板（Back Board） |
| 0x04 | 预留附加电机 |

## 4. 功能码

| 功能码 | 名称 | 说明 |
|--------|------|------|
| 0x03 | Read Holding Registers | 读保持寄存器 |
| 0x06 | Write Single Register | 写单个保持寄存器 |
| 0x10 | Write Multiple Registers | 写多个保持寄存器 |

异常响应：功能码最高位置 1，随后跟异常码：
- 0x01：非法功能码
- 0x02：非法数据地址
- 0x03：非法数据值

## 5. 寄存器映射

### 5.1 系统公共寄存器（前后板共用）

| 地址 | 名称 | 方向 | 默认值 | 说明 |
|------|------|------|--------|------|
| 0x11 | MH10_MB_REG_IAP_ENTER | WO | 0x0000 | 写入 0xB007 复位并进入 IAP bootloader（app 模式有效，见第 9 节） |
| 0x18 | MH10_MB_REG_CONST | RO | 0xA0A0 | 在线检测常量 |
| 0x19 | MH10_MB_REG_REBOOT | WO | 0x0000 | 写入 0x5A5A 触发复位 |
| 0x1A | MH10_MB_REG_HW_VERSION | RO | 0x0100 | 硬件版本 |
| 0x1B | MH10_MB_REG_SW_VERSION | RO | - | 软件版本 |
| 0x1C | MH10_MB_REG_SVN_NUM | RO | - | SVN 版本号 |
| 0x1D | MH10_MB_REG_PROTOCOL_VERSION | RO | 0x0120 | 协议版本 V1.2.0 |
| 0x1E | MH10_MB_REG_GIT_HASH_HI | RO | - | 固件 git 提交号高 16 位（短哈希前 4 位 hex，按 hex 数值解读） |
| 0x1F | MH10_MB_REG_GIT_HASH_LO | RO | - | 固件 git 提交号低 16 位（短哈希第 5~8 位 hex）。完整显示：`printf("%04x%04x", HI, LO)` |

### 5.2 前板寄存器（Slave ID = 0x02）

| 地址 | 名称 | 方向 | 说明 |
|------|------|------|------|
| 0x00 | MH10_MB_FO_TOOLHEAD_STATE_RO | RO | 工具头运行状态 |
| 0x01 | MH10_MB_FO_TOOLHEAD_EXCEPTION_RW | RW | 异常码 |
| 0x02 | MH10_MB_FO_TOOLHEAD_INFO_RO | RO | 工具头型号信息 |
| 0x03 | MH10_MB_FO_TOOLHEAD_SPEED_RO | RO | 工具头实际速度（= RPM / 100） |
| 0x04 | MH10_MB_FO_TOOLHEAD_COUNT_RO | RO | 工具头往复次数 |
| 0x05 | MH10_MB_FO_TOOLHEAD_POS_RO | RO | 工具头位置百分比 |
| 0x06 | MH10_MB_FO_PEDAL_INSERT_RO | RO | 踏板是否插入 |
| 0x07 | MH10_MB_FO_PEDAL_SWITCH_RO | RO | 踏板开关状态 |
| 0x08 | MH10_MB_FO_TOOLHEAD_INSERT_RO | RO | 工具头是否插入 |
| 0x09 | MH10_MB_FO_TOOLHEAD_SWITCH_RO | RO | 工具头开关状态 |
| 0x0A | MH10_MB_FO_TOOLHEAD_STATE_RW | RW | 工具头目标状态 |
| 0x0B | MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW | RW | 目标速度 |
| 0x0C | MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW | RW | 目标方向 |
| 0x0D | MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO | WO | 自检确认 |
| 0x0E | MH10_MB_FO_TOOLHEAD_READY_TO_START_WO | WO | 启动/吸引确认 |
| 0x0F | MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO | WO | 踏板延时配置 |
| 0x10 | MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW | RW | 切割往复周期计数（两次 HEAD_SWITCH 闭合沿间编码器计数） |

### 5.3 后板寄存器（Slave ID = 0x03）

| 地址 | 名称 | 方向 | 默认值 | 说明 |
|------|------|------|--------|------|
| 0x00 | MH10_MB_BK_VERSION_RO | RO | 0x0101 | 后板版本/存在标识 |
| 0x01 | MH10_MB_BK_NP_IS_RO | RO | - | 入口侧负压（= kPa × -100） |
| 0x02 | MH10_MB_BK_NP_OS_RO | RO | - | 出口侧负压（= kPa × -100） |
| 0x03 | MH10_MB_BK_TARGET_STATE_WO | WO | - | 负压目标状态 |

## 6. 状态枚举

### 6.1 工具头运行状态

| 值 | 状态 |
|----|------|
| 0 | OFFLINE |
| 1 | PEDAL_ONLY |
| 2 | TOOLHEAD_ONLY |
| 3 | ONLINE_WAIT_SELFCHECK |
| 4 | SELF_CHECK |
| 5 | ONLINE_READY |
| 6 | WAITTING |
| 7 | RUNNING |
| 8 | ATTRACTING |
| 9 | EXCEPTION |

### 6.2 工具头异常码

| 值 | 异常 |
|----|------|
| 0 | NO_EXPECTION |
| 1 | EXP_READ_CARD |
| 2 | EXP_TOOLHEAD_OFFLINE |
| 3 | EXP_TOOLHEAD_SWITCH |
| 4 | EXP_PEDAL_OFFLINE |
| 5 | EXP_MOTOR_STOP |
| 6 | EXP_MOTOR_SPEED |
| 7 | EXP_MOTOR_DIR |

### 6.3 后板负压目标状态

| 值 | 状态 |
|----|------|
| 0 | CALIBRATION |
| 1 | CLOSED |
| 2 | OPEN |

## 7. 数值缩放

| 物理量 | 寄存器值 → 实际值 |
|--------|-------------------|
| 负压 | 实际 kPa = 寄存器值 / -100.0 |
| 工具头速度 | 实际 RPM = 寄存器值 × 100 |

## 8. 通信流程

### 8.1 上电在线检测

1. 主控板依次读取前板/后板 0x18 寄存器，期望返回 0xA0A0。
2. 读取 0x1A~0x1D 版本/协议版本寄存器。
3. 若协议版本不匹配，记录警告。
4. 向 0x19 写入 0x5A5A，触发下位机复位。

### 8.2 正常运行轮询

1. 处理 UI 下发的异步写命令队列。
2. 轮询前板：读取 0x00~0x0F。
3. 轮询后板：读取 0x00~0x03。
4. 将状态同步到 `sync.js`。

### 8.3 复位安全机制

- 仅当向 0x19 写入 0x5A5A 时，下位机执行 NVIC 系统复位。
- 写入其他非零值，下位机忽略并清零该寄存器。

## 9. IAP 固件升级（bootloader）

V1.2.0 起，前板/后板支持通过 Modbus 总线进行 IAP（In-Application Programming）固件升级。app 模式下向系统寄存器 0x11 写入魔数 0xB007，下位机置位备份寄存器标志并复位，复位后由 bootloader 接管串口等待固件下载。

### 9.1 Flash 布局（STM32F103C8，64 KB，页 1 KB）

| 区域 | 地址范围 | 大小 | 说明 |
|------|----------|------|------|
| bootloader | 0x08000000 ~ 0x08001FFF | 8 KB | IAP 引导程序 |
| app | 0x08002000 ~ 0x0800F7BF | ~54 KB | 应用程序（最大 55296 B 含版本块） |
| app 版本块 | 0x0800F7C0 ~ 0x0800F7FF | 64 B | app 有效标志（见 9.2） |
| 设备 ID 页 | 0x0800F800 ~ 0x0800FFFF | 1 KB | bootloader 保留，IAP 不得擦除 |

### 9.2 app 版本块（mh10_version_block_t）

固定位于 0x0800F7C0（app 镜像内偏移 0xD7C0），共 64 B，小端：

| 偏移 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 0 | magic | uint32 | 0x4D483130（ASCII "MH10"），app 有效标志 |
| 4 | board_id | uint16 | 从机地址：0x02 前板 / 0x03 后板 |
| 6 | sw_version | uint16 | 同 0x1B 软件版本 |
| 8 | svn_num | uint16 | 同 0x1C SVN 版本号 |
| 10 | git_hash_hi | uint16 | 同 0x1E git 提交号高 16 位 |
| 12 | git_hash_lo | uint16 | 同 0x1F git 提交号低 16 位 |
| 14 | struct_ver | uint16 | 版本块结构版本，当前为 1 |
| 16 | reserved[24] | uint16 | 保留，填充 0xFF |

主控板升级前从板载 hex 同地址解析本结构，与总线上读到的 0x1B/0x1E/0x1F 寄存器比对，不一致则触发升级。

**安全语义**：版本块由主控板在升级时**最后**烧写——只有整块固件写完并校验通过后，magic 才出现在 flash 中。bootloader 上电检查 magic，缺失则停留在下载模式，保证升级中途断电/复位不会启动残缺 app。

### 9.3 bootloader 模式寄存器映射

仅在 bootloader 运行时有效，与 app 模式寄存器是相互独立的命名空间。bootloader 同时应答系统寄存器 0x18（0xA0A0）、0x19（复位魔数）、0x1D（0x0120），并将 0x1B 报为 0x0000（用于触发主控板版本不一致判定）。

| 地址 | 名称 | 方向 | 说明 |
|------|------|------|------|
| 0x00 | MH10_BL_REG_MAGIC | RO | bootloader 标识，固定 0xB010 |
| 0x01 | MH10_BL_REG_STATUS | RO | 状态：0 IDLE / 1 ERASING / 2 READY / 3 DONE / 4 ERROR |
| 0x02 | MH10_BL_REG_ERROR | RO | 错误码：0 NONE / 1 BAD_STATE / 2 BAD_LEN / 3 FLASH / 4 BAD_CRC |
| 0x03 | MH10_BL_REG_CMD | WO | 命令：0x0001 ERASE / 0x0002 VERIFY / 0x5A5A JUMP |
| 0x04 | MH10_BL_REG_LENGTH | WO | 固件总长度（字节），≤ 55296 |
| 0x05 | MH10_BL_REG_CRC16 | WO | 整图 CRC16（Modbus 多项式 0xA001，初值 0xFFFF） |
| 0x06 | MH10_BL_REG_BLOCK | WO | 数据窗口目标块号（128 B/块） |
| 0x07 | MH10_BL_REG_PROGRESS | RO | 已烧写到的块数边界：写完块 N 后置为 N+1 |
| 0x10~0x4F | MH10_BL_REG_DATA | WO | 数据窗口，64 个寄存器 = 128 B；寄存器值 = 镜像小端字节对：reg[k] = data[2k] \| (data[2k+1]<<8)，整块 = 镜像 block*128 起的 128 B |

注：数据窗口 0x10~0x4F 与系统寄存器 0x18/0x19/0x1D 地址重叠；bootloader 对这些地址的**读**返回系统值，FC16 **写**数据窗口时按镜像数据处理。

### 9.4 升级流程（主控板为主机）

1. 读 0x00 应为 0xB010；否则（板子在 app 模式）先写 0x11=0xB007 让板子复位进入 bootloader。
2. 写 0x04=固件长度（字节，≤55296）、0x05=整图 CRC16，再写 0x03=0x0001（ERASE）；轮询 0x01 直到 READY/ERROR。
3. 逐块：写 0x06=块号（128 B/块），再 FC16 写 64 个寄存器到 0x10 起始的数据窗口；FC16 应答即代表该块已烧入 flash（同步烧写）。
4. 写 0x03=0x0002（VERIFY），bootloader 校验整图 CRC16，轮询 0x01 直到 DONE/ERROR。
5. 写 0x03=0x5A5A（JUMP，或 0x19=0x5A5A 复位），板子启动新 app；若 app 版本块 magic 缺失/无效，板子复位后仍停留在 bootloader 下载模式。

## 10. 可靠性设计

### 10.1 主控板

- 所有读写操作均支持最多 3 次指数退避重试（5 ms / 10 ms / 20 ms）。
- 连续 10 次命令失败后触发 `communicationLost()` 信号。
- 恢复成功后触发 `communicationRestored()` 信号。

### 10.2 工控板

- Modbus 主站接口（访问 DM2C）支持超时与重试。
- 后板在错误计数超过阈值或长时间无帧时可复位（保留现有逻辑）。

## 11. 版本变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| V1.0.0 | 2024/12/30 | 初始版本，前板/后板/系统寄存器定义 |
| V1.1.0 | 2026/07/15 | 统一协议到独立仓库；新增协议版本寄存器 0x1D；复位寄存器增加魔数 0x5A5A；后板版本寄存器强制初始化；主控板读操作增加重试；恢复后板周期轮询 |
| V1.2.0 | 2026/08/04 | 新增 IAP/bootloader 固件升级：系统寄存器 0x11（写入 0xB007 进入 bootloader）；定义 flash 布局与 64 B app 版本块（magic "MH10" 作 app 有效标志）；新增 bootloader 模式寄存器映射（0x00~0x07 + 数据窗口 0x10~0x4F）及擦除/烧写/校验/跳转升级流程 |

## 12. 引用与约束

- 主控板与工控板的参考固件必须通过 git submodule 引用本仓库。
- 禁止在板子参考固件中私自升版或修改协议定义。
- 所有寄存器地址、常量、缩放因子以 `include/mh10_protocol.h` 为准。
