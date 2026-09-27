import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('Sidebar navigation styles', () => {
  it('does not mix border shorthand with an active left border', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/Sidebar.tsx'), 'utf8')

    expect(source).not.toMatch(/borderLeft:[\s\S]{0,500}border:\s*['"]none['"]/)
  })

  it('uses the approved compact vertical density for expanded navigation', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/Sidebar.tsx'), 'utf8')

    expect(source).toContain('className="flex-1 px-2 py-3 xl:py-2 space-y-0.5 overflow-y-auto"')
    expect(source).toContain('className="pt-3 xl:pt-2"')
    expect(source).toContain('className="justify-center xl:justify-start px-2.5 py-2 xl:py-1.5"')
    expect(source).not.toContain("padding: '6px 10px'")
  })
})
