import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('issue helper assignment selects a project member and sends the stable person ID', () => {
  const api = source('../src/api/issues.ts')
  const detail = source('../src/pages/IssueDetailPage.tsx')
  const confirmation = source('../src/features/confirmations/AiConfirmationIssueActions.tsx')

  assert.match(api, /helper_person_id/)
  assert.match(detail, /promptProjectMember/)
  assert.match(confirmation, /promptProjectMember/)
})
