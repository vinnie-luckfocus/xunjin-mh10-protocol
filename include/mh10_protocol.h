/*************************************************
Copyright (C),  2024-2034 , XJMDT. Co., Ltd.
File name: mh10_protocol.h
Author: Vinnie.Zhou
Version: V1.4.0
Date: 2026/08/25
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
 * @brief 协议版本（语义化版本，BCD 编码）。
 *
 * 当前为 V1.4.0，对应 0x0140（前板寄存器 0x0C 目标方向正式定义为
 * 三种切割模式，见 mh10_toolhead_cut_mode_t）。
 * 该值同步写入系统寄存器 MH10_MB_REG_PROTOCOL_VERSION。
 */
#define MH10_PROTOCOL_VERSION_MAJOR 1U
#define MH10_PROTOCOL_VERSION_MINOR 4U
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
 * （后板不使用调参区，读返回 0、写忽略）。老版本主机不访问新区，向下兼容。
 */
#define MH10_MB_REG_COUNT 0x50U

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
    MH10_MB_REG_CONST             = 0x18, /*!< 常量标识，固定为 0xA0A0 */
    MH10_MB_REG_REBOOT            = 0x19, /*!< 写入 0x5A5A 触发复位 */
    MH10_MB_REG_HW_VERSION        = 0x1A, /*!< 硬件版本 */
    MH10_MB_REG_SW_VERSION        = 0x1B, /*!< 软件版本 */
    MH10_MB_REG_SVN_NUM           = 0x1C, /*!< SVN 版本号 */
    MH10_MB_REG_PROTOCOL_VERSION  = 0x1D, /*!< 协议版本 V1.1.0 -> 0x0110 */
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
MH10_CTASSERT(MH10_MB_REG_PROTOCOL_VERSION < MH10_MB_REG_COUNT);
MH10_CTASSERT(sizeof(mh10_version_block_t) == MH10_VERSION_BLOCK_SIZE);

#ifdef __cplusplus
}
#endif

#endif /* MH10_PROTOCOL_H__ */
