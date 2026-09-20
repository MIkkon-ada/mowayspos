import { useState } from 'react'
import { createMemberChangeRequest } from '../../api/projects'
import { toast } from '../../utils/toast'
import type { Person, Project, ProjectMember } from '../../types'

type Props = {
  project: Project
  people: Person[]
  members: ProjectMember[]
  onClose: () => void
  onSuccess: () => void
}

/**
 * 申请添加成员弹窗（N8-P1-P1B）。
 * owner/project_ceo 发起，to_role 仅 member/coordinator。
 * project_ceo/super_admin 发起后端自动通过；owner 发起进入 pending。
 */
export function MemberChangeRequestModal({ project, people, members, onClose, onSuccess }: Props) {
  const [targetPersonId, setTargetPersonId] = useState<number | null>(null)
  const [toRole, setToRole] = useState<'member' | 'coordinator'>('member')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)

  // 已有相同角色的人，禁用选择
  const disabledIds = new Set(
    members.filter((m) => m.role === toRole).map((m) => m.person_id),
  )
  const activePeople = people.filter((p) => p.is_active !== false)

  async function handleSubmit() {
    if (targetPersonId === null) {
      toast.warning('请选择目标人员')
      return
    }
    if (!reason.trim()) {
      toast.warning('请填写申请原因')
      return
    }
    setLoading(true)
    try {
      const r = await createMemberChangeRequest(project.id, {
        target_person_id: targetPersonId,
        to_role: toRole,
        reason: reason.trim(),
      })
      if (r.status === 'approved') {
        toast.success('成员已添加。')
      } else {
        toast.success('成员添加申请已提交，等待企业教练审核。')
      }
      onSuccess()
    } catch (e: any) {
      toast.error(e?.message || '提交失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={() => !loading && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-[480px] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
          <div className="text-sm font-bold text-slate-800">申请添加成员 — {project.name}</div>
          <div className="text-xs text-slate-400 mt-0.5">提交后由企业教练审核（企业教练发起自动通过）</div>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">目标人员</label>
            <select
              value={targetPersonId ?? ''}
              onChange={(e) => setTargetPersonId(e.target.value ? Number(e.target.value) : null)}
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400/30"
            >
              <option value="">请选择人员…</option>
              {activePeople.map((p) => (
                <option key={p.id} value={p.id} disabled={disabledIds.has(p.id)}>
                  {p.name}
                  {p.department ? `（${p.department}）` : ''}
                  {disabledIds.has(p.id) ? ' · 已有该角色' : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">添加为</label>
            <select
              value={toRole}
              onChange={(e) => setToRole(e.target.value as 'member' | 'coordinator')}
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400/30"
            >
              <option value="member">协同成员</option>
              <option value="coordinator">统筹人</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">
              申请原因 <span className="text-red-400">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="说明为什么需要添加该成员…"
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-violet-400/30"
            />
          </div>
        </div>
        <div className="flex gap-2 px-6 pb-5 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="cursor-pointer flex-1 py-2 rounded-xl border border-slate-200 text-slate-500 text-sm hover:bg-slate-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="cursor-pointer flex-1 py-2 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}
          >
            {loading ? '提交中…' : '提交申请'}
          </button>
        </div>
      </div>
    </div>
  )
}
