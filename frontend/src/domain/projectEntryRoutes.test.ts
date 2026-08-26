import { describe, expect, it } from 'vitest'
import { projectEditPath, projectOwnerSubmitPath } from './projectEntryRoutes'

describe('project entry routes', () => {
  it('keeps the owner plan workflow separate from basic project editing', () => {
    expect(projectOwnerSubmitPath(4)).toBe('/home/projects/4/owner-submit')
    expect(projectEditPath(4)).toBe('/home/projects?edit=4')
    expect(projectOwnerSubmitPath(4)).not.toBe(projectEditPath(4))
  })
})
