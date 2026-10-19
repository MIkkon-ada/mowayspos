/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CurrentUser, Project } from '../types'
import { getNavigationEntries } from '../domain/navigationModel'
import { MobileAppNavigation } from './MobileAppNavigation'

afterEach(cleanup)

describe('work progress navigation', () => {
  it.each([{ projects: [] as Project[] }, { projects: [{ id: 9, name: '已归档的项目', status: 'archived' } as Project] }])(
    'keeps work progress directly accessible without an active project (%j)',
    ({ projects }) => {
      const navigate = vi.fn()
      const entries = getNavigationEntries({ name: '项目成员', system_role: 'normal_member' } as CurrentUser, ['member'], projects)
      render(<MobileAppNavigation activePage="mytasks" entries={entries} onNavigate={navigate} onChangePassword={vi.fn()} onLogout={vi.fn()} />)

      fireEvent.click(screen.getByRole('button', { name: /工作推进表/ }))
      expect(navigate).toHaveBeenCalledWith('table')
      expect(screen.queryByRole('dialog')).toBeNull()
    },
  )
})
