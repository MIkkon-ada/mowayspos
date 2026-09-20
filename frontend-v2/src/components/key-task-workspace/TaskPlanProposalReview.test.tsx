/* @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TaskPlanProposalReview } from './TaskPlanProposalReview'

const members = [
  { id: 1, project_id: 7, person_id: 11, person_name_snapshot: '吴肖', role: 'owner', note: '', joined_at: null },
]

const run = {
  id: 1, project_id: 7, key_task_id: 42, status: 'ready_for_review' as const, source_text: '由吴肖整理清单并交付清单。', model_code: 'fake',
  proposals: [{
    id: 2,
    plan: { title: '整理清单', expected_output: '清单', assignee_id: 11, collaborator_ids: [], status: '未开始' as const, start_date: null, due_date: null, completion_criteria: '' },
    evidence: { title: '整理清单', expected_output: '交付清单', assignee_id: '由吴肖' },
    validation: { state: 'ready' as const, errors: [] },
    status: 'ready' as const, reviewer_edit: {}, created_plan_id: null,
  }],
}

describe('TaskPlanProposalReview', () => {
  it('requires an explicit confirmation to apply selected ready drafts', () => {
    const onApply = vi.fn().mockResolvedValue(undefined)
    render(<TaskPlanProposalReview run={run} members={members} busy={false} onUpdate={vi.fn().mockResolvedValue(undefined)} onApply={onApply} />)

    expect(screen.getByText('可创建')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '确认创建已选计划（1）' }))
    expect(onApply).toHaveBeenCalledWith([2])
  })
})
