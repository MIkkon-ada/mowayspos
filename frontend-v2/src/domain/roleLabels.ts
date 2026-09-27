// 角色标签统一来源已迁移至 domain/roles.ts，此处保留 re-export 以兼容现有引用。
// super_admin 不属于项目角色，已从标签表中移除。
export { PROJECT_ROLE_LABELS, getProjectRoleLabel, formatProjectRoleLabels } from './roles'
export type { ProjectRoleKey } from './roles'
