import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/context/ProjectContext.tsx', import.meta.url), 'utf8')

assert.match(
  source,
  /try\s*\{\s*const list = await getProjects\(\)[\s\S]*?\}\s*catch\s*\{[\s\S]*?projectsFromAuthMe\(fallbackUser\)/,
  'project loading must fall back to authenticated-session projects when /api/projects fails',
)

assert.match(source, /project_owner:\s*'owner'/)
assert.match(source, /project_coordinator:\s*'coordinator'/)
assert.match(source, /project_member:\s*'member'/)
assert.match(source, /user_roles:\s*normalizeAuthMeProjectRoles\(item\.roles\)/)

console.log('project context fallback contract passed')
