import { describe, expect, it } from 'vitest'
import type { Project } from '../../types'
import {
  getProjectLifecycleStage,
  getProjectMaterialChecklist,
  getProjectOverviewStats,
  getProjectTodo,
} from './projectsWorkbench'

const project = (status: Project['status'], overrides: Partial<Project> = {}): Project => ({
  id: 1,
  name: '项目 A',
  code: '',
  description: '',
  status,
  is_active: status === 'active',
  user_roles: [],
  member_counts: {},
  coordinator: '',
  owners: [],
  collaborators: [],
  coaches: [],
  ...overrides,
})

describe('projects workbench pure helpers', () => {
  it('groups overview counts without dropping statuses that have no card', () => {
    const result = getProjectOverviewStats([
      project('draft'),
      project('dispatched'),
      project('returned'),
      project('pending_review'),
      project('active'),
      project('pending_close'),
      project('ended'),
      project('archived'),
    ])
    expect(result).toEqual({ all: 8, toComplete: 2, toApprove: 1, active: 1, archived: 1 })
  })

  it('maps real statuses to business stages without creating startup status', () => {
    expect(getProjectLifecycleStage('dispatched')).toMatchObject({ key: 'planning', label: '立项准备阶段', activeIndex: 0 })
    expect(getProjectLifecycleStage('active')).toMatchObject({ key: 'execution', label: '执行阶段', activeIndex: 2 })
    expect(getProjectLifecycleStage('pending_close')).toMatchObject({ key: 'closing', activeIndex: 3 })
    expect(getProjectLifecycleStage('archived')).toMatchObject({ key: 'archive', activeIndex: 4 })
    expect(getProjectLifecycleStage('startup' as string)).toMatchObject({ key: 'planning', activeIndex: 0 })
  })

  it('returns the four frontend-only material checks', () => {
    const result = getProjectMaterialChecklist(project('dispatched'), [], [])
    expect(result).toEqual([
      { key: 'objectives', label: '项目目标', complete: false },
      { key: 'period', label: '项目周期', complete: false },
      { key: 'tasks', label: '重点工作', complete: false },
      { key: 'subtasks', label: '关键任务', complete: false },
    ])
    expect(getProjectMaterialChecklist(project('dispatched', {
      objectives: '目标', start_date: '2026-08-01', end_date: '2026-08-31',
    }), [{ id: 1 } as any], [{ id: 2 } as any])).toEqual([
      { key: 'objectives', label: '项目目标', complete: true },
      { key: 'period', label: '项目周期', complete: true },
      { key: 'tasks', label: '重点工作', complete: true },
      { key: 'subtasks', label: '关键任务', complete: true },
    ])
  })

  it('shows only role-authorized todo items', () => {
    expect(getProjectTodo(project('draft'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toBeNull()
    expect(getProjectTodo(project('draft'), {
      isSuperAdmin: false, isCompanyCeo: true, isRealProjectCeo: false, isRealOwner: false,
    }, [], [])).toMatchObject({ action: 'edit', actionLabel: '继续完善项目' })
    expect(getProjectTodo(project('dispatched'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toMatchObject({ action: 'ownerSubmit', actionLabel: '继续完善项目' })
    expect(getProjectTodo(project('returned'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toMatchObject({ action: 'ownerSubmit', actionLabel: '修改项目计划' })
    expect(getProjectTodo(project('pending_review'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: false,
    }, [], [])).toMatchObject({ action: 'approvalMaterials', actionLabel: '审核项目' })
    expect(getProjectTodo(project('pending_review'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toBeNull()
    for (const status of ['active', 'pending_close', 'ended', 'archived'] as const) {
      expect(getProjectTodo(project(status), {
        isSuperAdmin: true, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: true,
      }, [], [])).toBeNull()
    }
  })
})
