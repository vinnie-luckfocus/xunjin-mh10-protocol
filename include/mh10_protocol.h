/*************************************************
Copyright (C),  2024-2034 , XJMDT. Co., Ltd.
File name: mh10_protocol.h
Author: Vinnie.Zhou
Version: V1.11.0
Date: 2026/09/10
Contact: zhoushizheng331@gmail.com
Description: Xunjin MH10 主控板与前后工控板 Modbus RTU 通信协议统一头文件。
             本文件为 C/C++ 双语言兼容，是主控板（a_box_app）与工控板
             （b_mini_board）之间协议定义的单一事实来源。
             任何一方引用本文件后，不得私自修改或升版协议。
*************************************************/
#ifndef MH10_PROTOCOL_H__
#define MH10_PROTOCOL_H__

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 协议版本（语义化版本，编码 (MAJOR<<8)|(MINOR<<4)|PATCH）。
 *
 * 当前为 V1.11.0，对应 0x01B0（前板调参区新增 0x47 连续模式启动助力
 * 峰值电流寄存器）。
 * V1.10.0 对应 0x01A0（前板速度→峰值电流曲线扩展区改为
 * 每 500 rpm 一个固定分段的新布局：18 段 × 4 套曲线，曲线区扩至
 * 0x50~0x97，支持标识 0x98，调试直驱区迁移至 0x99~0x9B，
 * REG_COUNT 0x70 → 0x9C）。
 * 注：V1.10.0 起 MINOR=10，低字节高半字节为 0xA（非 BCD 数字），
 * 主机须按 16 位原始值或与 MH10_PROTOCOL_VERSION 宏比较来判定版本，
 * 不得按 BCD 逐位解码。
 * 该值同步写入系统寄存器 MH10_MB_REG_PROTOCOL_VERSION。
 */
#define MH10_PROTOCOL_VERSION_MAJOR 1U
#define MH10_PROTOCOL_VERSION_MINOR 11U
#define MH10_PROTOCOL_VERSION_PATCH 0U
#define MH10_PROTOCOL_VERSION       \
    ((uint16_t)((MH10_PROTOCOL_VERSION_MAJOR << 8) | \
                (MH10_PROTOCOL_VERSION_MINOR << 4)  | \
                (MH10_PROTOCOL_VERSION_PATCH)))

/**
 * @brief Modbus 保持寄存器数组大小。
 *
 * V1.3.0 起从 0x20 扩展至 0x50（地址 0x00 ~ 0x4F）：
 * 0x00~0x1F 为原有业务/系统区，0x20~0x4F 为前板电机调参区
 * （后板不使用调参区，读返回 0、写忽略）。
 * V1.6.0 起扩展至 0x70（地址 0x00 ~ 0x6F）：0x50~0x6C 为前板
 * 正/反转电流曲线调节区，0x6D~0x6F 为调试直驱区。
 * V1.10.0 起扩展至 0x9C（地址 0x00 ~ 0x9B）：曲线区改为每 500 rpm
 * 一个固定分段（18 段 × 4 套，0x50~0x97），支持标识 0x98，
 * 调试直驱区迁至 0x99~0x9B。布局与 V1.9.x 不兼容，靠协议版本
 * 0x1D 与支持标识魔数 0x98 区分。
 */
#define MH10_MB_REG_COUNT 0x9CU

/**
 * @brief Modbus RTU 物理层参数。
 */
#define MH10_MODBUS_BAUDRATE      115200U
#define MH10_MODBUS_DATA_BITS     8U
#define MH10_MODBUS_PARITY        'N'
#define MH10_MODBUS_STOP_BITS     1U
#define MH10_MODBUS_DEFAULT_TIMEOUT_MS 100U
#define MH10_MODBUS_DEFAULT_RETRIES    2U

/**
 * @brief 在线检测常量。
 *
 * 主控板读取系统寄存器 MH10_MB_REG_CONST 期望返回该值。
 */
#define MH10_MODBUS_ONLINE_CONST  0xA0A0U

/**
 * @brief 复位寄存器安全魔数。
 *
 * 向 MH10_MB_REG_REBOOT 写入该值才触发下位机复位，防止误写。
 */
#define MH10_MODBUS_REBOOT_MAGIC  0x5A5AU

/**
 * @brief 进入 IAP bootloader 的安全魔数。
 *
 * 向 MH10_MB_REG_IAP_ENTER 写入该值，下位机置位备份寄存器标志并复位，
 * 复位后由 bootloader 接管串口等待固件下载。
 */
#define MH10_MODBUS_IAP_MAGIC     0xB007U

/**
 * @brief 从机地址分配。
 */
typedef enum {
    MH10_SLAVE_ID_BROADCAST     = 0x00,
    MH10_SLAVE_ID_MOTOR         = 0x01,
    MH10_SLAVE_ID_FRONT_BOARD   = 0x02,
    MH10_SLAVE_ID_BACK_BOARD    = 0x03,
    MH10_SLAVE_ID_ATTACH_MOTOR  = 0x04,
    MH10_SLAVE_ID_MAX
} mh10_slave_id_t;

/**
 * @brief Modbus 功能码。
 */
typedef enum {
    MH10_MB_FC_READ_HOLDING_REGISTERS   = 0x03,
    MH10_MB_FC_WRITE_SINGLE_REGISTER    = 0x06,
    MH10_MB_FC_WRITE_MULTIPLE_REGISTERS = 0x10,
} mh10_mb_function_code_t;

/**
 * @brief 系统公共寄存器（前后板均固定在这些地址）。
 */
typedef enum {
    MH10_MB_REG_IAP_ENTER         = 0x11, /*!< 写入 0xB007 进入 IAP bootloader（app 模式有效） */
    /* 前板专用寄存器，占用系统区 0x11 与 0x18 之间的空闲地址（后板不实现） */
    MH10_MB_FO_ALARM_SUPPRESS_RW  = 0x12, /*!< 前板异常检测屏蔽（V1.5.0）：bit0=1 屏蔽转速/驱动器
                                               异常检测（检测到异常仅打印日志，不置异常码、不进
                                               EXCEPTION 停机）；上电默认 0=检测开启，写入立即生效，
                                               易失不擦 flash（持久化由 box 侧负责） */
    MH10_MB_FO_AUTO_RETRACT_RW    = 0x13, /*!< 前板自动退刀使能（V1.8.0）：bit0=1 时运行中发生
                                               EXP_MOTOR_STOP 堵转异常后，前板先停机再以安全低速
                                               反向旋转，直至切割窗口到达打开位置（HEAD_SWITCH
                                               闭合沿后再走半个往复周期）后停止，随后仍上报堵转
                                               异常；上电默认 0=关闭，写入立即生效，易失不擦 flash
                                               （持久化由 box 侧负责）。0x12 bit0=1 屏蔽检测时本
                                               功能不触发（无检测就无异常） */
    /* 前板两段式加速参数（V1.9.0，仅连续旋转模式使用，往复模式不用）：
     * 目标转速 ≤ 全力转速（0x14）时，用全力上升时间（0x15）一步爬坡到位；
     * 目标转速 > 全力转速时，先用全力上升时间爬到全力转速，稳定
     * 0x17 指定的时间（V1.9.1 起可调，V1.9.0 固件为固定 3 秒）后再以
     * 加速上升时间（0x16）爬到目标转速。
     * 四个参数上电为默认值，写 0 或越界时固件回退默认值；写入立即生效，
     * 易失不擦 flash（持久化由 box 侧 sys.ini 负责）；后板不实现。 */
    MH10_MB_FO_FULL_POWER_SPEED_RW  = 0x14, /*!< 全力转速（V1.9.0）：两段式加速
                                                 第一段的目标转速，单位 rpm，量纲
                                                 同 0x0B 目标速度（设定转速）；
                                                 上电默认 4500 */
    MH10_MB_FO_FULL_POWER_RISE_RW   = 0x15, /*!< 全力上升时间（V1.9.0）：爬到全力
                                                 转速所用加速时间，单位 ms/1000rpm
                                                 （对应 DM2C PR0 加速时间）；
                                                 上电默认 100 */
    MH10_MB_FO_ACCEL_RISE_RW        = 0x16, /*!< 加速上升时间（V1.9.0）：全力转速
                                                 以上段（稳定 0x17 时间后）爬到
                                                 目标转速所用加速时间，单位
                                                 ms/1000rpm；上电默认 1000 */
    MH10_MB_FO_RAMP_STABLE_MS_RW    = 0x17, /*!< 全力转速稳定时间（V1.9.1）：爬到
                                                 全力转速后保持稳定、再进入加速
                                                 上升段的时间，单位 ms，有效范围
                                                 100~3000；上电默认 3000（即
                                                 V1.9.0 固件的固定 3 秒） */
    MH10_MB_REG_CONST             = 0x18, /*!< 常量标识，固定为 0xA0A0 */
    MH10_MB_REG_REBOOT            = 0x19, /*!< 写入 0x5A5A 触发复位 */
    MH10_MB_REG_HW_VERSION        = 0x1A, /*!< 硬件版本 */
    MH10_MB_REG_SW_VERSION        = 0x1B, /*!< 软件版本 */
    MH10_MB_REG_SVN_NUM           = 0x1C, /*!< SVN 版本号 */
    MH10_MB_REG_PROTOCOL_VERSION  = 0x1D, /*!< 协议版本 V1.11.0 -> 0x01B0 */
    MH10_MB_REG_GIT_HASH_HI       = 0x1E, /*!< 固件 git 提交号高 16 位（短哈希前 4 位 hex） */
    MH10_MB_REG_GIT_HASH_LO       = 0x1F, /*!< 固件 git 提交号低 16 位（短哈希第 5~8 位 hex） */
} mh10_mb_system_reg_t;

/**
 * @brief 前板寄存器映射。
 *
 * 地址范围 0x00 ~ 0x10，避免与系统寄存器 0x18 ~ 0x1F 重叠。
 */
typedef enum {
    MH10_MB_FO_TOOLHEAD_STATE_RO             = 0x00, /*!< 工具头运行状态 */
    MH10_MB_FO_TOOLHEAD_EXCEPTION_RW         = 0x01, /*!< 异常码 */
    MH10_MB_FO_TOOLHEAD_INFO_RO              = 0x02, /*!< 工具头型号信息 */
    MH10_MB_FO_TOOLHEAD_SPEED_RO             = 0x03, /*!< 工具头实际速度（缩放后） */
    MH10_MB_FO_TOOLHEAD_COUNT_RO             = 0x04, /*!< 工具头往复次数 */
    MH10_MB_FO_TOOLHEAD_POS_RO               = 0x05, /*!< 工具头位置百分比 */

    MH10_MB_FO_PEDAL_INSERT_RO               = 0x06, /*!< 踏板是否插入 */
    MH10_MB_FO_PEDAL_SWITCH_RO               = 0x07, /*!< 踏板开关状态 */
    MH10_MB_FO_TOOLHEAD_INSERT_RO            = 0x08, /*!< 工具头是否插入 */
    MH10_MB_FO_TOOLHEAD_SWITCH_RO            = 0x09, /*!< 工具头开关状态 */

    MH10_MB_FO_TOOLHEAD_STATE_RW             = 0x0A, /*!< 工具头目标状态 */
    MH10_MB_FO_TOOLHEAD_TARGET_SPEED_RW      = 0x0B, /*!< 目标速度 */
    MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW        = 0x0C, /*!< 目标方向/切割模式（mh10_toolhead_cut_mode_t） */
    MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO = 0x0D, /*!< 自检确认 */
    MH10_MB_FO_TOOLHEAD_READY_TO_START_WO    = 0x0E, /*!< 启动/吸引确认 */
    MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO       = 0x0F, /*!< 踏板延时配置 */
    MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW      = 0x10, /*!< 切割往复周期计数（两次 HEAD_SWITCH 闭合沿间编码器计数） */
} mh10_mb_front_reg_t;

/**
 * @brief 前板电机/往复运动调参寄存器区（V1.3.0 新增，0x20~0x4F）。
 *
 * 用途：box 系统信息"电机调参"页面对切割往复引擎参数在线调参、
 * 自动标定与手动档位运行。参数上电为固件定版默认值，写寄存器立即生效
 * （易失，不擦写 flash；持久化由 box 侧 sys.ini 负责）。
 * 详细设计见 b_mini_board 仓 docs/design-motor-tuning.md。
 *
 * 档位定义（数组下标 i = 0~7）：
 *   jog rpm（电机轴） 300/600/900/1200/1500/2000/2500/3000
 *   设定值（= jog×3）900/1800/2700/3600/4500/6000/7500/9000
 */
typedef enum {
    /* 档位参数组（i = 0~7，基址 + i） */
    MH10_MB_FO_TUNE_GEAR_SPEED_BASE   = 0x20, /*!< RW 档位全速段设定转速（8 个） */
    MH10_MB_FO_TUNE_GEAR_ZONE_BASE    = 0x28, /*!< RW 档位近顶减速区步数（8 个） */
    MH10_MB_FO_TUNE_GEAR_CURRENT_BASE = 0x30, /*!< RW 档位峰值电流 0.1A（8 个） */
    MH10_MB_FO_TUNE_GEAR_ACCEL_BASE   = 0x38, /*!< RW 档位加速时间 ms/1000rpm（8 个） */

    /* 往复位置/全局参数 */
    MH10_MB_FO_TUNE_DECEL        = 0x40, /*!< RW 减速时间 ms/1000rpm（全局），默认 30 */
    MH10_MB_FO_TUNE_START_SPEED  = 0x41, /*!< RW 起步段设定转速，默认 900（jog300） */
    MH10_MB_FO_TUNE_START_STEPS  = 0x42, /*!< RW 起步段步数，默认 12 */
    MH10_MB_FO_TUNE_SLOW_SPEED   = 0x43, /*!< RW 近顶爬行设定转速，默认 450（jog150） */
    MH10_MB_FO_TUNE_REV_EXTRA    = 0x44, /*!< RW 沿采信后延迟换向步数（贴顶微调），默认 4 */
    MH10_MB_FO_TUNE_CRAWL_ADJ_MAX = 0x45,/*!< RW 爬行自适应最大加步，默认 8 */
    MH10_MB_FO_TUNE_ESTOP_MS     = 0x46, /*!< RW 急停减速时间 ms，默认 60 */

    /* 连续模式启动助力（仅连续旋转模式使用，往复模式/后板不用） */
    MH10_MB_FO_BOOST_CURRENT_RW  = 0x47, /*!< RW 连续模式启动助力峰值电流（V1.11.0，
                                              单位 0.1A）：连续旋转模式起步/换向/升速
                                              时峰值电流先给本值保证启动力矩，爬坡到位
                                              并稳定 0x17 时长后恢复曲线查表正常电流；
                                              0（上电默认）= 用驱动器型号上限
                                              （522→22 / 556→26），有效范围 1~26，
                                              固件再按探测到的 DM2C 型号钳上限；
                                              写入立即生效，易失不擦 flash
                                              （持久化由 box 侧 sys.ini 负责） */

    /* 标定与手动运行 */
    MH10_MB_FO_TUNE_CMD          = 0x48, /*!< WO mh10_tune_cmd_t */
    MH10_MB_FO_TUNE_GEAR         = 0x49, /*!< RW 手动运行档位号 0~7 */
    MH10_MB_FO_TUNE_STATUS       = 0x4A, /*!< RO mh10_tune_status_t */
    MH10_MB_FO_TUNE_CYCLE_COUNTS_RO = 0x4B, /*!< RO 标定测得的往复周期计数（同步写 0x10） */
    MH10_MB_FO_TUNE_ZONE_WIDTH_RO   = 0x4C, /*!< RO 标定测得的闭合区宽度（步） */
    MH10_MB_FO_TUNE_LAST_CYCLE_MS_RO = 0x4D,/*!< RO 最近一个往复实测耗时 ms */
    MH10_MB_FO_TUNE_REV_STAT_RO     = 0x4E, /*!< RO 近 20 往复换向质量打包：
                                                 bit0-4 E（沿采信）数 /
                                                 bit5-9 F（固定点开关闭合）数 /
                                                 bit10-14 O（固定点开关未闭合）数 */
    MH10_MB_FO_TUNE_ERROR_RO        = 0x4F, /*!< RO mh10_tune_error_t 最近失败原因 */
} mh10_mb_front_tune_reg_t;

/**
 * @brief 前板正/反转电流曲线调节区（V1.6.0 新增，V1.10.0 改为固定分段布局）。
 *
 * 用途：box 系统维护"正反转校准"页面对连续旋转模式的 速度→峰值电流
 * 分段阶梯曲线在线调参。
 *
 * 曲线模型（V1.10.0 起）：不再有可变速度阈值，速度域按每
 * MH10_MB_FO_CURVE_SEG_RPM（500）rpm 一个固定分段，共
 * MH10_MB_FO_CURVE_SEG_NUM（18）段（工具头输出轴最大转速 9000 rpm =
 * 500×18）。段 i 覆盖转速区间 [500*i, 500*(i+1))，查表
 * seg = min((uint32_t)(speed/500), 17)，无插值，纯阶梯。
 *
 * 共四套曲线（驱动器型号 × 旋转方向）：
 *   DM2C522 正转 / DM2C522 反转 / DM2C556 正转 / DM2C556 反转。
 * 运行时按实际检测到的 DM2C 型号与当前方向选一套。
 *
 * 每套曲线占 MH10_MB_FO_CURVE_CUR_NUM（18）个寄存器（基址 + 0..17），
 * 全部为峰值电流 CUR[0..17]（单位 0.1A）。写入时固件全局钳制到
 * 1~26（0.1A~2.6A），再按曲线所属型号钳制上限：
 * 522 → 22（峰值 2.2A），556 → 26（允许放宽到 2.6A）。
 *
 * 默认值（正/反转相同，保持 V1.9.x 旧阶梯形状的等价映射：
 * 旧 speed<=1000 用 CUR[0..1]、<=4000 用 CUR[2..7]、<=7000 用
 * CUR[8..13]、否则 CUR[14..17]，见 MH10_CURVE_DEF_CUR_522/556）：
 *   522 电流 {16,16, 18×6, 20×6, 22×4}，556 电流 {18,18, 20×6, 23×6, 25×4}
 *
 * 写寄存器立即生效（易失，不擦写 flash；持久化由 box 侧 sys.ini 负责）。
 *
 * 兼容性：本布局与 V1.9.x（3 阈值 + 4 档电流，曲线区 0x50~0x6B，
 * 调试直驱区 0x6D~0x6F）**不兼容**——V1.9.x 及更早固件（REG_COUNT=0x70）
 * 读写 0x62 以外的新曲线地址返回非法地址异常（0x02）。主机先读协议
 * 版本寄存器 0x1D（本布局固件为 0x01A0）并读 0x98 支持标识魔数
 * MH10_CURVE_SUPPORT_MAGIC 判定新布局是否可用。
 */
typedef enum {
    MH10_MB_FO_CURVE_FWD_522_BASE = 0x50, /*!< RW DM2C522 正转曲线基址（0x50~0x61，CUR[0..17]） */
    MH10_MB_FO_CURVE_REV_522_BASE = 0x62, /*!< RW DM2C522 反转曲线基址（0x62~0x73） */
    MH10_MB_FO_CURVE_FWD_556_BASE = 0x74, /*!< RW DM2C556 正转曲线基址（0x74~0x85） */
    MH10_MB_FO_CURVE_REV_556_BASE = 0x86, /*!< RW DM2C556 反转曲线基址（0x86~0x97） */

    MH10_MB_FO_CURVE_SUPPORT_RO   = 0x98, /*!< RO 扩展区支持标识：支持 0x50~0x9B
                                               扩展区（电流曲线 + 调试直驱）的固件
                                               固定返回 MH10_CURVE_SUPPORT_MAGIC；
                                               旧固件读该地址返回非法地址异常，
                                               主机据此优雅降级 */
    /* 0x99~0x9B 为调试直驱区（V1.7.0 新增，V1.10.0 自 0x6D~0x6F 迁移至此），
     * 见 mh10_mb_front_debug_reg_t */
} mh10_mb_front_curve_reg_t;

/** @brief 单套曲线的峰值电流档数 / 寄存器总数（V1.10.0 起均为 18）。 */
#define MH10_MB_FO_CURVE_CUR_NUM   18U
#define MH10_MB_FO_CURVE_REG_NUM   18U

/** @brief 曲线分段参数：每段转速（工具头输出轴 rpm）与分段总数。 */
#define MH10_MB_FO_CURVE_SEG_RPM   500U   /*!< 每段 500 rpm，段 i 覆盖 [500i, 500(i+1)) */
#define MH10_MB_FO_CURVE_SEG_NUM   18U    /*!< 分段总数 = 9000/500，覆盖最大转速 9000 rpm */

/** @brief 峰值电流可调范围（单位 0.1A）：全局 1~26，再按型号钳制上限。 */
#define MH10_MB_FO_CURVE_CUR_MIN     1U   /*!< 0.1A */
#define MH10_MB_FO_CURVE_CUR_MAX_522 22U  /*!< DM2C-RS522 峰值 2.2A */
#define MH10_MB_FO_CURVE_CUR_MAX_556 26U  /*!< DM2C-RS556 允许放宽到 2.6A */

/** @brief 曲线调节支持标识魔数（读 MH10_MB_FO_CURVE_SUPPORT_RO）。 */
#define MH10_CURVE_SUPPORT_MAGIC   0xC0DEU

/**
 * @brief 速度→曲线段下标查表（V1.10.0 布局）：seg = min(speed/500, 17)。
 *
 * 段 i 的峰值电流为 CUR[i]（0.1A），覆盖转速 [500*i, 500*(i+1)) rpm；
 * speed ≥ 9000 时钳制到末段 CUR[17]。
 */
static inline uint8_t mh10_curve_seg_index(uint32_t speed)
{
    uint32_t seg = speed / MH10_MB_FO_CURVE_SEG_RPM;
    return (uint8_t)((seg < MH10_MB_FO_CURVE_SEG_NUM) ? seg
                                                      : (MH10_MB_FO_CURVE_SEG_NUM - 1U));
}

/**
 * @brief 曲线默认峰值电流数组（0.1A，18 段；正/反转相同）。
 *
 * 保持 V1.9.x 旧 3 阈值 + 4 档阶梯形状的等价映射：
 * 旧 speed<=1000（段 0~1）/ <=4000（段 2~7）/ <=7000（段 8~13）/
 * 否则（段 14~17）。供固件初始化与 box 侧持久化缺省使用：
 *   static const uint16_t def[MH10_MB_FO_CURVE_CUR_NUM] = MH10_CURVE_DEF_CUR_522;
 */
#define MH10_CURVE_DEF_CUR_522   {16U, 16U, 18U, 18U, 18U, 18U, 18U, 18U, \
                                  20U, 20U, 20U, 20U, 20U, 20U, 22U, 22U, 22U, 22U}
#define MH10_CURVE_DEF_CUR_556   {18U, 18U, 20U, 20U, 20U, 20U, 20U, 20U, \
                                  23U, 23U, 23U, 23U, 23U, 23U, 25U, 25U, 25U, 25U}

/**
 * @brief 前板调试直驱寄存器（V1.7.0 新增于 0x6D~0x6F，V1.10.0 迁移至 0x99~0x9B）。
 *
 * 用途：box 系统维护"调试模式"页面直接驱动电机连续旋转，完全独立于
 * 切割/往复状态机与调参手动档位运行（不占用 0x20~0x4F 调参区任何寄存器）。
 * 启动后电机按 0x99 设定转速、0x9A 方向持续连续旋转，直到收到停止命令；
 * 电流按曲线区对应方向/驱动器型号的曲线随速度下发。
 *
 * 互斥与安全：
 *  - 直驱运行期间，切割引擎/调参手动运行/自动标定不得启动，反之亦然；
 *  - 出现工具头异常（堵转/转速异常等）或进入 EXCEPTION 状态时自动停止；
 *  - 上电默认停止；寄存器值易失，不擦写 flash。
 *
 * 支持判定：与曲线区共用 0x98 支持标识（同一固件版本一并实现），
 * 旧固件写 0x99~0x9B 返回非法地址异常，主机据此优雅降级。
 */
typedef enum {
    MH10_MB_FO_DEBUG_SPEED_RW = 0x99, /*!< RW 直驱设定转速（工具头输出轴 rpm，
                                           与 0x0B 同刻度，固件钳制到安全范围） */
    MH10_MB_FO_DEBUG_DIR_RW   = 0x9A, /*!< RW 直驱方向：0=正转 1=反转，默认 0 */
    MH10_MB_FO_DEBUG_CMD_WO   = 0x9B, /*!< WO 直驱命令（mh10_debug_cmd_t），执行后清零 */
} mh10_mb_front_debug_reg_t;

/** @brief 调试直驱命令（写 MH10_MB_FO_DEBUG_CMD_WO）。 */
typedef enum {
    MH10_DEBUG_CMD_START = 1, /*!< 启动直驱（按 0x99/0x9A 连续旋转） */
    MH10_DEBUG_CMD_STOP  = 2, /*!< 停止直驱（减速停机） */
} mh10_debug_cmd_t;

/** @brief 调参命令（写 MH10_MB_FO_TUNE_CMD）。 */
typedef enum {
    MH10_TUNE_CMD_AUTO_CALIB   = 1, /*!< 自动标定：寻顶测闭合区 + 周期计数 */
    MH10_TUNE_CMD_MANUAL_START = 2, /*!< 手动运行启动（按 MH10_MB_FO_TUNE_GEAR 档位持续往复） */
    MH10_TUNE_CMD_MANUAL_STOP  = 3, /*!< 手动运行停止（当前往复到顶 ESTOP 停 0 位） */
    MH10_TUNE_CMD_RESTORE_DEFAULT = 4, /*!< 恢复定版默认参数 */
} mh10_tune_cmd_t;

/** @brief 调参状态（读 MH10_MB_FO_TUNE_STATUS）。 */
typedef enum {
    MH10_TUNE_STATUS_IDLE       = 0,
    MH10_TUNE_STATUS_CALIBRATING = 1,
    MH10_TUNE_STATUS_MANUAL_RUN  = 2,
    MH10_TUNE_STATUS_CALIB_DONE  = 3,
    MH10_TUNE_STATUS_FAILED      = 4,
} mh10_tune_status_t;

/** @brief 调参失败原因（读 MH10_MB_FO_TUNE_ERROR_RO）。 */
typedef enum {
    MH10_TUNE_ERROR_NONE       = 0,
    MH10_TUNE_ERROR_NO_CUTTER  = 1, /*!< 未插入切割器 */
    MH10_TUNE_ERROR_STALL      = 2, /*!< 堵转 */
    MH10_TUNE_ERROR_TIMEOUT    = 3, /*!< 超时 */
    MH10_TUNE_ERROR_NO_ZONE    = 4, /*!< 找不到闭合区 */
} mh10_tune_error_t;

/**
 * @brief 后板寄存器映射。
 */
typedef enum {
    MH10_MB_BK_VERSION_RO      = 0x00, /*!< 后板版本/存在标识 */
    MH10_MB_BK_NP_IS_RO        = 0x01, /*!< 入口侧负压 */
    MH10_MB_BK_NP_OS_RO        = 0x02, /*!< 出口侧负压 */
    MH10_MB_BK_TARGET_STATE_WO = 0x03, /*!< 负压目标状态 */
} mh10_mb_back_reg_t;

/**
 * @brief Flash 布局（STM32F103C8，64 KB，页 1 KB）。
 *
 * ┌────────────────────────────┬──────────────────┬────────┐
 * │ 区域                        │ 地址范围          │ 大小   │
 * ├────────────────────────────┼──────────────────┼────────┤
 * │ bootloader                  │ 0x08000000-1FFF  │ 8 KB   │
 * │ app                         │ 0x08002000-F7BF  │ ~54 KB │
 * │ app 版本块（app 有效标志）   │ 0x0800F7C0-F7FF  │ 64 B   │
 * │ 设备 ID 页（bootloader 保留）│ 0x0800F800-FFFF  │ 1 KB   │
 * └────────────────────────────┴──────────────────┴────────┘
 *
 * 版本块由主控板在升级时**最后**烧写：只有整块固件写完并校验通过后，
 * magic 才出现在 flash 中。bootloader 上电检查 magic，缺失则停留在
 * 下载模式，保证升级中途断电/复位不会启动残缺 app。
 */
#define MH10_FLASH_BASE             0x08000000UL
#define MH10_BL_BASE                0x08000000UL
#define MH10_BL_SIZE                0x2000UL   /*!< 8 KB */
#define MH10_APP_BASE               0x08002000UL
#define MH10_APP_END                0x0800F7FFUL /*!< app 区最后一字节（含版本块） */
#define MH10_APP_MAX_SIZE           (0x0800F800UL - MH10_APP_BASE) /*!< 55296 B */
#define MH10_VERSION_BLOCK_ADDR     0x0800F7C0UL /*!< app 区末尾 64 B */
#define MH10_VERSION_BLOCK_SIZE     64U
#define MH10_VERSION_BLOCK_MAGIC    0x4D483130UL /*!< ASCII "MH10" */
#define MH10_DEVICE_ID_PAGE_ADDR    0x0800F800UL /*!< 最后一页，IAP 不得擦除 */

/**
 * @brief app 版本块（固定位于 MH10_VERSION_BLOCK_ADDR，共 64 B）。
 *
 * 主控板升级前从板载 hex 同地址解析本结构，与总线上读到的
 * 0x1B/0x1E/0x1F 寄存器比对，不一致则触发升级。
 */
typedef struct {
    uint32_t magic;       /*!< MH10_VERSION_BLOCK_MAGIC，app 有效标志 */
    uint16_t board_id;    /*!< mh10_slave_id_t：0x02 前板 / 0x03 后板 */
    uint16_t sw_version;  /*!< 同 MH10_MB_REG_SW_VERSION */
    uint16_t svn_num;     /*!< 同 MH10_MB_REG_SVN_NUM */
    uint16_t git_hash_hi; /*!< 同 MH10_MB_REG_GIT_HASH_HI */
    uint16_t git_hash_lo; /*!< 同 MH10_MB_REG_GIT_HASH_LO */
    uint16_t struct_ver;  /*!< 版本块结构版本，当前为 1 */
    uint16_t reserved[24];/*!< 保留，填充 0xFF */
} mh10_version_block_t;   /* 4+2*6+2*24 = 64 B */

/**
 * @brief bootloader 模式寄存器映射（仅在 bootloader 运行时有效）。
 *
 * 与 app 模式寄存器是相互独立的命名空间：板子处于 bootloader 时只应答
 * 本表与系统寄存器 0x18/0x19/0x1D（0x1B 报 0x0000，用于触发版本不一致）。
 *
 * 升级流程（主控板为主机）：
 *  1. 读 0x00 应为 MH10_BL_MAGIC；否则（板子在 app 模式）先写
 *     MH10_MB_REG_IAP_ENTER=0xB007 让板子复位进入 bootloader。
 *  2. 写 0x04=固件长度(字节,≤MH10_APP_MAX_SIZE)、0x05=整图 CRC16，
 *     再写 0x03=MH10_BL_CMD_ERASE；轮询 0x01 直到 READY/ERROR。
 *  3. 逐块：写 0x06=块号（128 B/块），再 FC16 写 64 个寄存器到 0x10
 *     起始的数据窗口；FC16 应答即代表该块已烧入 flash（同步烧写）。
 *  4. 写 0x03=MH10_BL_CMD_VERIFY，bootloader 校验整图 CRC16，
 *     轮询 0x01 直到 DONE/ERROR。
 *  5. 写 0x03=MH10_BL_CMD_JUMP（或 0x19=0x5A5A 复位），板子启动新 app。
 */
typedef enum {
    MH10_BL_REG_MAGIC    = 0x00, /*!< RO bootloader 标识，固定 MH10_BL_MAGIC */
    MH10_BL_REG_STATUS   = 0x01, /*!< RO mh10_bl_status_t */
    MH10_BL_REG_ERROR    = 0x02, /*!< RO mh10_bl_error_t */
    MH10_BL_REG_CMD      = 0x03, /*!< WO mh10_bl_cmd_t */
    MH10_BL_REG_LENGTH   = 0x04, /*!< WO 固件总长度（字节），≤ MH10_APP_MAX_SIZE */
    MH10_BL_REG_CRC16    = 0x05, /*!< WO 整图 CRC16（Modbus 多项式，初值 0xFFFF） */
    MH10_BL_REG_BLOCK    = 0x06, /*!< WO 数据窗口目标块号（128 B/块） */
    MH10_BL_REG_PROGRESS = 0x07, /*!< RO 已烧写到的块数边界：写完块 N 后置为 N+1 */
    MH10_BL_REG_DATA     = 0x10, /*!< WO 数据窗口起始地址，64 个寄存器 = 128 B；
                                      寄存器值 = 镜像小端字节对：reg[k] = data[2k] | (data[2k+1] << 8)，
                                      整块数据 = 镜像 block*128 起的 128 B */
} mh10_bl_reg_t;

#define MH10_BL_MAGIC        0xB010U  /*!< bootloader 运行标识 */
#define MH10_BL_BLOCK_SIZE   128U     /*!< 数据窗口字节数（64 个寄存器） */
#define MH10_BL_REG_DATA_COUNT 64U    /*!< 数据窗口寄存器数（0x10~0x4F） */

typedef enum {
    MH10_BL_STATUS_IDLE     = 0, /*!< 上电/等待命令 */
    MH10_BL_STATUS_ERASING  = 1, /*!< 正在擦除 app 区 */
    MH10_BL_STATUS_READY    = 2, /*!< 擦除完成，可接收数据 */
    MH10_BL_STATUS_DONE     = 3, /*!< 校验通过，可跳转 */
    MH10_BL_STATUS_ERROR    = 4, /*!< 出错，见 MH10_BL_REG_ERROR */
} mh10_bl_status_t;

typedef enum {
    MH10_BL_ERROR_NONE      = 0,
    MH10_BL_ERROR_BAD_STATE = 1, /*!< 当前状态不允许该命令 */
    MH10_BL_ERROR_BAD_LEN   = 2, /*!< 长度越界 */
    MH10_BL_ERROR_FLASH     = 3, /*!< 擦除/烧写失败 */
    MH10_BL_ERROR_BAD_CRC   = 4, /*!< 整图 CRC16 校验失败 */
} mh10_bl_error_t;

typedef enum {
    MH10_BL_CMD_ERASE  = 0x0001, /*!< 按 0x04 长度擦除 app 区 */
    MH10_BL_CMD_VERIFY = 0x0002, /*!< 按 0x04/0x05 校验整图 CRC16 */
    MH10_BL_CMD_JUMP   = 0x5A5A, /*!< 跳转 app（复用复位魔数） */
} mh10_bl_cmd_t;

/**
 * @brief 前板工具头运行状态。
 */
typedef enum {
    MH10_TOOLHEAD_STATE_OFFLINE             = 0,
    MH10_TOOLHEAD_STATE_PEDAL_ONLY          = 1,
    MH10_TOOLHEAD_STATE_TOOLHEAD_ONLY       = 2,
    MH10_TOOLHEAD_STATE_ONLINE_WAIT_SELFCHECK = 3,
    MH10_TOOLHEAD_STATE_SELF_CHECK          = 4,
    MH10_TOOLHEAD_STATE_ONLINE_READY        = 5,
    MH10_TOOLHEAD_STATE_WAITTING            = 6,
    MH10_TOOLHEAD_STATE_RUNNING             = 7,
    MH10_TOOLHEAD_STATE_ATTRACTING          = 8,
    MH10_TOOLHEAD_STATE_EXCEPTION           = 9,
} mh10_toolhead_state_t;

/**
 * @brief 前板切割模式（写 MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW，V1.4.0 定义）。
 *
 * 注意语义变化：V1.3.0 固件中 0/1 表示"往复起始方向"，V1.4.0 起
 * 0/1 改为连续旋转方向，2 才是往复（即 V1.3.0 固件的现有行为）。
 * box 与固件须同步升级，默认值为 0（正转）。
 */
typedef enum {
    MH10_TOOLHEAD_CUT_MODE_FORWARD = 0, /*!< 正转（连续旋转，默认） */
    MH10_TOOLHEAD_CUT_MODE_REVERSE = 1, /*!< 反转（连续旋转） */
    MH10_TOOLHEAD_CUT_MODE_RECIP   = 2, /*!< 往复（速度规划往复切割） */
} mh10_toolhead_cut_mode_t;

/**
 * @brief 前板工具头异常码。
 */
typedef enum {
    MH10_TOOLHEAD_EXP_NONE              = 0,
    MH10_TOOLHEAD_EXP_READ_CARD         = 1,
    MH10_TOOLHEAD_EXP_TOOLHEAD_OFFLINE  = 2,
    MH10_TOOLHEAD_EXP_TOOLHEAD_SWITCH   = 3,
    MH10_TOOLHEAD_EXP_PEDAL_OFFLINE     = 4,
    MH10_TOOLHEAD_EXP_MOTOR_STOP        = 5,
    MH10_TOOLHEAD_EXP_MOTOR_SPEED       = 6,
    MH10_TOOLHEAD_EXP_MOTOR_DIR         = 7,
} mh10_toolhead_exception_t;

/**
 * @brief 后板负压目标状态。
 */
typedef enum {
    MH10_BACKBOARD_STATE_CALIBRATION = 0,
    MH10_BACKBOARD_STATE_CLOSED      = 1,
    MH10_BACKBOARD_STATE_OPEN        = 2,
} mh10_backboard_state_t;

/**
 * @brief 自检确认值。
 */
typedef enum {
    MH10_SELFCHECK_NOT_READY = 0,
    MH10_SELFCHECK_READY     = 1,
    MH10_SELFCHECK_SKIP      = 2,
} mh10_selfcheck_mode_t;

/**
 * @brief 运行确认值。
 */
typedef enum {
    MH10_RUN_NOT_READY  = 0,
    MH10_RUN_READY      = 1,
    MH10_ATTACH_READY   = 2,
} mh10_run_mode_t;

/**
 * @brief 数值缩放因子。
 *
 * 负压值：寄存器值 / -100.0f = 实际 kPa。
 * 工具头速度：寄存器值 * 100 = 实际 RPM（下位机 taskfrontboard.c 中 gRealSpeed / 100）。
 */
#define MH10_NP_SCALE_FACTOR      (-100.0f)
#define MH10_TOOLHEAD_SPEED_SCALE (100U)

/**
 * @brief 编译期检查：各寄存器最大值不超过数组大小。
 *
 * 使用简单的编译期断言，不依赖外部宏。
 */
#ifndef MH10_CTASSERT
#define MH10_CTASSERT_(pred, line) typedef char mh10_ct_assert_##line[(pred) ? 1 : -1]
#define MH10_CTASSERT(pred)        MH10_CTASSERT_(pred, __LINE__)
#endif

MH10_CTASSERT(MH10_MB_FO_TOOLHEAD_CYCLE_COUNTS_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_TUNE_ERROR_RO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_BK_TARGET_STATE_WO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_REG_IAP_ENTER < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_ALARM_SUPPRESS_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_AUTO_RETRACT_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_FULL_POWER_SPEED_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_FULL_POWER_RISE_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_ACCEL_RISE_RW < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_RAMP_STABLE_MS_RW < MH10_MB_REG_COUNT);
/* V1.10.0 曲线区/调试区布局：四套曲线首尾相接，支持标识与调试直驱紧随其后 */
MH10_CTASSERT(MH10_MB_FO_CURVE_CUR_NUM == MH10_MB_FO_CURVE_REG_NUM);
MH10_CTASSERT(MH10_MB_FO_CURVE_SEG_RPM * MH10_MB_FO_CURVE_SEG_NUM == 9000U);
MH10_CTASSERT(MH10_MB_FO_CURVE_FWD_522_BASE < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_REV_522_BASE < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_FWD_556_BASE < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_REV_556_BASE < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_FWD_522_BASE + MH10_MB_FO_CURVE_CUR_NUM ==
              MH10_MB_FO_CURVE_REV_522_BASE);
MH10_CTASSERT(MH10_MB_FO_CURVE_REV_522_BASE + MH10_MB_FO_CURVE_CUR_NUM ==
              MH10_MB_FO_CURVE_FWD_556_BASE);
MH10_CTASSERT(MH10_MB_FO_CURVE_FWD_556_BASE + MH10_MB_FO_CURVE_CUR_NUM ==
              MH10_MB_FO_CURVE_REV_556_BASE);
MH10_CTASSERT(MH10_MB_FO_CURVE_REV_556_BASE + MH10_MB_FO_CURVE_CUR_NUM ==
              MH10_MB_FO_CURVE_SUPPORT_RO);
MH10_CTASSERT(MH10_MB_FO_CURVE_SUPPORT_RO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_SUPPORT_RO + 1U == MH10_MB_FO_DEBUG_SPEED_RW);
MH10_CTASSERT(MH10_MB_FO_DEBUG_CMD_WO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_FO_CURVE_CUR_MIN <= MH10_MB_FO_CURVE_CUR_MAX_522);
MH10_CTASSERT(MH10_MB_FO_CURVE_CUR_MAX_522 <= MH10_MB_FO_CURVE_CUR_MAX_556);
MH10_CTASSERT(MH10_MB_REG_PROTOCOL_VERSION < MH10_MB_REG_COUNT);
MH10_CTASSERT(sizeof(mh10_version_block_t) == MH10_VERSION_BLOCK_SIZE);

#ifdef __cplusplus
}
#endif

#endif /* MH10_PROTOCOL_H__ */
