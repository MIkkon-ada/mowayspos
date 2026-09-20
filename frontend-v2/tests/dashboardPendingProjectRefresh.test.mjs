import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')

test('dashboard refreshes projects but leaves project-init actions to project management', () => {
  assert.match(source, /const \{[^}]*reloadProjects[^}]*\} = useProject\(\)/)
  assert.match(source, /useEffect\(\(\) => \{\s*void reloadProjects\(\)\s*\}, \[reloadProjects\]\)/)
  assert.doesNotMatch(source, /待完善立项项目列表/)
  assert.doesNotMatch(source, /负责人填报横幅/)
  assert.doesNotMatch(source, /projectOwnerSubmitPath/)
})
