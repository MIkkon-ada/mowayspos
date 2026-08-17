import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('meeting list column layout', () => {
  it('keeps meeting time in a fixed readable column and clips only the meeting type label', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

    expect(source).toContain('min-w-[1040px]')
    expect(source).toContain("width: '220px'")
    expect(source).toContain('max-w-full')
    expect(source).toContain('truncate')
    expect(source).toContain("width: '150px'")
  })

  it('uses distinct API actions for publishing minutes and applying changes', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

    expect(source).toContain("action: 'publish'")
    expect(source).toContain("action: 'apply_changes'")
    expect(source).toContain('会议纪要已发布，项目计划尚未变更')
    expect(source).toContain('已回填选中的执行安排变更')
  })
})
