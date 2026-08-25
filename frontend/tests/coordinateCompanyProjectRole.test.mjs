import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const source = fs.readFileSync(path.resolve(process.cwd(), 'src/pages/CoordinatePage.tsx'), 'utf8')

assert.match(source, /import\s*\{\s*systemRoleLabel\s*\}\s*from\s*'\.\.\/domain\/roles'/)
assert.match(source, /const companyRole = \{ label: systemRoleLabel\(p\.system_role\), cls: 'bg-slate-100 text-slate-700' \}/)
assert.match(source, /const \{ label: roleLabel, cls: roleCls \} = selectedProjectId \? \(roleInProject \?\? companyRole\) : companyRole/)
assert.ok(!source.includes('roleInProject ?? getBestRole(p)'), 'project roles must not be the default card role')

console.log('coordinate company/project role contract passed')
