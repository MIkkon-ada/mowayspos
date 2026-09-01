/* @vitest-environment jsdom */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ExecutionPlan, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { ExecutionPlanDetailDrawer } from './ExecutionPlanDetailDrawer'

const plan: ExecutionPlan = {
  id: 1,
  title: '完成关键任务 AI 拆解入口资料上传与分析能力',
  status: '未开始',
  assignee: '吴肖',
  assignee_id: 5,
  collaborator_ids: [],
  collaborators: [],
  start_date: '2026-07-08',
  due_kind: 'exact',
  due_date: '2026-07-09',
  due_label: null,
  due_reference_date: null,
  expected_output: '完成资料上传与 AI 分析能力并可验证',
  actual_output: '',
  completion_criteria: '资料可上传、分析结果可生成并经测试验证',
  progress_note: '',
  latest_progress: null,
  risk_dependency: '',
  is_archived: false,
}

const workspace = {
  timeline: [],
  achievements: [],
  issues: [],
  permissions: { can_submit_update: true, can_operate: true },
} as unknown as KeyTaskWorkspace

describe('ExecutionPlanDetailDrawer', () => {
  it('shows the approved task-plan detail sections and actions', () => {
    render(<ExecutionPlanDetailDrawer open plan={plan} workspace={workspace} onClose={vi.fn()} onSubmitUpdate={vi.fn()} onEdit={vi.fn()} onMarkCompleted={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: '任务计划详情' }).classList.contains('max-w-[480px]')).toBe(true)
    expect(screen.getByText('预期成果')).toBeTruthy()
    expect(screen.getByText('完成定义')).toBeTruthy()
    expect(screen.getByText('当前进展')).toBeTruthy()
    expect(screen.getByText('推进记录')).toBeTruthy()
    expect(screen.getByRole('button', { name: '提交更新' })).toBeTruthy()
  })
})
