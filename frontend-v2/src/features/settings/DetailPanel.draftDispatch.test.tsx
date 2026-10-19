/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DetailPanel } from './ProjectsMgmtSection'

afterEach(cleanup)

describe('project detail draft dispatch action', () => {
  it('shows dispatch as the next action when required initiation data is complete', () => {
    const onDispatch = vi.fn()
    render(<DetailPanel
      project={{
        id: 1, name: 'Project draft', status: 'draft', lifecycle_status: 'draft',
        objectives: '目标已录入', start_date: '2026-10-19', end_date: '',
        owners: ['PM'], coaches: ['Coach'], project_type: '博维内部项目',
      } as any}
      projectMembers={[]}
      tasks={[]}
      subtasks={[]}
      roles={{ isSuperAdmin: true, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: false }}
      onClose={vi.fn()}
      onEdit={vi.fn()}
      onDispatch={onDispatch}
      onOwnerSubmit={vi.fn()}
      onOpenApprovalMaterials={vi.fn()}
      onReturn={vi.fn()}
      onWorkProgress={vi.fn()}
      onOpenCloseFlow={vi.fn()}
      onOpenArchive={vi.fn()}
      wide
    />)

    expect(screen.getByText('项目核心信息已齐全；可下发给负责人，结束日期可待定。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '下发给负责人' }))
    expect(onDispatch).toHaveBeenCalledOnce()
  })
})
