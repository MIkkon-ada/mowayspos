/**
 * 角色常量单一来源。
 *
 * 系统角色 system_role —— 平台级身份，存入 people.system_role，英文键。
 *   DB 存英文键，展示用 SYSTEM_ROLE_LABELS 映射中文。
 *   旧中文值（组长CEO/超级管理员/普通成员）通过 normalizeSystemRole 兼容。
 * 项目角色 project_members.role —— 项目内身份，英文 key。
 */

// ── 系统角色（英文键）───────────────────────────────────────
export const SYSTEM_ROLE_NORMAL = 'normal_member'
export const SYSTEM_ROLE_CEO = 'company_ceo'
export const SYSTEM_ROLE_SUPER_ADMIN = 'super_admin'

export const SYSTEM_ROLES = [
  SYSTEM_ROLE_NORMAL,
  SYSTEM_ROLE_CEO,
  SYSTEM_ROLE_SUPER_ADMIN,
] as const

export type SystemRole = (typeof SYSTEM_ROLES)[number]

// 英文键 → 中文展示名
export const SYSTEM_ROLE_LABELS: Record<string, string> = {
  [SYSTEM_ROLE_NORMAL]: '普通成员',
  [SYSTEM_ROLE_CEO]: '公司CEO',
  [SYSTEM_ROLE_SUPER_ADMIN]: '超级管理员',
}

// 下拉框选项
export const SYSTEM_ROLE_OPTIONS: { value: SystemRole; label: string }[] =
  SYSTEM_ROLES.map((r) => ({ value: r, label: SYSTEM_ROLE_LABELS[r] }))

// 旧中文值 → 英文键（迁移兼容）
const LEGACY_ROLE_MAP: Record<string, string> = {
  '普通成员': SYSTEM_ROLE_NORMAL,
  '组长CEO': SYSTEM_ROLE_CEO,
  '公司CEO': SYSTEM_ROLE_CEO,
  '超级管理员': SYSTEM_ROLE_SUPER_ADMIN,
}

/** 英文键 → 中文展示名。 */
export function systemRoleLabel(role: string | null | undefined): string {
  return SYSTEM_ROLE_LABELS[role ?? ''] ?? '普通成员'
}

/** 任意输入归一化为合法系统角色英文键，非法值回落为 normal_member。 */
export function normalizeSystemRole(role: string | null | undefined): SystemRole {
  const value = (role ?? '').trim()
  if (value === SYSTEM_ROLE_CEO || value === SYSTEM_ROLE_SUPER_ADMIN || value === SYSTEM_ROLE_NORMAL) {
    return value as SystemRole
  }
  const mapped = LEGACY_ROLE_MAP[value]
  if (mapped) return mapped as SystemRole
  return SYSTEM_ROLE_NORMAL
}

// ── 项目角色 ────────────────────────────────────────────────
export const PROJECT_ROLE_KEYS = ['project_ceo', 'owner', 'coordinator', 'member'] as const
export type ProjectRoleKey = (typeof PROJECT_ROLE_KEYS)[number]

export const PROJECT_ROLE_LABELS: Record<ProjectRoleKey, string> = {
  project_ceo: '企业教练',
  owner: '项目负责人',
  coordinator: '统筹人',
  member: '协同成员',
}

export function getProjectRoleLabel(role: string): string {
  return (PROJECT_ROLE_LABELS as Record<string, string>)[role] ?? role
}

export function formatProjectRoleLabels(roles: readonly string[] | null | undefined): string {
  if (!roles || roles.length === 0) return ''
  return roles.map((role) => getProjectRoleLabel(role)).join(' / ')
}
