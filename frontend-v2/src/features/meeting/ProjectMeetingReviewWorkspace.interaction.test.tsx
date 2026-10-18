/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProjectMeetingReviewWorkspace, type ProjectMeetingDraft } from './ProjectMeetingReviewWorkspace'

const meetingDraft: ProjectMeetingDraft = {
  id: 1,
  project_id: 1,
  title: '项目周会',
  meeting_type: '周会',
  meeting_date: '2026-08-24',
  location: '线上会议',
  host: '主持人',
  participants: '参会者甲、参会者乙',
  organizer: '整理人',
  copied_to: '项目组',
  summary: '',
  publish_status: 'draft',
  agendaItems: [],
  decisions: [],
  completedItems: [],
  nextStageWork: [],
  risks: [],
  priorActionTracking: [],
}

afterEach(() => cleanup())

describe('project meeting review editing', () => {
  it('shows imported Word changes beside the work progress table and approves selected rows', () => {
    const onApproveAndApply = vi.fn()
    render(<ProjectMeetingReviewWorkspace
      projectContext={{
        projectId: 1, projectName: '客户项目', members: [],
        workstreams: [{ id: 10, title: '交付准备' }],
        keyTasks: [{ id: 20, workstreamId: 10, title: '梳理客户清单', status: '进行中',
          currentProgress: { summary: '已完成第一批', nextStep: '等待复核', sourceLabel: '个人提交' } }],
      }}
      meetingDraft={meetingDraft}
      meetingInfoEvidence={{}}
      openQuestions={[]}
      workProgressPreview={{ rows: [{
        workstream_id: 10, workstream_title: '交付准备', key_task_id: 20,
        key_task_title: '梳理客户清单', key_task_status: '进行中',
        related_facts: [{ fact_id: 'F001', fact_type: 'action_item', content: '完成第二批清单', delta_type: 'NEW_EXECUTION_SCHEDULE', reason: '本周安排' }],
        proposed: { next_step: '完成第二批清单' }, field_fact_ids: { next_step: ['F001'] },
        evidence: [], confidence: 0.9,
      }], unlinked_facts: [] }}
      scheduleChanges={[{
        id: 90, action: 'confirm_work_progress', keyTaskId: 20,
        title: '梳理客户清单', keyTaskTitle: '梳理客户清单', before: {}, proposed: { next_step: '完成第二批清单' },
        evidence: [], validationState: 'ready', executionStatus: 'pending',
      }]}
      isOwner
      onSaveDraft={vi.fn()}
      onPublish={vi.fn()}
      onApproveAndApply={onApproveAndApply}
      onApplyChanges={vi.fn()}
      onReturn={vi.fn()}
      onDownload={vi.fn()}
    />)

    const table = screen.getByRole('region', { name: '工作推进表审核预览' })
    expect(table.textContent).toContain('已完成第一批')
    expect(table.textContent).toContain('完成第二批清单')
    expect(table.textContent).toContain('交付准备')
    fireEvent.click(screen.getByRole('button', { name: '审核通过并同步推进表' }))
    expect(onApproveAndApply).toHaveBeenCalledWith([90])
  })

  it('explains an unlinked Word item and lets the reviewer keep it in the minutes', () => {
    const onReviewUnlinkedFacts = vi.fn()
    render(<ProjectMeetingReviewWorkspace
      projectContext={{ projectId: 1, projectName: '客户项目', members: [], workstreams: [{ id: 10, title: '交付准备' }], keyTasks: [{ id: 20, workstreamId: 10, title: '客户清单' }] }}
      meetingDraft={meetingDraft}
      meetingInfoEvidence={{}}
      openQuestions={[]}
      workProgressPreview={{ rows: [], unlinked_facts: [{ fact_id: 'F002', content: '整理内部知识库', fact_type: 'action_item', reason: '有两个可能的关键任务', disposition: 'needs_confirmation' }] }}
      scheduleChanges={[{
        id: 91, action: 'review_unlinked_fact', keyTaskId: 0, keyTaskTitle: '', title: '整理内部知识库',
        before: { fact_id: 'F002', content: '整理内部知识库', reason: '有两个可能的关键任务' }, proposed: { next_step: '整理内部知识库' },
        evidence: [], validationState: 'needs_review', executionStatus: 'pending',
      }]}
      isOwner onSaveDraft={vi.fn()} onPublish={vi.fn()} onApplyChanges={vi.fn()}
      onReviewUnlinkedFacts={onReviewUnlinkedFacts} onReturn={vi.fn()} onDownload={vi.fn()}
    />)

    expect(screen.getByText(/有两个可能的关键任务/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '标记为仅留纪要' }))
    expect(onReviewUnlinkedFacts).toHaveBeenCalledWith({ decision: 'minutes_only', proposal_ids: [91] })
    expect(screen.getByRole('button', { name: '发布会议纪要' }).hasAttribute('disabled')).toBe(false)
  })

  it('opens as a readable document and retains unsaved edits when editing is toggled', () => {
    const onSaveDraft = vi.fn()
    render(<ProjectMeetingReviewWorkspace
      projectContext={{ projectId: 1, projectName: '项目', members: [], workstreams: [], keyTasks: [] }}
      meetingDraft={meetingDraft}
      meetingInfoEvidence={{}}
      openQuestions={[]}
      scheduleChanges={[]}
      isOwner
      onSaveDraft={onSaveDraft}
      onPublish={vi.fn()}
      onApplyChanges={vi.fn()}
      onReturn={vi.fn()}
      onDownload={vi.fn()}
    />)

    expect(screen.getByRole('heading', { name: '项目周会 会议纪要' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: '会议纪要标题' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '编辑纪要' }))
    fireEvent.change(screen.getByRole('textbox', { name: '会议纪要标题' }), { target: { value: '修订周会' } })
    fireEvent.click(screen.getByRole('button', { name: '退出编辑' }))

    expect(screen.getByRole('heading', { name: '修订周会 会议纪要' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' }))
    expect((screen.getByRole('textbox', { name: '会议纪要标题' }) as HTMLInputElement).value).toBe('修订周会')

    fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
    expect(onSaveDraft).toHaveBeenCalledWith(expect.objectContaining({ title: '修订周会' }))
  })
})
