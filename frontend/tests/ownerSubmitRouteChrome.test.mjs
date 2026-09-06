import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/layouts/ProjectLayout.tsx', import.meta.url), 'utf8')
const workbench = readFileSync(new URL('../src/features/settings/OwnerSubmitModal.tsx', import.meta.url), 'utf8')

test('owner submit route uses the focused full-page canvas without global navigation chrome', () => {
  assert.match(source, /const isOwnerSubmitPage = \/\\\/owner-submit\$\/\.test\(location\.pathname\)/)
  assert.match(source, /isOwnerSubmitPage \? null : \(/)
})

test('owner submit canvas keeps the reference proportions for the header and two-column workbench', () => {
  assert.match(workbench, /owner-submit-workbench-header[^\n]*min-h-\[88px\][^\n]*px-8/)
  assert.match(workbench, /owner-submit-workbench-columns[^\n]*gap-6[^\n]*px-8[^\n]*py-6/)
  assert.match(workbench, /owner-submit-left-pane[^\n]*lg:w-\[360px\]/)
  assert.match(workbench, /owner-submit-b-split[^\n]*h-auto min-h-0/)
  assert.match(workbench, /owner-submit-workbench-footer[^\n]*min-h-\[72px\][^\n]*px-8/)
})
