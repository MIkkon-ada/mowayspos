import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('Sidebar navigation styles', () => {
  it('does not mix border shorthand with an active left border', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/Sidebar.tsx'), 'utf8')

    expect(source).not.toMatch(/borderLeft:[\s\S]{0,500}border:\s*['"]none['"]/)
  })
})
