import { useEffect, useMemo, useState } from 'react'
import { fetchWecomDirectory, provisionWecomDirectoryAccounts, syncWecomDirectory, type WecomDirectoryPreviewItem, type WecomDirectoryProvisionResult } from '../../api/accounts'
import { toast } from '../../utils/toast'

type Props = {
  onClose: () => void
  onDone: () => void
  onProvisioned: () => void
}

const provisionConflictReason: Record<string, string> = {
  ambiguous_name: '本地存在同名人员',
  orphaned_account_binding: '企业微信已绑定到未关联人员的账号',
  userid_bound_to_other_account: '企业微信已绑定到其他账号',
  person_bound_to_other_userid: '本地人员已绑定其他企业微信身份',
  account_bound_to_other_userid: '本地账号已绑定其他企业微信身份',
  userid_bound_to_other_person: '企业微信身份已绑定其他人员',
}

export function WecomIdentitySyncModal({ onClose, onDone, onProvisioned }: Props) {
  const [items, setItems] = useState<WecomDirectoryPreviewItem[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [createPerson, setCreatePerson] = useState<Record<string, boolean>>({})
  const [provisionResult, setProvisionResult] = useState<WecomDirectoryProvisionResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchWecomDirectory().then((result) => {
      setItems(result.items)
      const initial: Record<string, boolean> = {}
      result.items.forEach((item) => { initial[item.userid] = item.match_type === 'exact' })
      setSelected(initial)
    }).catch((error) => {
      toast.error(error instanceof Error ? error.message : '读取企业微信通讯录失败')
      onClose()
    }).finally(() => setLoading(false))
  }, [])

  const selectedCount = useMemo(() => Object.values(selected).filter(Boolean).length, [selected])

  async function handleSync() {
    const payload = items.filter((item) => selected[item.userid]).map((item) => ({
      wecom_userid: item.userid,
      person_id: item.matched_person_id,
      create_person: item.match_type === 'new' && Boolean(createPerson[item.userid]),
    })).filter((item) => item.person_id || item.create_person)
    if (payload.length === 0) {
      toast.warning('请至少选择一个已匹配人员，或勾选新建人员')
      return
    }
    setSaving(true)
    try {
      const result = await syncWecomDirectory(payload)
      toast.success(`已同步 ${result.synced} 名人员的部门和岗位`)
      onDone()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '同步企业微信身份失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleProvisionAll() {
    setSaving(true)
    try {
      const result = await provisionWecomDirectoryAccounts()
      setProvisionResult(result)
      toast.success(`已同步 ${result.updated} 人，创建 ${result.created_people} 名人员和 ${result.created_accounts} 个账号`)
      onProvisioned()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '同步企业微信全员失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-5xl w-full max-h-[88vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-slate-800">同步企业微信部门与岗位</h3>
            <p className="text-xs text-slate-500 mt-1">企业微信只提供公司身份资料，不会修改系统权限或项目角色。</p>
          </div>
          <button type="button" onClick={() => !saving && onClose()} className="text-slate-400 hover:text-slate-700 text-xl">×</button>
        </div>
        <div className="overflow-auto px-5 py-4 flex-1">
          {loading ? <div className="py-12 text-center text-sm text-slate-400">正在读取企业微信通讯录…</div> : <>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                  <th className="py-2 px-2">同步</th>
                  <th className="py-2 px-2">人员</th>
                  <th className="py-2 px-2">企业微信部门</th>
                  <th className="py-2 px-2">企业微信岗位</th>
                  <th className="py-2 px-2">匹配状态</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const canSync = item.match_type !== 'conflict'
                  return (
                    <tr key={item.userid} className="border-b border-slate-50 align-top">
                      <td className="py-2 px-2">
                        <input type="checkbox" checked={Boolean(selected[item.userid])} disabled={!canSync} onChange={(event) => setSelected((current) => ({ ...current, [item.userid]: event.target.checked }))} />
                      </td>
                      <td className="py-2 px-2">
                        <div className="font-medium text-slate-700">{item.name}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{item.userid}</div>
                        {item.matched_person_name && <div className="text-[11px] text-slate-500">匹配：{item.matched_person_name}</div>}
                      </td>
                      <td className="py-2 px-2 text-slate-600">{item.department_path || '未填写'}</td>
                      <td className="py-2 px-2 text-slate-600">{item.position || '未填写'}</td>
                      <td className="py-2 px-2">
                        {item.match_type === 'exact' && <span className="text-xs text-emerald-700">已按企业微信 ID 匹配</span>}
                        {item.match_type === 'name_suggestion' && <span className="text-xs text-amber-700">姓名建议，请确认</span>}
                        {item.match_type === 'new' && (
                          <label className="flex items-center gap-1 text-xs text-blue-700">
                            <input type="checkbox" checked={Boolean(createPerson[item.userid])} onChange={(event) => setCreatePerson((current) => ({ ...current, [item.userid]: event.target.checked }))} />
                            新建本地人员
                          </label>
                        )}
                        {item.match_type === 'conflict' && <span className="text-xs text-red-600">姓名重复，需手动处理</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="mt-3 text-[11px] text-slate-500">
              确认同步后，企业微信同步后将覆盖系统中的部门和岗位；不会修改系统角色或项目角色。
            </p>
            {provisionResult && <div className="mt-3 rounded-lg border border-sky-100 bg-sky-50 p-3 text-xs text-slate-700">
              <div>已同步 {provisionResult.updated} 人；按姓名关联 {provisionResult.linked_by_name} 人；新建人员 {provisionResult.created_people} 名；新建账号 {provisionResult.created_accounts} 个。</div>
              {provisionResult.conflicts.length > 0 && <div className="mt-2 text-amber-700">需人工处理：{provisionResult.conflicts.map((item) => `${item.name || item.userid}（${provisionConflictReason[item.reason] || item.reason}）`).join('、')}</div>}
            </div>}
          </>}
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100">
          <span className="text-xs text-slate-500">已选择 {selectedCount} 人</span>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onClose} disabled={saving} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 border border-slate-200">取消</button>
            <button type="button" onClick={() => void handleProvisionAll()} disabled={loading || saving} className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-sky-700 disabled:opacity-50">{saving ? '同步中…' : '同步全员并创建账号'}</button>
            <button type="button" onClick={handleSync} disabled={loading || saving} className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 disabled:opacity-50">{saving ? '同步中…' : '确认同步'}</button>
          </div>
        </div>
        <p className="px-5 pb-3 text-[11px] text-slate-500">新账号用户名使用企微 ID，初始密码为 123456。</p>
      </div>
    </div>
  )
}
