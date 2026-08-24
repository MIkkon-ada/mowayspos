import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('new meeting modal', () => {
  it('does not expose preset meeting-type cards or send a selected type to the Agent', () => {
    const source = fs.readFileSync('src/features/meeting/NewMeetingModal.tsx', 'utf8')

    expect(source).not.toContain('MEETING_TYPE_OPTIONS')
    expect(source).not.toContain('六类会议均使用通用会议纪要模板')
    expect(source).not.toContain('选择会议类型，补充任意会议材料后生成草稿')
    expect(source).toContain('createProjectMeetingDocumentRun(projectId, documentFile)')
  })

  it('does not include a compatibility meeting_type form value in the document-run request', () => {
    const source = fs.readFileSync('src/api/meetings.ts', 'utf8')

    expect(source).toContain('createProjectMeetingDocumentRun(projectId: number, file: File)')
    expect(source).not.toContain("form.append('meeting_type'")
  })

  it('uses reference-aligned meeting controls and default project-wide copy recipients', () => {
    const source = fs.readFileSync('src/features/meeting/NewMeetingModal.tsx', 'utf8')

    expect(source).toContain("copied_to: '项目全体成员'")
    expect(source).toContain('type="date"')
    expect(source).toContain('getProjectMembers(projectId)')
    expect(source).toContain("singleMemberField('主持人', 'host'")
    expect(source).toContain("singleMemberField('整理人', 'organizer'")
    expect(source).toContain('meeting-new-information-card')
    expect(source).toContain('meeting-new-material-card')
    expect(source).toContain('meeting-new-footer')
    expect(source).not.toContain('请选择会议类型')
  })
})
