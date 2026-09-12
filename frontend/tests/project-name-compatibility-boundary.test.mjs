import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const compatibilityPath = new URL('../src/compatibility/projectNames.ts', import.meta.url)
const identityPath = new URL('../src/domain/projectIdentity.ts', import.meta.url)

assert.ok(existsSync(compatibilityPath), 'project-name fallback requires an explicit compatibility module')
assert.ok(existsSync(identityPath), 'project identity requires a strict domain module')

const compatibility = source('../src/compatibility/projectNames.ts')
const identity = source('../src/domain/projectIdentity.ts')

assert.match(compatibility, /special_project/)
assert.doesNotMatch(identity, /special_project|related_special_project/)

console.log('project name compatibility boundary passed')
