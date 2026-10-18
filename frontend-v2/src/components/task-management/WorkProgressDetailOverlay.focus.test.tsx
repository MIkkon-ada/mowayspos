/* @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WorkProgressDetailOverlay } from './WorkProgressDetailOverlay'

afterEach(cleanup)

describe('WorkProgressDetailOverlay focus management', () => {
  it('moves focus into the detail panel and restores it without scrolling on close', () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开任务详情'
    document.body.append(trigger)
    trigger.focus()

    const focus = vi.spyOn(trigger, 'focus')
    const view = render(<WorkProgressDetailOverlay onClose={() => {}}><h2>任务详情</h2></WorkProgressDetailOverlay>)
    const dialog = screen.getByRole('dialog', { name: '关键任务执行详情' })

    expect(document.activeElement).toBe(dialog)
    view.unmount()

    expect(document.activeElement).toBe(trigger)
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })
    trigger.remove()
  })
})
