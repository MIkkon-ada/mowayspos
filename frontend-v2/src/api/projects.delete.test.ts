import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('draft project deletion API contract', () => {
  it('sends both destructive confirmations in the DELETE request body', () => {
    const clientSource = fs.readFileSync('src/api/client.ts', 'utf8')
    const projectsSource = fs.readFileSync('src/api/projects.ts', 'utf8')

    expect(clientSource).toContain("apiDelete<T>(path: string, body?: unknown)")
    expect(projectsSource).toContain('export function deleteProject')
    expect(projectsSource).toContain('confirm_name: confirmName, confirm_phrase: confirmPhrase')
  })
})
