import { describe, expect, it } from 'vitest'
import { canShowProjectSubmitAction } from './projectLifecycleStatus'

describe('canShowProjectSubmitAction', () => {
  it('allows owner submission only after dispatch or return', () => {
    expect(canShowProjectSubmitAction({ status: 'draft' })).toBe(false)
    expect(canShowProjectSubmitAction({ status: 'dispatched' })).toBe(true)
    expect(canShowProjectSubmitAction({ status: 'returned' })).toBe(true)
  })
})
