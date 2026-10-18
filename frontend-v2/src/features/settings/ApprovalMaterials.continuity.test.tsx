/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApprovalMaterialsWorkbenchModal } from './ProjectsMgmtSection'

afterEach(cleanup)
const props = { project: { id: 4, name: '客户项目', status: 'pending_review', objectives: '完成交付' } as any,
  projectMembers: [], tasks: [], subtasks: [], canReview: true, loading: false,
  onClose: vi.fn(), onApprove: vi.fn(), onReturn: vi.fn() }

describe('approval data integrity', () => {
  it('collects return comments in the page without relying on native browser prompts', () => {
    const onReturn = vi.fn()
    render(<ApprovalMaterialsWorkbenchModal {...props} onReturn={onReturn} />)
    fireEvent.click(screen.getByRole('button', { name: '退回修改' }))
    fireEvent.change(screen.getByLabelText('退回意见'), { target: { value: '补充关键任务日期' } })
    fireEvent.click(screen.getByRole('button', { name: '确认退回' }))
    expect(onReturn).toHaveBeenCalledWith('补充关键任务日期')
  })
  it('shows retry and blocks approval when the plan cannot be loaded', () => {
    const retry = vi.fn()
    render(<ApprovalMaterialsWorkbenchModal {...props} planError="网络失败" onRetry={retry} />)
    expect(screen.getByText(/网络失败/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '审核通过' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '重新加载审核材料' }))
    expect(retry).toHaveBeenCalledOnce()
  })
  it('uses the same full-plan presentation with untruncated standards', () => {
    render(<ApprovalMaterialsWorkbenchModal {...props}
      tasks={[{ id: 10, key_task: '交付准备', key_achievement: '完整交付', completion_standard: '标准全文：客户逐项确认后验收', plan_process: '准备后验收' }] as any}
      subtasks={[{ id: 20, parent_task_id: 10, title: '检查清单', completion_criteria: '全部项目逐条检查' }] as any} />)
    expect(screen.getByLabelText('完整工作推进方案')).toBeTruthy()
    expect(screen.getByText('标准全文：客户逐项确认后验收')).toBeTruthy()
    expect(screen.getByText('全部项目逐条检查')).toBeTruthy()
  })
})
