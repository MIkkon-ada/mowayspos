import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectsMgmtSection.tsx', import.meta.url), 'utf8')
const parser = readFileSync(new URL('../src/features/settings/projectPlanImport.ts', import.meta.url), 'utf8')

test('project management uses the complete work plan parser and blocks invalid imports', () => {
  assert.match(source, /parseProjectPlanImportText/)
  assert.match(source, /importErrors/)
  assert.match(source, /重点工作 \{new Set/)
  assert.match(source, /关键任务 \{rows\.length\}/)
  assert.match(source, /errors\.length > 0/)
  assert.match(source, /work_area/)
  assert.match(parser, /目标与重点工作计划表/)
  assert.match(parser, /重点工作计划开始时间/)
  assert.match(parser, /currentWorkArea/)
})
