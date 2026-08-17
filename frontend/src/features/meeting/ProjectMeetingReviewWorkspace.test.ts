import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project meeting review workspace', () => {
  it('keeps evidence on demand and hides empty review sections', () => {
    const source = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')
    const minutesSource = fs.readFileSync('src/features/meeting/FormalProjectMeetingMinutes.tsx', 'utf8')

    expect(source).toContain('<details')
    expect(source).toContain('查看原文依据')
    expect(minutesSource).toContain("['meeting_date', '会议日期']")
    expect(minutesSource).not.toContain("['title', '会议主题']")
    expect(minutesSource).not.toContain("['meeting_type', '会议类型']")
    expect(source).toContain("import { TYPE_STYLE, typeLabel } from './meetingUtils'")
    expect(source).toContain('typeLabel(editableDraft.meeting_type)')
    expect(source).toContain('{openQuestions.length ?')
    expect(source).toContain('{scheduleChanges.length ?')
    expect(source).not.toContain('aria-label="项目上下文"')
    expect(source).not.toContain('lg:grid-cols-3')
    expect(source).not.toContain('本周已完成 / 行动项')
    expect(minutesSource).toContain('一、会议议程')
    expect(minutesSource).toContain('二、会议小结与决议')
    expect(minutesSource).toContain('三、待办事项跟踪')
    expect(minutesSource).toContain('会议安排事项')
    expect(minutesSource).toContain('{draft.risks.length ?')
    expect(minutesSource).toContain('hasStructuredActionFields')
  })

  it('separates publishing minutes from applying selected plan changes', () => {
    const source = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')

    expect(source).toContain('onPublish')
    expect(source).toContain('onApplyChanges')
    expect(source).toContain('发布会议纪要')
    expect(source).toContain('回填已选')
    expect(source).toContain("editableDraft.publish_status === 'published'")
    expect(source).not.toContain('项目负责人批准')
  })
})
