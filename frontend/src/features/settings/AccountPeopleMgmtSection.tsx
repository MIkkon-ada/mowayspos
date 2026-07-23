import { useEffect, useState } from 'react'
import { createAccount, fetchAccounts, resetAccountPassword, updateAccountStatus, bindAccountWecom, unbindAccountWecom, fetchWecomUsers, batchBindWecom, type AccountItem, type WecomUserItem } from '../../api/accounts'
import { fetchPeople, createPerson, updatePerson, deletePerson } from '../../api/people'
import type { Person } from '../../types'
import { Card, SectionTitle } from './settingsShared'
import { SYSTEM_ROLE_SUPER_ADMIN, SYSTEM_ROLE_NORMAL, SYSTEM_ROLE_OPTIONS, systemRoleLabel, normalizeSystemRole } from '../../domain/roles'
import { PeopleBatchImportModal } from './PeopleBatchImportModal'
import { toast } from '../../utils/toast'

export function AccountPeopleMgmtSection() {
  const [people, setPeople] = useState<Person[]>([])
  const [accounts, setAccounts] = useState<AccountItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [showBatchImport, setShowBatchImport] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState(SYSTEM_ROLE_NORMAL)
  const [newDept, setNewDept] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [createLoginAccount, setCreateLoginAccount] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<{ name: string; system_role: string; department: string }>({ name: '', system_role: SYSTEM_ROLE_NORMAL, department: '' })
  const [creating, setCreating] = useState(false)
  const [accountDraft, setAccountDraft] = useState<Record<number, { username: string; password: string }>>({})
  const [resetDraft, setResetDraft] = useState<Record<number, string>>({})
  const [wecomDraft, setWecomDraft] = useState<Record<number, string>>({})
  const [showWecomImport, setShowWecomImport] = useState(false)
  const [wecomUsers, setWecomUsers] = useState<WecomUserItem[]>([])
  const [wecomLoading, setWecomLoading] = useState(false)
  const [wecomSelected, setWecomSelected] = useState<Record<string, number | null>>({})
  const [wecomSaving, setWecomSaving] = useState(false)
  const [message, setMessage] = useState('')

  function loadAll() {
    setLoading(true)
    Promise.all([
      fetchPeople(),
      fetchAccounts().catch(() => [] as AccountItem[]),
    ]).then(([peopleRows, accountRows]) => {
      setPeople(peopleRows)
      setAccounts(accountRows)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadAll() }, [])

  function accountForPerson(personId: number) {
    return accounts.find((account) => account.person_id === personId)
  }

  function showMessage(text: string) {
    setMessage(text)
    window.setTimeout(() => setMessage(''), 2200)
  }

  async function handleCreate() {
    if (!newName.trim()) return
    if (createLoginAccount && newPassword.trim().length < 6) {
      toast.error('初始密码至少 6 位')
      return
    }
    setCreating(true)
    try {
      const person = await createPerson({ name: newName.trim(), system_role: newRole, department: newDept })
      let createdAccount: AccountItem | null = null
      if (createLoginAccount) {
        createdAccount = await createAccount({
          username: (newUsername || newName).trim(),
          password: newPassword.trim(),
          person_id: person.id,
          is_tech_admin: newRole === SYSTEM_ROLE_SUPER_ADMIN,
        })
      }
      setPeople((prev) => [...prev, person])
      if (createdAccount) setAccounts((prev) => [...prev, createdAccount])
      setNewName('')
      setNewRole(SYSTEM_ROLE_NORMAL)
      setNewDept('')
      setNewUsername('')
      setNewPassword('')
      setCreateLoginAccount(true)
      setShowNew(false)
      showMessage('人员已创建')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  async function handleSaveEdit(id: number) {
    const person = await updatePerson(id, {
      name: editForm.name,
      system_role: editForm.system_role,
      department: editForm.department,
    })
    setPeople((prev) => prev.map((item) => item.id === id ? { ...item, ...person } : item))
    setEditingId(null)
    showMessage('人员信息已保存')
  }

  async function handleCreateAccount(person: Person) {
    const draft = accountDraft[person.id] || { username: String(person.name || ''), password: '' }
    if (!draft.username.trim()) return toast.error('请输入账号名')
    if (draft.password.trim().length < 6) return toast.error('初始密码至少 6 位')
    try {
      const account = await createAccount({
        username: draft.username.trim(),
        password: draft.password.trim(),
        person_id: person.id,
        is_tech_admin: person.system_role === SYSTEM_ROLE_SUPER_ADMIN,
      })
      setAccounts((prev) => [...prev.filter((item) => item.id !== account.id), account])
      setAccountDraft((prev) => ({ ...prev, [person.id]: { username: '', password: '' } }))
      showMessage('登录账号已创建')
      loadAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '创建账号失败')
    }
  }

  async function handleResetPassword(account: AccountItem) {
    const password = resetDraft[account.id] || ''
    if (password.length < 6) return toast.error('新密码至少 6 位')
    await resetAccountPassword(account.id, password)
    setResetDraft((prev) => ({ ...prev, [account.id]: '' }))
    showMessage('密码已重置')
    loadAll()
  }

  async function handleToggleAccount(account: AccountItem) {
    const nextStatus = account.status === 'active' ? 'disabled' : 'active'
    if (nextStatus === 'disabled' && !window.confirm(`确认禁用账号「${account.username}」？禁用后该用户不能登录。`)) return
    const updated = await updateAccountStatus(account.id, nextStatus)
    setAccounts((prev) => prev.map((item) => item.id === updated.id ? updated : item))
    showMessage(nextStatus === 'active' ? '账号已启用' : '账号已禁用')
  }

  async function handleBindWecom(account: AccountItem) {
    const wecomUserid = (wecomDraft[account.id] || '').trim()
    if (!wecomUserid) return toast.error('请输入企业微信 ID')
    try {
      const updated = await bindAccountWecom(account.id, wecomUserid)
      setAccounts((prev) => prev.map((item) => item.id === updated.id ? updated : item))
      setWecomDraft((prev) => ({ ...prev, [account.id]: '' }))
      showMessage('企业微信 ID 已绑定')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '绑定失败')
    }
  }

  async function handleUnbindWecom(account: AccountItem) {
    if (!window.confirm(`确认解绑「${account.username}」的企业微信 ID？解绑后该用户不能用企业微信登录。`)) return
    try {
      const updated = await unbindAccountWecom(account.id)
      setAccounts((prev) => prev.map((item) => item.id === updated.id ? updated : item))
      showMessage('企业微信 ID 已解绑')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '解绑失败')
    }
  }

  async function handleLoadWecomUsers() {
    setShowWecomImport(true)
    setWecomLoading(true)
    try {
      const rows = await fetchWecomUsers()
      setWecomUsers(rows)
      // 初始化每行的选中账号：优先 preselect，否则 bound_account_id，否则 null
      const initial: Record<string, number | null> = {}
      rows.forEach((u) => {
        if (u.preselect_account_id) {
          initial[u.wecom_userid] = u.preselect_account_id
        } else if (u.bound_account_id) {
          initial[u.wecom_userid] = u.bound_account_id
        } else {
          initial[u.wecom_userid] = null
        }
      })
      setWecomSelected(initial)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '拉取企微通讯录失败')
      setShowWecomImport(false)
    } finally {
      setWecomLoading(false)
    }
  }

  async function handleBatchBindWecom() {
    const items: { account_id: number; wecom_userid: string }[] = []
    Object.entries(wecomSelected).forEach(([wecomUserid, accountId]) => {
      if (accountId) items.push({ account_id: accountId, wecom_userid: wecomUserid })
    })
    if (items.length === 0) {
      toast.warning('请至少选择一个要绑定的账号')
      return
    }
    setWecomSaving(true)
    try {
      const updated = await batchBindWecom(items)
      setAccounts((prev) => {
        const map = new Map(updated.map((a) => [a.id, a]))
        return prev.map((p) => map.get(p.id) ?? p)
      })
      setShowWecomImport(false)
      showMessage(`成功绑定 ${items.length} 个企业微信账号`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批量绑定失败')
    } finally {
      setWecomSaving(false)
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!window.confirm(`确认删除「${name}」？建议优先禁用账号，删除人员会影响项目成员关系。`)) return
    await deletePerson(id)
    setPeople((prev) => prev.filter((item) => item.id !== id))
    showMessage('人员已删除')
  }

  if (loading) return <Card><p className="text-sm text-slate-400 py-8 text-center">加载中...</p></Card>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <SectionTitle inline>人员与账号管理</SectionTitle>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowBatchImport(true)}
            className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-indigo-200 text-indigo-600 bg-indigo-50 hover:bg-indigo-100">
            批量导入人员
          </button>
          <button type="button" onClick={handleLoadWecomUsers}
            className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-emerald-200 text-emerald-600 bg-emerald-50 hover:bg-emerald-100">
            拉取企微通讯录
          </button>
          <button type="button" onClick={() => setShowNew(true)}
            className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-xs font-semibold"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
            新建人员
          </button>
        </div>
      </div>

      {message && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">{message}</div>}

      {showBatchImport && (
        <PeopleBatchImportModal
          onClose={() => setShowBatchImport(false)}
          onDone={() => {
            loadAll()
            setShowBatchImport(false)
          }}
        />
      )}

      {showWecomImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-800">企业微信通讯录</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {wecomLoading ? '加载中…' : `共 ${wecomUsers.length} 位成员，系统已按姓名自动推荐绑定，可手动调整`}
                </p>
              </div>
              <button type="button" onClick={() => !wecomSaving && setShowWecomImport(false)}
                className="w-7 h-7 flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 16, height: 16 }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="overflow-auto px-5 py-4 flex-1">
              {wecomLoading ? (
                <div className="text-center text-slate-400 py-12">加载中…</div>
              ) : wecomUsers.length === 0 ? (
                <div className="text-center text-slate-400 py-12">没有通讯录数据</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                      <th className="py-2 px-2 font-semibold">企微 ID</th>
                      <th className="py-2 px-2 font-semibold">姓名</th>
                      <th className="py-2 px-2 font-semibold">绑定到系统账号</th>
                      <th className="py-2 px-2 font-semibold">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wecomUsers.map((u) => {
                      const sel = wecomSelected[u.wecom_userid]
                      const isRecommended = !u.bound_account_id && !!u.preselect_account_id && sel === u.preselect_account_id
                      return (
                        <tr key={u.wecom_userid} className="border-b border-slate-50 hover:bg-slate-50/50">
                          <td className="py-2 px-2 font-mono text-xs text-slate-700">{u.wecom_userid}</td>
                          <td className="py-2 px-2 text-slate-700">{u.wecom_name}</td>
                          <td className="py-2 px-2">
                            <select
                              value={sel ?? ''}
                              onChange={(e) => setWecomSelected((prev) => ({ ...prev, [u.wecom_userid]: e.target.value ? Number(e.target.value) : null }))}
                              className="border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none min-w-[140px]"
                            >
                              <option value="">不绑定</option>
                              {accounts.map((a) => (
                                <option key={a.id} value={a.id}>{a.username}{a.person_name ? `（${a.person_name}）` : ''}</option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 px-2">
                            {u.bound_account_id ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">已绑定 {u.bound_username}</span>
                            ) : isRecommended ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">推荐</span>
                            ) : sel ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">待绑定</span>
                            ) : (
                              <span className="text-xs text-slate-400">—</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
            <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100">
              <div className="text-xs text-slate-500">
                将绑定 {Object.values(wecomSelected).filter(Boolean).length} 个账号
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => !wecomSaving && setShowWecomImport(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 border border-slate-200 hover:bg-slate-50">
                  取消
                </button>
                <button type="button" onClick={handleBatchBindWecom}
                  disabled={wecomSaving || wecomLoading}
                  className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50">
                  {wecomSaving ? '保存中…' : '保存绑定'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showNew && (
        <Card>
          <p className="text-sm font-semibold text-slate-700 mb-3">新建人员与登录账号</p>
          <div className="flex items-center gap-2 flex-wrap">
            <input autoFocus value={newName} onChange={e => setNewName(e.target.value)}
              placeholder="姓名（必填）"
              className="w-32 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400" />
            <select value={newRole} onChange={e => setNewRole(e.target.value)}
              className="w-32 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30">
              {SYSTEM_ROLE_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
            <input value={newDept} onChange={e => setNewDept(e.target.value)}
              placeholder="部门（可选）"
              className="w-36 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400" />
            <label className="flex items-center gap-1.5 text-xs text-slate-600 px-2">
              <input type="checkbox" checked={createLoginAccount} onChange={e => setCreateLoginAccount(e.target.checked)} />
              同时创建登录账号
            </label>
            {createLoginAccount && (
              <>
                <input value={newUsername} onChange={e => setNewUsername(e.target.value)}
                  placeholder="账号名，默认同姓名"
                  className="w-40 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400" />
                <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  placeholder="初始密码，至少 6 位"
                  className="w-40 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400" />
              </>
            )}
            <button type="button" onClick={handleCreate} disabled={creating || !newName.trim()}
              className="cursor-pointer px-4 py-2 rounded-xl text-white text-sm font-semibold disabled:opacity-50" style={{ background: '#0369A1' }}>
              {creating ? '创建中...' : '创建'}
            </button>
            <button type="button" onClick={() => setShowNew(false)}
              className="cursor-pointer px-3 py-2 rounded-xl border border-slate-200 text-slate-500 text-sm">取消</button>
          </div>
        </Card>
      )}

      <Card>
        {people.length === 0 ? (
          <p className="text-sm text-slate-400 py-8 text-center">暂无人员</p>
        ) : (
          <div className="divide-y">
            {people.map((person) => {
              const account = accountForPerson(person.id)
              const draft = accountDraft[person.id] || { username: String(person.name || ''), password: '' }
              return (
                <div key={person.id} className="py-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                      style={{ background: person.is_active === false ? '#CBD5E1' : 'linear-gradient(135deg,#3B82F6,#0369A1)' }}>
                      {String(person.name || '?').slice(0, 1)}
                    </div>

                    {editingId === person.id ? (
                      <div className="flex-1 flex items-center gap-2 flex-wrap">
                        <input value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                          className="w-24 border border-sky-400 rounded-lg px-2 py-1 text-sm focus:outline-none" />
                        <select value={editForm.system_role} onChange={e => setEditForm(f => ({ ...f, system_role: e.target.value }))}
                          className="w-28 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none">
                          {SYSTEM_ROLE_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
                        </select>
                        <input value={editForm.department} onChange={e => setEditForm(f => ({ ...f, department: e.target.value }))}
                          placeholder="部门" className="w-28 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none" />
                        <button type="button" onClick={() => handleSaveEdit(person.id)}
                          className="cursor-pointer px-3 py-1 rounded-lg text-white text-xs font-semibold" style={{ background: '#0369A1' }}>保存</button>
                        <button type="button" onClick={() => setEditingId(null)}
                          className="cursor-pointer px-2 py-1 rounded-lg border border-slate-200 text-slate-500 text-xs">取消</button>
                      </div>
                    ) : (
                      <>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-slate-800">{person.name as string}</span>
                            {person.department && <span className="text-xs text-slate-400">{person.department as string}</span>}
                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">{systemRoleLabel(person.system_role)}</span>
                            {person.is_active === false && <span className="text-xs text-slate-400">已停用</span>}
                          </div>

                          {!account ? (
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">未创建登录账号</span>
                              <input value={draft.username} onChange={e => setAccountDraft(prev => ({ ...prev, [person.id]: { ...draft, username: e.target.value } }))}
                                placeholder="账号名" className="w-28 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none" />
                              <input type="password" value={draft.password} onChange={e => setAccountDraft(prev => ({ ...prev, [person.id]: { ...draft, password: e.target.value } }))}
                                placeholder="初始密码" className="w-28 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none" />
                              <button type="button" onClick={() => handleCreateAccount(person)}
                                className="px-2 py-1 rounded-lg text-xs font-semibold text-white" style={{ background: '#0369A1' }}>创建账号</button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              <span className="text-xs text-slate-500">账号：{account.username}</span>
                              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: account.status === 'active' ? '#DCFCE7' : '#F1F5F9', color: account.status === 'active' ? '#047857' : '#64748B' }}>
                                {account.status === 'active' ? '可登录' : '已禁用'}
                              </span>
                              <input type="password" value={resetDraft[account.id] || ''} onChange={e => setResetDraft(prev => ({ ...prev, [account.id]: e.target.value }))}
                                placeholder="新密码" className="w-24 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none" />
                              <button type="button" onClick={() => handleResetPassword(account)}
                                className="px-2 py-1 rounded-lg text-xs font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50">重置密码</button>
                              <button type="button" onClick={() => handleToggleAccount(account)}
                                className="px-2 py-1 rounded-lg text-xs font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50">
                                {account.status === 'active' ? '禁用账号' : '启用账号'}
                              </button>
                            </div>
                          )}

                          {account && (
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              <span className="text-xs text-slate-500">企微：</span>
                              {account.wecom_userid ? (
                                <>
                                  <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">{account.wecom_userid}</span>
                                  <button type="button" onClick={() => handleUnbindWecom(account)}
                                    className="px-2 py-1 rounded-lg text-xs font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50">解绑</button>
                                </>
                              ) : (
                                <>
                                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">未绑定</span>
                                  <input value={wecomDraft[account.id] || ''} onChange={e => setWecomDraft(prev => ({ ...prev, [account.id]: e.target.value }))}
                                    placeholder="输入企业微信 ID" className="w-32 border border-slate-200 rounded-lg px-2 py-1 text-xs focus:outline-none" />
                                  <button type="button" onClick={() => handleBindWecom(account)}
                                    className="px-2 py-1 rounded-lg text-xs font-semibold border border-emerald-200 text-emerald-600 bg-emerald-50 hover:bg-emerald-100">绑定</button>
                                </>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button type="button"
                            onClick={() => { setEditingId(person.id); setEditForm({ name: person.name as string, system_role: normalizeSystemRole(person.system_role as string), department: (person.department as string) || '' }) }}
                            className="cursor-pointer px-2 py-1 rounded-lg text-xs text-blue-600 hover:bg-blue-50">编辑</button>
                          <button type="button" onClick={() => handleDelete(person.id, person.name as string)}
                            className="cursor-pointer px-2 py-1 rounded-lg text-xs text-red-500 hover:bg-red-50">删除</button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
