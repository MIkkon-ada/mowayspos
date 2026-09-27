import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/ProjectDetailPage.tsx', import.meta.url), 'utf8')

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
