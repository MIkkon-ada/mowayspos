import { describe, expect, it } from 'vitest'
import { pendingMeetingRunStorageKey } from './pendingMeetingRunStorage'

describe('pending meeting run storage key', () => {
  it('scopes resumable runs by both project and authenticated account', () => {
    expect(pendingMeetingRunStorageKey(12, 'account:41'))
      .toBe(pendingMeetingRunStorageKey(12, 'account:41'))
    expect(pendingMeetingRunStorageKey(12, 'account:41'))
      .not.toBe(pendingMeetingRunStorageKey(12, 'account:42'))
    expect(pendingMeetingRunStorageKey(12, 'account:41'))
      .not.toBe(pendingMeetingRunStorageKey(13, 'account:41'))
  })
})
