/* @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CurrentProgressCard } from './CurrentProgressCard'

afterEach(cleanup)

describe('CurrentProgressCard', () => {
  it('shows submitter separately from confirmation person, time, and source', () => {
    render(<CurrentProgressCard progress={{
      id: 1,
      summary: '已确认的正式进展',
      next_step: '',
      submitter: '汇报人甲',
      confirmed_by: '审核人乙',
      confirmed_at: '2026-10-19T10:30:00',
      source_label: '个人提交',
    }} />)

    expect(screen.getByText('提交人：汇报人甲')).toBeTruthy()
    expect(screen.getByLabelText('关键任务最新提交').querySelectorAll('p')[1].textContent).toBe('确认人：审核人乙 · 2026/10/19 10:30 · 个人提交')
    expect(screen.getByText('已确认的正式进展')).toBeTruthy()
  })
})
