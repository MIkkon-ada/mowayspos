import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')

test('dashboard refreshes projects when it mounts and renders every fillable owner project', () => {
  assert.match(source, /const \{[^}]*reloadProjects[^}]*\} = useProject\(\)/)
  assert.match(source, /useEffect\(\(\) => \{\s*void reloadProjects\(\)\s*\}, \[reloadProjects\]\)/)
  assert.match(source, /const fillableProjects = projects\.filter/)
  assert.match(source, /\{fillableProjects\.length\} 个项目/)
  assert.match(source, /fillableProjects\.map\(\(p\) => \(/)
  assert.doesNotMatch(source, /fillableProjects\.slice\(/)
})
