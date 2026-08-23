import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project meeting review workspace', () => {
  it('keeps evidence on demand and hides empty review sections', () => {
    const source = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')

    expect(source).toContain('<details')
    expect(source).toContain('查看原文依据')
    expect(source).toContain("['meeting_date', '会议日期']")
    expect(source).not.toContain("['title', '会议主题']")
    expect(source).not.toContain("['meeting_type', '会议类型']")
    expect(source).not.toContain('TYPE_STYLE')
    expect(source).not.toContain('typeLabel(')
    expect(source).toContain('{openQuestions.length ?')
    expect(source).toContain('{scheduleChanges.length ?')
    expect(source).not.toContain('aria-label="项目上下文"')
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
