import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const source = fs.readFileSync(path.resolve(process.cwd(), 'src/pages/CoordinatePage.tsx'), 'utf8')

assert.match(source, /import\s*\{\s*systemRoleLabel\s*\}\s*from\s*'\.\.\/domain\/roles'/)
assert.match(source, /const COMPANY_ROLE_CLS: Record<string, string> = \{[\s\S]*?normal_member:\s*'bg-sky-100 text-sky-700',[\s\S]*?company_ceo:\s*'bg-indigo-100 text-indigo-700',[\s\S]*?super_admin:\s*'bg-rose-100 text-rose-700',[\s\S]*?\}/, 'company roles must have distinct colors')
assert.match(source, /const companyRole = \{ label: systemRoleLabel\(p\.system_role\), cls: COMPANY_ROLE_CLS\[p\.system_role \?\? ''\] \?\? COMPANY_ROLE_CLS\.normal_member \}/, 'company role color must follow the system role')
assert.match(source, /const \{ label: roleLabel, cls: roleCls \} = selectedProjectId \? \(roleInProject \?\? companyRole\) : companyRole/)
assert.ok(!source.includes('roleInProject ?? getBestRole(p)'), 'project roles must not be the default card role')
assert.ok(!source.includes('负责专项'), 'member cards must not show the project duty summary row')
assert.match(source, /selectedProjectId\s*&&\s*\(\s*<div className="flex flex-wrap gap-1\.5 mt-2">[\s\S]*?\.filter\(\(r\) => r\.project\.id === selectedProjectId\)/, 'project role tags must require a selected project and be scoped to it')
assert.match(source, /className=\{`text-xs px-2 py-0\.5 rounded-full cursor-pointer transition-all hover:opacity-90 \$\{PROJ_ROLE_CLS\[r\.role\] \?\? 'bg-amber-100 text-amber-700'\}`\}/, 'project role tags must use role-specific colors')

console.log('coordinate company/project role contract passed')
