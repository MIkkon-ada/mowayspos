import { SectionTitle } from './meetingShared'

type ReportData = { member?: string; content?: string; related_task?: string }

export function ReportsSection({ reportsJson }: { reportsJson: string }) {
  let reports: ReportData[] = []
  try { reports = JSON.parse(reportsJson) } catch { return null }
  const actualUpdates = Array.isArray(reports)
    ? reports.filter((report) => String(report.content || '').trim())
    : []
  if (!actualUpdates.length) return null

  return (
    <div>
      <SectionTitle>成员进度更新</SectionTitle>
      <div className="mt-3 grid grid-cols-1 xl:grid-cols-2 gap-3">
        {actualUpdates.map((report, index) => (
          <article key={index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold">
                {(report.member || '待').slice(0, 1)}
              </span>
              <div>
                <div className="text-sm font-bold text-slate-800">{report.member || '待确认成员'}</div>
                <div className="text-xs text-slate-400">本次会议实际更新</div>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap">{report.content}</p>
            {report.related_task && <div className="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-xs text-sky-700">关联推进表：{report.related_task}</div>}
          </article>
        ))}
      </div>
    </div>
  )
}
