import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('personal key-task detail embeds the monthly plan workbench with scoped members and permissions', () => {
  const detail = read('src/pages/MyTaskDetailPage.tsx')

  assert.match(detail, /import \{ getProjectMembers \} from '..\/api\/projects'/)
  assert.match(detail, /import \{ MonthlyPlanWorkspace \} from '..\/components\/task-management\/MonthlyPlanWorkspace'/)
  assert.match(detail, /useProject\(\)/)
  assert.match(detail, /getProjectMembers\(scopedProjectId\)/)
  assert.match(detail, /defaultAssigneeId/)
  assert.match(detail, /canManageProjectWork/)
  assert.match(detail, /<MonthlyPlanWorkspace[\s\S]*?subtaskId=\{detail\.id\}[\s\S]*?defaultAssigneeId=\{defaultAssigneeId\}[\s\S]*?members=\{projectMembers\}[\s\S]*?canManage=\{canManageMonthlyPlans\}[\s\S]*?onChanged=\{reload\}/)
})
