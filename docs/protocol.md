# Xunjin MH10 Modbus RTU 通信协议规范 V1.9.1

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
| 0x1D | MH10_MB_REG_PROTOCOL_VERSION | RO | 0x0191 | 协议版本 V1.9.1 |
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
| 0x0C | MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW | RW | 目标方向/切割模式：0=正转（连续旋转，默认） 1=反转（连续旋转） 2=往复（速度规划往复切割）。V1.4.0 起 0/1 语义由"往复起始方向"改为连续旋转方向 |
| 0x0D | MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO | WO | 自检确认 |
| 0x0E | MH10_MB_FO_TOOLHEAD_READY_TO_START_WO | WO | 启动/吸引确认 |
| 0x0F | MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO | WO | 踏板延时配置 |
| 0x10 | MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW | RW | 切割往复周期计数（两次 HEAD_SWITCH 闭合沿间编码器计数） |
| 0x12 | MH10_MB_FO_ALARM_SUPPRESS_RW | RW | 异常检测屏蔽（V1.5.0）：bit0=1 屏蔽转速/驱动器异常检测——连续/往复转速判据与驱动器故障锁存检测到异常时仅打印日志，不置异常码、不进 EXCEPTION 停机（**屏蔽后电机不停机保护失效**）。上电默认 0=检测开启，写入立即生效，易失不擦 flash（持久化由 box 侧负责） |
| 0x13 | MH10_MB_FO_AUTO_RETRACT_RW | RW | 自动退刀使能（V1.8.0）：bit0=1 时运行中发生 `EXP_MOTOR_STOP` 堵转异常后，前板先停机再以安全低速反向旋转，直至切割窗口到达打开位置（HEAD_SWITCH 闭合沿后再走半个往复周期）后停止，随后仍按原流程上报堵转异常。上电默认 0=关闭，写入立即生效，易失不擦 flash（持久化由 box 侧负责）。**0x12 bit0=1 屏蔽检测时本功能不触发（无检测就无异常）** |
| 0x14 | MH10_MB_FO_FULL_POWER_SPEED_RW | RW | 全力转速（V1.9.0）：两段式加速第一段的目标转速，单位 rpm，量纲同 0x0B 目标速度（设定转速）。上电默认 4500，写 0 或越界时固件回退默认值，写入立即生效，易失不擦 flash（持久化由 box 侧负责），后板不实现 |
| 0x15 | MH10_MB_FO_FULL_POWER_RISE_RW | RW | 全力上升时间（V1.9.0）：爬到全力转速所用加速时间，单位 ms/1000rpm（对应 DM2C PR0 加速时间）。上电默认 100，写 0 或越界时固件回退默认值，其余同 0x14 |
| 0x16 | MH10_MB_FO_ACCEL_RISE_RW | RW | 加速上升时间（V1.9.0）：全力转速以上段（稳定 0x17 时间后）爬到目标转速所用加速时间，单位 ms/1000rpm。上电默认 1000，写 0 或越界时固件回退默认值，其余同 0x14 |
| 0x17 | MH10_MB_FO_RAMP_STABLE_MS_RW | RW | 全力转速稳定时间（V1.9.1）：爬到全力转速后保持稳定、再进入加速上升段的时间，单位 ms，有效范围 100~3000。上电默认 3000（即 V1.9.0 固件的固定 3 秒），写 0 或越界时固件回退默认值，其余同 0x14 |

0x14~0x17 为前板两段式加速参数（V1.9.0 起，0x17 为 V1.9.1 新增），仅连续旋转模式使用，往复模式不用：
目标转速 ≤ 全力转速（0x14）时，用全力上升时间（0x15）一步爬坡到位；目标转速 > 全力转速时，
先用全力上升时间爬到全力转速，稳定 0x17 指定的时间（默认 3000ms，V1.9.0 固件为固定 3 秒）后再以
加速上升时间（0x16）爬到目标转速。

### 5.2.1 前板调参寄存器区（V1.3.0 新增，0x20~0x4F）

供 box 系统信息"电机调参"页面对切割往复引擎在线调参、自动标定与手动档位运行。
参数上电为固件定版默认值，写入立即生效（易失，不擦写 flash，持久化由 box 侧负责）。
档位下标 i=0~7 对应 jog rpm（电机轴）300/600/900/1200/1500/2000/2500/3000，
设定值 = jog×3。详细设计见 b_mini_board 仓 docs/design-motor-tuning.md。

| 地址 | 名称 | 方向 | 默认值 | 说明 |
|------|------|------|--------|------|
| 0x20+i | MH10_MB_FO_TUNE_GEAR_SPEED_BASE | RW | 900/1800/2700/3600/4500/6000/7500/9000 | 档位全速段设定转速（8 个） |
| 0x28+i | MH10_MB_FO_TUNE_GEAR_ZONE_BASE | RW | 6/6/6/10/16/26/50/68 | 档位近顶减速区步数（8 个） |
| 0x30+i | MH10_MB_FO_TUNE_GEAR_CURRENT_BASE | RW | 16/18/18/18/20/20/22/22 | 档位峰值电流（0.1A，8 个） |
| 0x38+i | MH10_MB_FO_TUNE_GEAR_ACCEL_BASE | RW | 80 | 档位加速时间 ms/1000rpm（8 个） |
| 0x40 | MH10_MB_FO_TUNE_DECEL | RW | 30 | 减速时间 ms/1000rpm（全局） |
| 0x41 | MH10_MB_FO_TUNE_START_SPEED | RW | 900 | 起步段设定转速（jog300） |
| 0x42 | MH10_MB_FO_TUNE_START_STEPS | RW | 12 | 起步段步数 |
| 0x43 | MH10_MB_FO_TUNE_SLOW_SPEED | RW | 450 | 近顶爬行设定转速（jog150） |
| 0x44 | MH10_MB_FO_TUNE_REV_EXTRA | RW | 4 | 沿采信后延迟换向步数（贴顶微调） |
| 0x45 | MH10_MB_FO_TUNE_CRAWL_ADJ_MAX | RW | 8 | 爬行自适应最大加步 |
| 0x46 | MH10_MB_FO_TUNE_ESTOP_MS | RW | 60 | 急停减速时间 ms |
| 0x48 | MH10_MB_FO_TUNE_CMD | WO | - | 命令：1=自动标定 2=手动运行启动 3=手动运行停止 4=恢复默认参数 |
| 0x49 | MH10_MB_FO_TUNE_GEAR | RW | 0 | 手动运行档位号 0~7 |
| 0x4A | MH10_MB_FO_TUNE_STATUS | RO | 0 | 0=空闲 1=标定中 2=手动运行中 3=标定完成 4=失败 |
| 0x4B | MH10_MB_FO_TUNE_CYCLE_COUNTS_RO | RO | - | 标定测得的往复周期计数（同步写 0x10） |
| 0x4C | MH10_MB_FO_TUNE_ZONE_WIDTH_RO | RO | - | 标定测得的闭合区宽度（步） |
| 0x4D | MH10_MB_FO_TUNE_LAST_CYCLE_MS_RO | RO | - | 最近一个往复实测耗时 ms |
| 0x4E | MH10_MB_FO_TUNE_REV_STAT_RO | RO | - | 近 20 往复换向质量：bit0-4 E 数 / bit5-9 F 数 / bit10-14 O 数 |
| 0x4F | MH10_MB_FO_TUNE_ERROR_RO | RO | 0 | 失败原因：0 无 1 未插刀 2 堵转 3 超时 4 找不到闭合区 |

### 5.2.2 前板正/反转电流曲线调节区（V1.6.0 新增，0x50~0x6C）

供 box 系统维护"正反转校准"页面对连续旋转模式的 速度→峰值电流 分段阶梯曲线在线调参。
曲线模型与固件现有模型一致：3 个速度阈值（工具头输出轴 rpm）把速度域分成 4 段，
每段一档峰值电流（0.1A）：speed ≤ LOW 用 CUR[0]，≤ MED 用 CUR[1]，≤ HIGH 用 CUR[2]，
否则用 CUR[3]；无插值，纯阶梯。共四套曲线（驱动器型号 × 旋转方向）：
DM2C522 正转 / DM2C522 反转 / DM2C556 正转 / DM2C556 反转，
运行时按实际检测到的 DM2C 型号与当前方向选一套。
每套曲线占 7 个寄存器（基址 + 偏移）：+0/+1/+2 为速度阈值 LOW/MED/HIGH（写入时固件
钳制为单调递增），+3~+6 为峰值电流 CUR[0..3]（钳制到该型号上限：522→22，556→25）。
写寄存器立即生效（易失，不擦写 flash，持久化由 box 侧 sys.ini 负责）。

| 地址 | 名称 | 方向 | 默认值 | 说明 |
|------|------|------|--------|------|
| 0x50+k | MH10_MB_FO_CURVE_FWD_522_BASE | RW | 1000/4000/7000 + 16/18/20/22 | DM2C522 正转曲线（0x50~0x56）：k=0~2 阈值 LOW/MED/HIGH rpm，k=3~6 峰值电流 CUR[0..3]（0.1A） |
| 0x57+k | MH10_MB_FO_CURVE_REV_522_BASE | RW | 1000/4000/7000 + 16/18/20/22 | DM2C522 反转曲线（0x57~0x5D），布局同上 |
| 0x5E+k | MH10_MB_FO_CURVE_FWD_556_BASE | RW | 1000/4000/7000 + 18/20/23/25 | DM2C556 正转曲线（0x5E~0x64），布局同上 |
| 0x65+k | MH10_MB_FO_CURVE_REV_556_BASE | RW | 1000/4000/7000 + 18/20/23/25 | DM2C556 反转曲线（0x65~0x6B），布局同上 |
| 0x6C | MH10_MB_FO_CURVE_SUPPORT_RO | RO | 0xC0DE | 扩展区支持标识：支持 0x50~0x6F 扩展区（电流曲线 + 调试直驱，同一固件版本一并实现）的固件固定返回 MH10_CURVE_SUPPORT_MAGIC（0xC0DE）；旧固件（REG_COUNT=0x50）读该地址返回非法地址异常（0x02），主机据此优雅降级（隐藏/禁用曲线调节与调试直驱功能） |

默认值即 V1.5.0 及以前固件的编译期行为（正/反转默认相同）。

### 5.2.3 前板调试直驱寄存器（V1.7.0 新增，0x6D~0x6F）

供 box 系统维护"调试模式"页面直接驱动电机连续旋转，完全独立于切割/往复状态机与
调参手动档位运行（不占用 0x20~0x4F 调参区任何寄存器）。启动后电机按 0x6D 设定转速、
0x6E 方向持续连续旋转，直到收到停止命令；电流按 5.2.2 曲线区对应方向/驱动器型号的
曲线随速度下发。支持判定与曲线区共用 0x6C 支持标识，旧固件写 0x6D~0x6F 返回非法
地址异常（0x02），主机据此优雅降级。

| 地址 | 名称 | 方向 | 默认值 | 说明 |
|------|------|------|--------|------|
| 0x6D | MH10_MB_FO_DEBUG_SPEED_RW | RW | 0 | 直驱设定转速（工具头输出轴 rpm，与 0x0B 同刻度，固件钳制到安全范围） |
| 0x6E | MH10_MB_FO_DEBUG_DIR_RW | RW | 0 | 直驱方向：0=正转 1=反转 |
| 0x6F | MH10_MB_FO_DEBUG_CMD_WO | WO | 0 | 直驱命令：1=启动（按 0x6D/0x6E 连续旋转） 2=停止（减速停机），执行后清零 |

互斥与安全：

- 直驱运行期间，切割引擎/调参手动运行/自动标定不得启动，反之亦然；
- 出现工具头异常（堵转/转速异常等）或进入 EXCEPTION 状态时自动停止；
- 上电默认停止；寄存器值易失，不擦写 flash。


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

仅在 bootloader 运行时有效，与 app 模式寄存器是相互独立的命名空间。bootloader 同时应答系统寄存器 0x18（0xA0A0）、0x19（复位魔数）、0x1D（0x0191），并将 0x1B 报为 0x0000（用于触发主控板版本不一致判定）。

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
| V1.3.0 | 2026/08/17 | 寄存器数组 0x20 → 0x50；新增前板电机/往复运动调参寄存器区 0x20~0x4F（8 档速度/减速区/电流/加速时间 + 全局位置参数 + 自动标定/手动运行命令与状态），供 box 电机调参页使用 |
| V1.4.0 | 2026/08/25 | 前板寄存器 0x0C（目标方向）扩展为三种切割模式：0=正转（连续旋转，默认）、1=反转（连续旋转）、2=往复（速度规划往复切割，即 V1.3.0 固件现有行为）。**Break**：0/1 语义由"往复起始方向"改为连续旋转方向，box 与固件须同步升级 |
| V1.5.0 | 2026/08/27 | 新增前板寄存器 0x12（MH10_MB_FO_ALARM_SUPPRESS_RW）异常检测屏蔽：bit0=1 时连续/往复转速判据与驱动器故障锁存不再置异常、不进 EXCEPTION 软停，仅保留日志；上电默认 0=检测开启，易失不擦 flash，持久化由 box 侧负责 |
| V1.6.0 | 2026/08/27 | 寄存器数组 0x50 → 0x70；新增前板正/反转电流曲线调节区 0x50~0x6C（DM2C522/DM2C556 × 正转/反转 共四套分段阶梯曲线，每套 3 速度阈值 + 4 档峰值电流），0x6C 为支持标识（0xC0DE），供 box 正反转校准页使用 |
| V1.7.0 | 2026/08/28 | 新增前板调试直驱寄存器 0x6D~0x6F（0x6D 直驱转速 rpm / 0x6E 方向 0正转1反转 / 0x6F 命令 1启动2停止执行后清零）：独立于切割引擎与调参手动运行的连续旋转直驱，与切割/手动运行/自动标定互斥，异常自动停止，上电默认停止；0x6C 支持标识语义扩展为整个 0x50~0x6F 扩展区（曲线 + 调试直驱同一固件版本一并实现），REG_COUNT 保持 0x70 |
| V1.8.0 | 2026/08/28 | 新增前板自动退刀寄存器 0x13（MH10_MB_FO_AUTO_RETRACT_RW）：bit0=1 时运行中发生 `EXP_MOTOR_STOP` 堵转异常后，前板先停机再以安全低速反向旋转到切割窗口打开位置（HEAD_SWITCH 闭合沿后再走半个往复周期），随后仍上报堵转异常；上电默认 0=关闭，写入立即生效，易失不擦 flash；0x12 bit0=1 屏蔽检测时本功能不触发 |
| V1.9.0 | 2026/09/03 | 新增前板两段式加速寄存器 0x14~0x16（0x14 全力转速 rpm，量纲同 0x0B，默认 4500 / 0x15 全力上升时间 ms/1000rpm，对应 DM2C PR0 加速时间，默认 100 / 0x16 加速上升时间 ms/1000rpm，默认 1000）：连续旋转模式下，目标转速 ≤ 全力转速时用全力上升时间一步爬坡到位，目标转速 > 全力转速时先爬到全力转速、稳定 3 秒（固件固定常量）后再以加速上升时间爬到目标转速；仅连续旋转模式使用，往复模式不用；写 0 或越界固件回退默认值，易失不擦 flash（持久化由 box 侧 sys.ini 负责），后板不实现；REG_COUNT 保持 0x70 |
| V1.9.1 | 2026/09/03 | 新增前板寄存器 0x17（MH10_MB_FO_RAMP_STABLE_MS_RW）全力转速稳定时间：单位 ms，有效范围 100~3000，默认 3000——将 V1.9.0 两段式加速中固件固定的 3 秒稳定段改为寄存器可调；写 0 或越界固件回退默认值，易失不擦 flash（持久化由 box 侧负责），后板不实现，仅连续旋转模式使用；REG_COUNT 保持 0x70。注：协议版本号为 BCD 编码（(MAJOR<<8)|(MINOR<<4)|PATCH），MINOR 无法表达 10，故以 PATCH 升版 |

## 12. 引用与约束

- 主控板与工控板的参考固件必须通过 git submodule 引用本仓库。
- 禁止在板子参考固件中私自升版或修改协议定义。
- 所有寄存器地址、常量、缩放因子以 `include/mh10_protocol.h` 为准。
