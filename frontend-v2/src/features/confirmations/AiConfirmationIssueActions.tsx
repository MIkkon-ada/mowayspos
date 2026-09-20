import { useEffect, useState } from 'react'
import {
  assignIssueHelper,
  fetchIssueById,
  ownerConfirmOpinion,
  requestIssueCeo,
  resolveIssue,
  submitIssueOpinion,
} from '../../api/issues'
import type { IssueItem } from '../../types'

type Props = {
  issueId: number
  projectId: number | null
  canOwnerAct: boolean
  canCoordinatorAct: boolean
  canCoachAct: boolean
}

export function AiConfirmationIssueActions({ issueId, projectId, canOwnerAct, canCoordinatorAct, canCoachAct }: Props) {
  const [issue, setIssue] = useState<IssueItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      setIssue(await fetchIssueById(issueId))
      setMessage('')
    } catch {
      setIssue(null)
      setMessage('问题详情加载失败，请到问题中心查看。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [issueId])

  const run = async (action: () => Promise<IssueItem>, success: string) => {
    setActing(true)
    try {
      setIssue(await action())
      setMessage(success)
    } catch (error) {
      setMessage(`操作失败：${error instanceof Error ? error.message : '请稍后重试'}`)
    } finally {
      setActing(false)
    }
  }

  const openDetail = () => {
    const query = projectId == null ? '' : `?projectId=${projectId}&issueId=${issueId}`
    window.location.assign(`/work/issues/${issueId}${query}`)
  }

  if (loading) return <section className="rounded-xl border border-violet-100 bg-violet-50/40 p-3 text-xs text-violet-700">正在读取已转出的问题…</section>
  if (!issue) return <section className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">{message}</section>

  const pendingOwner = issue.status === '待负责人确认'
  const terminal = issue.status === '已解决' || issue.status === '已关闭'
  const canSubmitOpinion = (issue.status === '待协调' && canCoordinatorAct) || (issue.status === '待决策' && canCoachAct)

  return (
    <section data-ai-confirmation-issue-actions className="rounded-xl border border-violet-200 bg-violet-50/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-violet-900">已转出问题</h3>
        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-violet-700">{issue.status || '待处理'}</span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{issue.description || '未填写问题描述'}</p>
      <p className="mt-1 text-[11px] text-slate-500">负责人：{issue.owner || '未指定'} {issue.helper ? `· 协助人：${issue.helper}` : ''}</p>
      {message && <p className="mt-2 text-xs text-slate-600">{message}</p>}
      <div className="mt-3 space-y-2">
        <button type="button" onClick={openDetail} className="h-9 w-full rounded-lg border border-violet-200 bg-white text-xs font-semibold text-violet-700 hover:bg-violet-100">查看完整问题详情</button>
        {!terminal && canOwnerAct && (
          <button type="button" disabled={acting} onClick={() => {
            const helper = window.prompt('请输入协助人姓名：')
            if (helper?.trim()) void run(() => assignIssueHelper(issue.id, helper.trim()), '已指定协助人。')
          }} className="h-9 w-full rounded-lg border border-indigo-200 bg-white text-xs font-semibold text-indigo-700 disabled:opacity-50">指定协助人</button>
        )}
        {!terminal && canSubmitOpinion && (
          <button type="button" disabled={acting} onClick={() => {
            const opinion = window.prompt('请输入处理意见：')
            if (opinion?.trim()) void run(() => submitIssueOpinion(issue.id, opinion.trim()), '处理意见已提交，等待负责人确认。')
          }} className="h-9 w-full rounded-lg border border-purple-200 bg-white text-xs font-semibold text-purple-700 disabled:opacity-50">提交处理意见</button>
        )}
        {!terminal && pendingOwner && canOwnerAct && (
          <button type="button" disabled={acting} onClick={() => {
            const note = window.prompt('确认备注（可选）：') ?? ''
            void run(() => ownerConfirmOpinion(issue.id, true, note), '已确认，问题已解决。')
          }} className="h-9 w-full rounded-lg bg-emerald-600 text-xs font-semibold text-white disabled:opacity-50">确认并解决问题</button>
        )}
        {!terminal && !pendingOwner && canOwnerAct && (
          <>
            <button type="button" disabled={acting} onClick={() => {
              const decisionBy = window.prompt('需要由谁决策？')
              if (decisionBy?.trim()) void run(() => requestIssueCeo(issue.id, decisionBy.trim()), '已请求企业教练决策。')
            }} className="h-9 w-full rounded-lg border border-fuchsia-200 bg-white text-xs font-semibold text-fuchsia-700 disabled:opacity-50">请求企业教练决策</button>
            <button type="button" disabled={acting} onClick={() => {
              const resolution = window.prompt('解决方案：')
              if (resolution?.trim()) void run(() => resolveIssue(issue.id, resolution.trim()), '问题已标记为解决。')
            }} className="h-9 w-full rounded-lg bg-emerald-600 text-xs font-semibold text-white disabled:opacity-50">标记为已解决</button>
          </>
        )}
      </div>
    </section>
  )
}
