import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('meeting list column layout', () => {
  it('shows only the essential meeting columns without a meeting-type filter', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

    expect(source).toContain('min-w-[940px]')
    expect(source).not.toContain('会议类型筛选')
    expect(source).not.toContain("width: '220px'")
    expect(source).not.toContain('TYPE_STYLE')
    expect(source).not.toContain('typeLabel(')
    expect(source).toContain("width: '150px'")
  })

  it('uses distinct API actions for publishing minutes and applying changes', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

    expect(source).toContain("action: 'publish'")
    expect(source).toContain("action: 'apply_changes'")
    expect(source).toContain('会议纪要已发布，项目计划尚未变更')
    expect(source).toContain('已回填选中的执行安排变更')
  })

  it('does not pass a preselected meeting type into the new-meeting flow', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

    expect(source).not.toContain('defaultMeetingType=')
    expect(source).not.toContain('urlMeetingType')
  })
})
