import { SectionTitle } from './meetingShared'

type ReportData = {
  member: string
  role?: string
  completed_items?: string[]
  vs_last_plan?: string
  issues?: string[]
  requests?: string[]
  leader_feedback?: { positive?: string[]; improve?: string[]; reminder?: string[] }
  next_steps?: { task: string; deadline?: string }[]
}

const VS_STYLE: Record<string, { bg: string; text: string }> = {
  over: { bg: '#DCFCE7', text: '#166534' },
  same: { bg: '#DBEAFE', text: '#1D4ED8' },
  gap: { bg: '#FEF3C7', text: '#92400E' },
  missing: { bg: '#FEE2E2', text: '#991B1B' },
  unknown: { bg: '#F1F5F9', text: '#64748B' },
}

function ReportList({ label, items, color }: { label: string; items?: string[]; color: string }) {
  if (!items?.length) return null
  return (
    <div>
      <div className="text-xs font-semibold text-slate-500 mb-1">{label}</div>
      <div className="space-y-1">
        {items.map((t, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: color }} />
            <span>{t}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ReportsSection({ reportsJson }: { reportsJson: string }) {
  let reports: ReportData[] = []
  try {
    reports = JSON.parse(reportsJson)
  } catch {
    return null
  }
  if (!Array.isArray(reports) || reports.length === 0) return null

  return (
    <div>
      <SectionTitle>成员汇报</SectionTitle>
      <div className="mt-2 space-y-3">
        {reports.map((r, i) => {
          const vs = r.vs_last_plan ?? ''
          const vsStyle = VS_STYLE[vs] ?? VS_STYLE.unknown
          const fb = r.leader_feedback ?? {}
          return (
            <div key={i} className="border rounded-xl overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
              <div className="flex items-center justify-between px-4 py-2.5" style={{ background: '#F8FAFC' }}>
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold">
                    {(r.member || '?').slice(0, 1)}
                  </div>
                  <span className="text-sm font-bold text-slate-700">{r.member || `成员 ${i + 1}`}</span>
                  {r.role && <span className="text-xs text-slate-400">{r.role}</span>}
                </div>
                {vs && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: vsStyle.bg, color: vsStyle.text }}>
                    {vs}
                  </span>
                )}
              </div>
              <div className="px-4 py-3 space-y-3">
                <ReportList label="本期完成" items={r.completed_items} color="#10B981" />
                <ReportList label="问题/卡点" items={r.issues} color="#F59E0B" />
                <ReportList label="请求协助/决策" items={r.requests} color="#3B82F6" />
                {(fb.positive?.length || fb.improve?.length || fb.reminder?.length) ? (
                  <div>
                    <div className="text-xs font-semibold text-slate-500 mb-1.5">领导反馈</div>
                    <div className="space-y-1.5 pl-2 border-l-2" style={{ borderColor: '#8B5CF6' }}>
                      {fb.positive?.map((t, j) => (
                        <div key={j} className="flex items-start gap-1.5 text-xs text-emerald-700">
                          <span className="mt-0.5">+</span>
                          <span>{t}</span>
                        </div>
                      ))}
                      {fb.improve?.map((t, j) => (
                        <div key={j} className="flex items-start gap-1.5 text-xs text-amber-700">
                          <span className="mt-0.5">*</span>
                          <span>{t}</span>
                        </div>
                      ))}
                      {fb.reminder?.map((t, j) => (
                        <div key={j} className="flex items-start gap-1.5 text-xs text-red-600 font-medium">
                          <span className="mt-0.5">!</span>
                          <span>{t}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {r.next_steps && r.next_steps.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-slate-500 mb-1.5">下一步计划</div>
                    <div className="space-y-1">
                      {r.next_steps.map((ns, j) => (
                        <div key={j} className="flex items-start gap-2 text-xs text-slate-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                          <span>{ns.task}</span>
                          {ns.deadline && <span className="ml-auto text-slate-400 whitespace-nowrap">{ns.deadline}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
