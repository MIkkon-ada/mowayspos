/* @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ExecutionPlan } from '../../api/keyTaskWorkspace'
import { ExecutionPlanTable } from './ExecutionPlanTable'

const plan: ExecutionPlan = {
  id: 1,
  title: '完成关键任务 AI 拆解入口资料上传与分析能力',
  status: '未开始',
  assignee: '吴肖',
  assignee_id: 5,
  collaborator_ids: [6],
  collaborators: ['郭熠彬'],
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

describe('ExecutionPlanTable', () => {
  it('uses a compact list and opens details only from the row action', () => {
    const onOpen = vi.fn()
    render(<ExecutionPlanTable plans={[plan]} summary={{ total: 1, completed: 0, in_progress: 0, not_started: 1 }} canManage={false} onAdd={vi.fn()} onOpen={onOpen} />)

    expect(screen.getByRole('columnheader', { name: '负责人' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: '协助人' })).toBeTruthy()
    expect(screen.queryByRole('columnheader', { name: /最新进展/ })).toBeNull()
    fireEvent.click(screen.getByText(plan.title))
    expect(onOpen).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: `查看任务计划：${plan.title}` }))
    expect(onOpen).toHaveBeenCalledWith(plan)
  })
})
