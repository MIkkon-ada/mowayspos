import { useEffect, useState } from 'react'
import {
  getMemberChangeRequests,
  approveMemberChangeRequest,
  rejectMemberChangeRequest,
} from '../../api/projects'
import { toast } from '../../utils/toast'
import type { MemberChangeRequest, Project } from '../../types'

type Props = {
  project: Project
  onClose: () => void
  onChanged: () => void
}

/**
 * 审核成员添加申请弹窗（N8-P1-P1B）。
 * 仅 project_ceo / super_admin 可见（入口由调用方控制）。
 * 列出 pending 申请，支持通过/拒绝。
 */
export function MemberChangeReviewModal({ project, onClose, onChanged }: Props) {
  const [list, setList] = useState<MemberChangeRequest[]>([])
  const [loading, setLoading] = useState(false)
  const [comments, setComments] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    try {
      const r = await getMemberChangeRequests(project.id, 'pending')
      setList(r)
    } catch {
      setList([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleApprove(rid: number) {
    setBusy(rid)
    try {
      await approveMemberChangeRequest(project.id, rid, { review_comment: comments[rid] || '' })
      toast.success('已通过成员添加申请。')
      onChanged()
      load()
    } catch (e: any) {
      toast.error(e?.message || '操作失败')
    } finally {
      setBusy(null)
    }
  }

  async function handleReject(rid: number) {
    const c = (comments[rid] || '').trim()
    if (!c) {
      toast.warning('拒绝请填写审核意见')
      return
    }
    setBusy(rid)
    try {
      await rejectMemberChangeRequest(project.id, rid, { review_comment: c })
      toast.success('已拒绝成员添加申请。')
      onChanged()
      load()
    } catch (e: any) {
      toast.error(e?.message || '操作失败')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-[560px] max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <div className="text-sm font-bold text-slate-800">审核成员添加申请 — {project.name}</div>
            <div className="text-xs text-slate-400 mt-0.5">仅企业教练可审核</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg leading-none">
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <p className="text-center text-sm text-slate-400 py-8">加载中…</p>
          ) : list.length === 0 ? (
            <p className="text-center text-sm text-slate-400 py-8">暂无待审核成员添加申请。</p>
          ) : (
            <div className="space-y-3">
              {list.map((r) => (
                <div key={r.id} className="rounded-xl border p-4" style={{ borderColor: '#E9EFF6' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-semibold text-slate-800">{r.target_person_name}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-semibold">
                      {r.to_role_label || r.to_role}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 space-y-0.5">
                    <div>申请人：{r.requester_name || '-'}</div>
                    <div>原因：{r.reason || '-'}</div>
                    <div>时间：{r.created_at || '-'}</div>
                  </div>
                  <div className="mt-2">
                    <input
                      value={comments[r.id] || ''}
                      onChange={(e) => setComments((prev) => ({ ...prev, [r.id]: e.target.value }))}
                      placeholder="审核意见（拒绝必填）"
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                    />
                  </div>
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      onClick={() => handleApprove(r.id)}
                      disabled={busy === r.id}
                      className="cursor-pointer flex-1 py-1.5 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
                      style={{ background: '#059669' }}
                    >
                      通过
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReject(r.id)}
                      disabled={busy === r.id}
                      className="cursor-pointer flex-1 py-1.5 rounded-lg text-xs font-semibold border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
