import type { KeyboardEvent } from 'react'
import { FaLink, FaSearch, FaUserSlash } from 'react-icons/fa'
import type { AccountItem } from '../../api/accounts'
import { systemRoleLabel } from '../../domain/roles'
import type { Person } from '../../types'

export type PersonWithAccount = { person: Person; account: AccountItem | null }
export type AccountStatusFilter = 'all' | 'active' | 'disabled' | 'no_account'

type Props = {
  rows: PersonWithAccount[]
  query: string
  department: string
  accountStatus: AccountStatusFilter
  onQueryChange: (value: string) => void
  onDepartmentChange: (value: string) => void
  onAccountStatusChange: (value: AccountStatusFilter) => void
  onSelectPerson: (personId: number) => void
}

function accountStatusLabel(account: AccountItem | null) {
  if (!account) return '未创建账号'
  return account.status === 'active' ? '正常' : '已禁用'
}

export function PeopleManagementTable({ rows, query, department, accountStatus, onQueryChange, onDepartmentChange, onAccountStatusChange, onSelectPerson }: Props) {
  const departments = Array.from(new Set(rows.map(({ person }) => person.department?.trim()).filter((value): value is string => Boolean(value)))).sort((a, b) => a.localeCompare(b, 'zh-CN'))
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const visibleRows = rows.filter(({ person, account }) => {
    const matchedQuery = !normalizedQuery || `${person.name} ${account?.username ?? ''}`.toLocaleLowerCase().includes(normalizedQuery)
    const matchedDepartment = !department || person.department === department
    const matchedStatus = accountStatus === 'all' || (accountStatus === 'no_account' ? !account : account?.status === accountStatus)
    return matchedQuery && matchedDepartment && matchedStatus
  })

  function openByKeyboard(event: KeyboardEvent<HTMLTableRowElement>, personId: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectPerson(personId)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-[220px] flex-1 max-w-sm">
          <FaSearch size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索姓名或账号" className="w-full rounded-lg border border-slate-200 py-2 pl-8 pr-3 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100" />
        </label>
        <select aria-label="部门" value={department} onChange={(event) => onDepartmentChange(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none focus:border-sky-400">
          <option value="">全部部门</option>
          {departments.map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <select aria-label="账号状态" value={accountStatus} onChange={(event) => onAccountStatusChange(event.target.value as AccountStatusFilter)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none focus:border-sky-400">
          <option value="all">全部账号状态</option>
          <option value="active">正常</option>
          <option value="disabled">已禁用</option>
          <option value="no_account">未创建账号</option>
        </select>
        <span className="ml-auto text-xs text-slate-400">共 {visibleRows.length} 人</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full min-w-[780px] text-left text-sm">
          <thead className="bg-slate-50 text-xs font-medium text-slate-500">
            <tr>
              <th className="px-4 py-3">人员 / 账号</th>
              <th className="px-4 py-3">部门 · 岗位</th>
              <th className="px-4 py-3">系统角色</th>
              <th className="px-4 py-3">企业微信</th>
              <th className="px-4 py-3">账号状态</th>
              <th className="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {visibleRows.map(({ person, account }) => (
              <tr key={person.id} tabIndex={0} onClick={() => onSelectPerson(person.id)} onKeyDown={(event) => openByKeyboard(event, person.id)} className="cursor-pointer transition hover:bg-sky-50/70 focus:bg-sky-50 focus:outline-none">
                <td className="px-4 py-3">
                  <div className="font-semibold text-slate-800">{person.name}</div>
                  <div className="mt-0.5 text-xs text-slate-400">{account?.username || '未创建登录账号'}</div>
                </td>
                <td className="px-4 py-3 text-slate-600">
                  <div>{person.department || '未同步'}</div>
                  <div className="mt-0.5 text-xs text-slate-400">{person.position_title || '未同步'}</div>
                </td>
                <td className="px-4 py-3"><span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{systemRoleLabel(person.system_role)}</span></td>
                <td className="px-4 py-3">
                  {account?.wecom_userid || person.wecom_userid ? <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700"><FaLink size={10} />已绑定</span> : <span className="text-xs text-amber-600">待绑定</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium ${account?.status === 'disabled' ? 'text-red-600' : account ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {account?.status === 'disabled' && <FaUserSlash size={10} />}{accountStatusLabel(account)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right"><span className="text-xs font-semibold text-sky-700">查看详情</span></td>
              </tr>
            ))}
            {visibleRows.length === 0 && <tr><td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-400">暂无匹配人员</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
