/**
 * 统一展示词典（第一阶段：用户可见命名收敛）
 *
 * 命名口径：
 * - 产品英文名：Moways-SOP
 * - 中文系统名：Moways 项目协同平台
 * - 案例名：博维 AI 升级项目驾驶舱（仅作项目/案例名称，不作系统通用名）
 * - 第二层业务对象：重点工作（技术字段 task）
 * - 第三层业务对象：关键任务（技术字段 subtask）
 * - AI 审核页面：AI 确认中心
 * - 汇报入口：工作汇报
 *
 * 边界：task / subtask 作为技术字段（表名、API 字段、类型名）保留不变，
 * 仅统一用户可见文案。接口字段名、数据库表名、路由路径、权限逻辑均不动。
 */

/** 产品英文名 */
export const PRODUCT_NAME_EN = 'Moways-SOP'

/** 中文系统名 */
export const SYSTEM_NAME_CN = 'Moways 项目协同平台'

/** 项目当前案例名（仅作为项目名称/案例名称，不作为系统通用名称） */
export const CASE_NAME = '博维 AI 升级项目驾驶舱'

/** 第二层业务对象展示名（技术字段：task） */
export const WORKSTREAM_LABEL = '重点工作'

/** 第三层业务对象展示名（技术字段：subtask） */
export const KEY_TASK_LABEL = '关键任务'

/** AI 审核页面名称 */
export const AI_CONFIRM_CENTER_LABEL = 'AI 确认中心'

/** 汇报入口名称 */
export const WORK_REPORT_LABEL = '工作汇报'
