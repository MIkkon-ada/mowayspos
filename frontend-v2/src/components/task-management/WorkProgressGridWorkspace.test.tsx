/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, TaskItem, SubTaskItem } from '../../types'
import { WorkProgressGridWorkspace } from './WorkProgressGridWorkspace'
import { fetchSubTasksBatch } from '../../api/subtasks'

vi.mock('../../api/subtasks', () => ({ fetchSubTasksBatch: vi.fn() }))

vi.mock('./WorkProgressGrid', () => ({ WorkProgressGrid: (props: { onChanges: (cells: unknown[]) => void; canEdit: boolean }) => <button disabled={!props.canEdit} onClick={() => props.onChanges([{ source: row, key: 'keyTask', value: '修订任务' }])}>模拟单元格编辑</button> }))
const row = { id: 20, task_id: 10, title: '原任务', assignee: '张三', status: '进行中', updated_at: '2026-10-19T09:00:00Z', edit_version: '2026-10-19T09:00:00.123456Z' } as SubTaskItem
const input = { project: { id: 1, name: '项目', status: 'active' } as Project, tasks: [{ id: 10, key_task: '重点工作' } as TaskItem], taskSubMap: { 10: [row] }, memberNames: ['张三'], storageScope: 'member:1', filters: { search: '', status: '', owner: '', quickFilter: 'all' as const }, onFiltersChange: vi.fn() }
afterEach(() => { cleanup(); localStorage.clear() })
describe('grid workspace', () => {
  it('keeps pending input after a failed save', async () => {
    render(<WorkProgressGridWorkspace {...input} onSave={vi.fn().mockRejectedValue(new Error('版本冲突'))} />)
    fireEvent.click(await screen.findByText('模拟单元格编辑'))
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('版本冲突'))
    expect(screen.getByText(/1 行待保存/)).toBeTruthy()
  })
  it('saves and restores a personal view and keeps other projects separate', () => {
    const view = render(<WorkProgressGridWorkspace {...input} />)
    fireEvent.change(screen.getByLabelText('分组方式'), { target: { value: 'owner' } })
    fireEvent.click(screen.getByRole('button', { name: '保存视图' }))
    fireEvent.change(screen.getByLabelText('视图名称'), { target: { value: '按负责人' } })
    fireEvent.click(screen.getByRole('button', { name: '确认保存视图' }))
    view.unmount()
    render(<WorkProgressGridWorkspace {...input} />)
    expect(screen.getByRole('button', { name: '按负责人' })).toBeTruthy()
    cleanup()
    render(<WorkProgressGridWorkspace {...input} storageScope="member:2" />)
    expect(screen.queryByRole('button', { name: '按负责人' })).toBeNull()
  })
  it('requires review before retrying against a newer server version', async () => {
    const onSave = vi.fn().mockRejectedValueOnce(new Error('版本冲突')).mockResolvedValue(undefined)
    vi.mocked(fetchSubTasksBatch).mockResolvedValue({ 10: [{ ...row, title: '其他人修改的任务', edit_version: '2026-10-19T10:00:00.123456Z' }] })
    render(<WorkProgressGridWorkspace {...input} onSave={onSave} />)
    fireEvent.click(await screen.findByText('模拟单元格编辑'))
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
    await screen.findByRole('alert')
    fireEvent.click(screen.getByRole('button', { name: '刷新并核对' }))
    await screen.findByRole('heading', { name: '其他人修改的任务', level: 3 })
    expect(onSave).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: '已核对，使用最新版本' }))
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(2))
    expect(onSave.mock.calls[1][0][0].expected_updated_at).toBe('2026-10-19T10:00:00.123456Z')
  })
})
