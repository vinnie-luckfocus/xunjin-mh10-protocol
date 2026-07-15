/*************************************************
Copyright (C),  2024-2034 , XJMDT. Co., Ltd.
File name: mh10_protocol.h
Author: Vinnie.Zhou
Version: V1.1.0
Date: 2026/07/15
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
 * 当前为 V1.1.0，对应 0x0110。
 * 该值同步写入系统寄存器 MH10_MB_REG_PROTOCOL_VERSION。
 */
#define MH10_PROTOCOL_VERSION_MAJOR 1U
#define MH10_PROTOCOL_VERSION_MINOR 1U
#define MH10_PROTOCOL_VERSION_PATCH 0U
#define MH10_PROTOCOL_VERSION       \
    ((uint16_t)((MH10_PROTOCOL_VERSION_MAJOR << 8) | \
                (MH10_PROTOCOL_VERSION_MINOR << 4)  | \
                (MH10_PROTOCOL_VERSION_PATCH)))

/**
 * @brief Modbus 保持寄存器数组大小。
 *
 * 与现有工程保持一致（32 个寄存器，地址 0x00 ~ 0x1F）。
 */
#define MH10_MB_REG_COUNT 0x20U

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
    MH10_MB_REG_CONST             = 0x18, /*!< 常量标识，固定为 0xA0A0 */
    MH10_MB_REG_REBOOT            = 0x19, /*!< 写入 0x5A5A 触发复位 */
    MH10_MB_REG_HW_VERSION        = 0x1A, /*!< 硬件版本 */
    MH10_MB_REG_SW_VERSION        = 0x1B, /*!< 软件版本 */
    MH10_MB_REG_SVN_NUM           = 0x1C, /*!< SVN 版本号 */
    MH10_MB_REG_PROTOCOL_VERSION  = 0x1D, /*!< 协议版本 V1.1.0 -> 0x0110 */
    MH10_MB_REG_RESERVED_1E       = 0x1E, /*!< 保留 */
    MH10_MB_REG_RESERVED_1F       = 0x1F, /*!< 保留 */
} mh10_mb_system_reg_t;

/**
 * @brief 前板寄存器映射。
 *
 * 地址范围 0x00 ~ 0x0F，避免与系统寄存器 0x18 ~ 0x1F 重叠。
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
    MH10_MB_FO_TOOLHEAD_TARGET_DIR_RW        = 0x0C, /*!< 目标方向 */
    MH10_MB_FO_TOOLHEAD_READY_TO_SELFCHECK_WO = 0x0D, /*!< 自检确认 */
    MH10_MB_FO_TOOLHEAD_READY_TO_START_WO    = 0x0E, /*!< 启动/吸引确认 */
    MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO       = 0x0F, /*!< 踏板延时配置 */
} mh10_mb_front_reg_t;

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

MH10_CTASSERT(MH10_MB_FO_TOOLHEAD_PEDAL_DELAY_WO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_BK_TARGET_STATE_WO < MH10_MB_REG_COUNT);
MH10_CTASSERT(MH10_MB_REG_PROTOCOL_VERSION < MH10_MB_REG_COUNT);

#ifdef __cplusplus
}
#endif

#endif /* MH10_PROTOCOL_H__ */
