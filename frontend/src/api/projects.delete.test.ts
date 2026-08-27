import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('draft project deletion API contract', () => {
  it('sends an exact-name confirmation in the DELETE request body', () => {
    const clientSource = fs.readFileSync('src/api/client.ts', 'utf8')
    const projectsSource = fs.readFileSync('src/api/projects.ts', 'utf8')

    expect(clientSource).toContain("apiDelete<T>(path: string, body?: unknown)")
    expect(projectsSource).toContain('export function deleteDraftProject')
    expect(projectsSource).toContain("apiDelete(`/api/projects/${projectId}`, { confirm_name: confirmName })")
  })
})
