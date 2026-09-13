import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const read = (relativePath) => readFileSync(path.resolve(here, relativePath), 'utf8')
const iconPath = path.resolve(here, '../src/components/icons/ChevronDownIcon.tsx')

test('unified dropdown chevron uses the reference selector geometry everywhere', () => {
  const icon = existsSync(iconPath) ? read('../src/components/icons/ChevronDownIcon.tsx') : ''
  const styles = read('../src/styles.css')
  const archive = read('../src/features/project-archive/ArchiveOverview.tsx')
  const detail = read('../src/features/meeting/MeetingDetailWorkspace.tsx')
  const voiceBinding = read('../src/features/voice-update/VoiceUpdateTaskBindingBar.tsx')
  const explicitChevronSources = [
    archive,
    detail,
    voiceBinding,
    read('../src/features/settings/AIModelDrawer.tsx'),
    read('../src/pages/ConfirmPage.tsx'),
  ]
  const defaultDisclosureSources = [
    read('../src/features/voice-update/VoiceUpdateTaskReportsSection.tsx'),
    read('../src/pages/MeetingPage.tsx'),
    read('../src/features/meeting/ProjectMeetingReviewWorkspace.tsx'),
    read('../src/features/settings/ProjectsMgmtSection.tsx'),
  ]

  assert.match(icon, /viewBox="0 0 24 24"/)
  assert.match(icon, /strokeWidth="2\.5"/)
  assert.match(icon, /<polyline points="6 9 12 15 18 9"/)
  assert.match(styles, /--dropdown-chevron-image/)
  assert.match(styles, /\.app-disclosure > summary::after/)
  assert.match(detail, /ChevronDownIcon/)
  assert.match(voiceBinding, /<ChevronDownIcon className="voice-update-binding-scope-arrow"/)
  assert.match(read('../src/features/settings/OwnerSubmitModal.tsx'), /owner-submit-picker-chevron/)
  assert.doesNotMatch(archive, /⌄|⌃/)
  explicitChevronSources.forEach((source) => assert.match(source, /ChevronDownIcon/))
  defaultDisclosureSources.forEach((source) => assert.match(source, /app-disclosure/))
})
