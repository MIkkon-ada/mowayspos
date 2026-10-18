/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ExecutionPlanSidebar } from './ExecutionPlanSidebar'

const emptySummary = { total: 0, completed: 0, in_progress: 0, not_started: 0, delayed: 0 }

afterEach(cleanup)

describe('ExecutionPlanSidebar', () => {
  it('lets authorized plan managers create the first plan from the empty state', () => {
    const onAdd = vi.fn()
    render(<ExecutionPlanSidebar plans={[]} summary={emptySummary} canManage onAdd={onAdd} onOpen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '新增计划' }))
    expect(onAdd).toHaveBeenCalledOnce()
  })

  it('does not offer plan creation to users without management permission', () => {
    render(<ExecutionPlanSidebar plans={[]} summary={emptySummary} canManage={false} onAdd={vi.fn()} onOpen={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '新增计划' })).toBeNull()
  })
})
