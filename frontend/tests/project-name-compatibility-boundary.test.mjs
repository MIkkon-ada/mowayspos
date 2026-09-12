import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const compatibilityPath = new URL('../src/compatibility/projectNames.ts', import.meta.url)
const identityPath = new URL('../src/domain/projectIdentity.ts', import.meta.url)
const displayFacadePath = new URL('../src/domain/projectDisplay.ts', import.meta.url)

assert.ok(existsSync(compatibilityPath), 'project-name fallback requires an explicit compatibility module')
assert.ok(existsSync(identityPath), 'project identity requires a strict domain module')
assert.ok(!existsSync(displayFacadePath), 'compatibility callers must not depend on a domain display facade')

const compatibility = source('../src/compatibility/projectNames.ts')
const identity = source('../src/domain/projectIdentity.ts')
const taskPage = source('../src/pages/TaskManagementPage.tsx')
const taskExport = source('../src/utils/exportTasksExcel.ts')

assert.match(compatibility, /special_project/)
assert.match(compatibility, /compat-name:/)
assert.doesNotMatch(identity, /special_project|related_special_project/)

for (const [name, value] of [['task page', taskPage], ['task export', taskExport]]) {
  assert.match(value, /getProjectGroupKey/, `${name} must use the shared group-key adapter`)
  assert.doesNotMatch(value, /legacy:/, `${name} must not construct its own historical group key`)
  assert.doesNotMatch(value, /task\.special_project/, `${name} must not read a historical name directly`)
}

console.log('project name compatibility boundary passed')
