import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve('frontend/src/pages/ProjectDetailPage.tsx'), 'utf8')

assert.match(
  source,
  /const proj = await getProject\(projectId\)[\s\S]*?setProject\(proj\)[\s\S]*?Promise\.allSettled\(\[\s*getProjectMembers\(projectId\),\s*fetchTasks\(projectId\),/,
  'project existence must be loaded before optional detail data so one failed supplemental request cannot hide a valid project',
)

assert.match(
  source,
  /memberResult\.status === 'fulfilled'[\s\S]*?taskResult\.status !== 'fulfilled'/,
  'member and task requests must degrade independently when they fail',
)

assert.match(
  source,
  /try\s*\{\s*const batch = await fetchSubTasksBatch\(taskIds\)[\s\S]*?catch \(err\)/,
  'subtask loading must not make an already loaded project disappear',
)

console.log('project detail loading contract passed')
