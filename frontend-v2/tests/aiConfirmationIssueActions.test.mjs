import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const cards = readFileSync(resolve(root, 'src/domain/confirmationTaskCards.ts'), 'utf8')
const page = readFileSync(resolve(root, 'src/pages/ConfirmPage.tsx'), 'utf8')

assert.match(cards, /escalatedIssueId:\s*number \| null/)
assert.match(cards, /escalated_issue_id/)
assert.match(page, /AiConfirmationIssueActions/)

console.log('AI confirmation issue action contract passed')
