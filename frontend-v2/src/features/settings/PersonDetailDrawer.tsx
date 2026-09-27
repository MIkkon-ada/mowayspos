import { useEffect, useState } from 'react'
import { FaKey, FaLink, FaPowerOff, FaShieldAlt, FaTrash, FaUser } from 'react-icons/fa'
import type { AccountItem } from '../../api/accounts'
import type { Person } from '../../types'

type Props = {
  person: Person | null
  account: AccountItem | null
  roleOptions: Array<{ value: string; label: string }>
  busyAction: string
  onClose: () => void
  onSavePerson: (payload: { name: string; system_role: string }) => Promise<void>
  onCreateAccount: (payload: { username: string; password: string }) => Promise<void>
  onRenameAccount: (username: string) => Promise<void>
  onResetPassword: (password: string) => Promise<void>
  onToggleAccount: () => Promise<void>
  onUnbindWecom: () => Promise<void>
  onDeletePerson: () => Promise<void>
}

export function PersonDetailDrawer({ person, account, roleOptions, busyAction, onClose, onSavePerson, onCreateAccount, onRenameAccount, onResetPassword, onToggleAccount, onUnbindWecom, onDeletePerson }: Props) {
  const [name, setName] = useState('')
  const [systemRole, setSystemRole] = useState('')
  const [username, setUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [accountPassword, setAccountPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setName(person?.name || '')
    setSystemRole(person?.system_role || roleOptions[0]?.value || '')
    setUsername(account?.username || person?.name || '')
    setNewPassword('')
    setAccountPassword('')
    setError('')
  }, [person?.id, account?.id, account?.username, person?.name, person?.system_role, roleOptions])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busyAction) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [busyAction, onClose])

  if (!person) return null

  async function run(action: () => Promise<void>) {
    setError('')
    try {
      await action()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败，请稍后重试')
    }
  }

  function requirePassword(value: string) {
    if (value.length >= 6) return true
    setError('密码至少需要 6 位')
    return false
  }

  const wecomUserid = account?.wecom_userid || person.wecom_userid || ''
  const isBusy = Boolean(busyAction)

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30" role="presentation" onMouseDown={() => !isBusy && onClose()}>
      <aside aria-modal="true" aria-label={`${person.name}人员详情`} role="dialog" onMouseDown={(event) => event.stopPropagation()} className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <div className="flex items-center gap-2"><h2 className="text-lg font-bold text-slate-800">{person.name}</h2><span className={`rounded-full px-2 py-0.5 text-xs ${account?.status === 'disabled' ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700'}`}>{account?.status === 'disabled' ? '已禁用' : account ? '正常' : '未创建账号'}</span></div>
            <p className="mt-1 text-xs text-slate-400">{account?.username ? `账号：${account.username}` : '尚未创建登录账号'}</p>
          </div>
          <button type="button" onClick={onClose} disabled={isBusy} className="rounded-md px-2 py-1 text-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50" aria-label="关闭详情">×</button>
        </header>

        <main className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

          <section className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-4">
            <div className="flex items-center justify-between"><h3 className="font-semibold text-slate-800">企业微信身份</h3><span className="text-xs font-medium text-emerald-700">同步来源：企业微信</span></div>
            <dl className="mt-3 grid grid-cols-[88px_1fr] gap-y-2 text-sm"><dt className="text-slate-400">企业微信 ID</dt><dd className="font-medium text-slate-700">{wecomUserid || '待绑定'}</dd><dt className="text-slate-400">部门</dt><dd className="text-slate-700">{person.department || '未同步'}</dd><dt className="text-slate-400">岗位</dt><dd className="text-slate-700">{person.position_title || '未同步'}</dd></dl>
            {wecomUserid && account && <button type="button" disabled={isBusy} onClick={() => { if (window.confirm(`确认解绑「${account.username}」的企业微信 ID？解绑后该用户不能用企业微信登录。`)) void run(onUnbindWecom) }} className="mt-3 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-red-600 disabled:opacity-50"><FaLink size={10} />解绑企业微信</button>}
            {!wecomUserid && <p className="mt-3 text-xs text-amber-700">请通过页面顶部“拉取企微通讯录”完成匹配和绑定。</p>}
          </section>

          <section>
            <div className="flex items-center gap-2"><FaShieldAlt size={14} className="text-sky-600" /><h3 className="font-semibold text-slate-800">系统权限</h3></div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-500">姓名<input value={name} onChange={(event) => setName(event.target.value)} disabled={isBusy} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-50" /></label>
              <label className="text-xs font-medium text-slate-500">系统角色<select value={systemRole} onChange={(event) => setSystemRole(event.target.value)} disabled={isBusy} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-50">{roleOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            </div>
            <button type="button" disabled={isBusy || !name.trim()} onClick={() => void run(() => onSavePerson({ name: name.trim(), system_role: systemRole }))} className="mt-3 rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50">{busyAction === 'save-person' ? '处理中…' : '保存系统权限'}</button>
          </section>

          <section className="border-t border-slate-100 pt-5">
            <div className="flex items-center gap-2"><FaUser size={14} className="text-sky-600" /><h3 className="font-semibold text-slate-800">账号与安全</h3></div>
            {!account ? <div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-xs font-medium text-slate-500">账号名<input value={username} onChange={(event) => setUsername(event.target.value)} disabled={isBusy} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" /></label><label className="text-xs font-medium text-slate-500">初始密码<input type="password" value={accountPassword} onChange={(event) => setAccountPassword(event.target.value)} disabled={isBusy} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" /></label><button type="button" disabled={isBusy || !username.trim()} onClick={() => { if (requirePassword(accountPassword)) void run(() => onCreateAccount({ username: username.trim(), password: accountPassword })) }} className="w-fit rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{busyAction === 'create-account' ? '处理中…' : '创建登录账号'}</button></div> : <div className="mt-3 space-y-3"><label className="block text-xs font-medium text-slate-500">账号名<div className="mt-1 flex gap-2"><input value={username} onChange={(event) => setUsername(event.target.value)} disabled={isBusy} className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" /><button type="button" disabled={isBusy || !username.trim() || username === account.username} onClick={() => void run(() => onRenameAccount(username.trim()))} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 disabled:opacity-50">保存</button></div></label><label className="block text-xs font-medium text-slate-500">新密码<div className="mt-1 flex gap-2"><input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} disabled={isBusy} placeholder="至少 6 位" className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" /><button type="button" disabled={isBusy} onClick={() => { if (requirePassword(newPassword)) void run(() => onResetPassword(newPassword)) }} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 disabled:opacity-50"><FaKey size={11} />重置密码</button></div></label><button type="button" disabled={isBusy} onClick={() => { const next = account.status === 'active' ? '禁用' : '启用'; if (window.confirm(`确认${next}账号「${account.username}」？`)) void run(onToggleAccount) }} className={`inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-50 ${account.status === 'active' ? 'border-red-200 text-red-700 hover:bg-red-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'}`}><FaPowerOff size={12} />{busyAction === 'toggle-account' ? '处理中…' : account.status === 'active' ? '停用账号' : '启用账号'}</button></div>}
          </section>

          <details className="border-t border-slate-100 pt-5"><summary className="cursor-pointer text-sm font-medium text-slate-500">更多操作</summary><button type="button" disabled={isBusy} onClick={() => { if (window.confirm(`确认删除「${person.name}」？删除前必须先处理登录账号和项目成员关系。`)) void run(onDeletePerson) }} className="mt-3 inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"><FaTrash size={12} />{busyAction === 'delete-person' ? '处理中…' : '删除人员'}</button></details>
        </main>
      </aside>
    </div>
  )
}
