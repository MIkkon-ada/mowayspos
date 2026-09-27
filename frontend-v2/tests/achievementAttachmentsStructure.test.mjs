import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/pages/AchievementsPage.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/achievements.ts', import.meta.url), 'utf8')

test('achievement attachment detail uses the attachment API contract and supported file picker', () => {
  for (const helper of ['fetchAchievementAttachments', 'uploadAchievementAttachment', 'downloadAchievementAttachment', 'deleteAchievementAttachment']) {
    assert.match(api, new RegExp(`function ${helper}`))
    assert.match(page, new RegExp(helper))
  }
  assert.match(api, /achievement_id=/)
  assert.match(api, /achievement_submission_id/)
  assert.match(page, /accept="\.pdf,\.doc,\.docx,\.xls,\.xlsx,\.ppt,\.pptx,\.jpg,\.jpeg,\.png,\.gif,\.webp,\.zip,\.rar"/)
})

test('achievement attachment detail exposes queue progress, retry, image preview, metadata, and download', () => {
  for (const token of ['attachmentQueue', 'item.progress', '重试', 'isPreviewableImage', 'attachment.original_name', 'attachment.size_bytes', 'attachment.uploaded_by', 'attachment.created_at', '下载']) {
    assert.match(page, new RegExp(token.replace('.', '\\.')))
  }
})

test('attachment uploads are scoped to the selected achievement and gated by maintenance ownership', () => {
  for (const token of ['selectedAchievementIdRef', 'uploadAbortControllers', 'AbortController', 'controller.abort()', 'selectedAchievementIdRef.current !== achievementId', 'canMaintainAttachments', 'canManageProjectWork', 'attachment.uploaded_by === currentUser?.name']) {
    assert.match(page, new RegExp(token.replaceAll('.', '\\.').replaceAll('?', '\\?').replaceAll('(', '\\(').replaceAll(')', '\\)')))
  }
  assert.match(api, /signal\?: AbortSignal/)
  assert.match(api, /xhr\.onabort/)
})
