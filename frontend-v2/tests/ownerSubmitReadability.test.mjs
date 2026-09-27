import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/features/settings/OwnerSubmitModal.tsx', import.meta.url), 'utf8')
const styles = fs.readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')

test('owner submit editing controls keep readable text and affordances', () => {
  const liveRenderer = source.split('  /*')[0]

  assert.match(styles, /owner-submit-b-split input\[placeholder="请输入重点工作名称"\]::placeholder[\s\S]*color:\s*#667085/)
  assert.match(styles, /owner-submit-b-split input\[placeholder="请输入目标成果"\]::placeholder[\s\S]*color:\s*#667085/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table input::placeholder[\s\S]*color:\s*#667085/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table button\[aria-haspopup="listbox"\][\s\S]*color:\s*#667085/)
  assert.match(styles, /owner-submit-subtask-drag-handle[\s\S]*color:\s*#98a2b3/)
  assert.match(styles, /owner-submit-subtask-delete-icon[\s\S]*color:\s*#b0b8c5/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table tbody tr[\s\S]*height:\s*64px/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:first-child[\s\S]*width:\s*30%/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:nth-child\(2\)[\s\S]*width:\s*13%/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:nth-child\(3\)[\s\S]*width:\s*13%/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:nth-child\(4\)[\s\S]*width:\s*14%/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:nth-child\(5\)[\s\S]*width:\s*25%/)
  assert.match(styles, /owner-submit-b-split \.owner-submit-subtask-table th:last-child[\s\S]*width:\s*5%/)
  assert.match(liveRenderer, /owner-submit-subtask-delete-icon/)
  assert.doesNotMatch(liveRenderer, /owner-submit-subtask-delete-icon[^\n]*opacity-/)
})
