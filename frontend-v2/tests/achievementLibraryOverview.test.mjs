import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/AchievementsPage.tsx', import.meta.url), 'utf8')

test('achievement filters use the compact single-row layout', () => {
  assert.match(source, /flex flex-col gap-3 border-b border-slate-100 bg-white px-4 py-3/)
  assert.match(source, /flex max-w-full flex-wrap items-center gap-x-4 gap-y-2/)
  assert.match(source, /relative w-full sm:w-\[220px\]/)
  assert.match(source, /重置/)
})

test('achievement filters expose only work and task selectors', () => {
  for (const label of ['重点工作筛选', '关键任务筛选']) assert.match(source, new RegExp(`aria-label="${label}"`))
  for (const label of ['成果类型筛选', '来源筛选', '入库时间筛选', '入库开始日期', '入库结束日期']) assert.doesNotMatch(source, new RegExp(`aria-label="${label}"`))
  assert.match(source, /<option value="">/)
  assert.match(source, /filterSubtaskId/)
  assert.match(source, /allSubtasks\.filter/)
})

test('achievement detail shows a prompt until a row is selected', () => {
  assert.doesNotMatch(source, /if \(!prev\) return rows\[0\] \?\? null/)
  assert.doesNotMatch(source, /rows\.find\(\(item\) => item\.id === prev\.id\) \?\? rows\[0\] \?\? null/)
  assert.match(source, /onClick=\{\(\) => \{ setSelected\(item\); setEditMode\(false\) \}\}/)
  assert.match(source, /选择左侧成果查看详情/)
  assert.match(source, /\{!selected \? \(/)
})

test('achievement list keeps core columns plus the submitter', () => {
  assert.match(source, /<th className="px-4 py-3 font-semibold">成果名称<\/th>/)
  assert.match(source, /<th className="px-3 py-3 font-semibold">成果类型<\/th>/)
  assert.match(source, /关联重点工作 \/ 关键任务/)
  assert.match(source, /<th className="px-3 py-3 font-semibold">提交\/登记人<\/th>/)
  assert.match(source, /<td colSpan=\{4\}/)
  assert.doesNotMatch(source, /<th className="px-3 py-3 font-semibold">来源<\/th>/)
  assert.doesNotMatch(source, /<th className="px-3 py-3 font-semibold">确认\/入库人<\/th>/)
})

test('achievement library overview matches the full project table information architecture', () => {
  assert.match(source, /mx-auto max-w-\[1440px\] px-6 py-6/)
  assert.match(source, /mb-6 flex items-center gap-4/)
  assert.match(source, /achievement-project-picker-card overflow-hidden rounded border border-slate-200 bg-white shadow-sm/)
  assert.match(source, /<table className="w-full min-w-\[920px\] text-left text-sm">/)
  assert.match(source, /<thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">/)
  assert.match(source, /<th className="px-5 py-2\.5">项目名称<\/th>/)
  assert.match(source, /<td className="px-5 py-2\.5 achievement-project-identity border-l-4 border-blue-500">/)
  assert.match(source, /<td className="px-4 py-2\.5 text-sm text-slate-600">\{ownerText\(project\)\}<\/td>/)
  assert.match(source, /border-t border-slate-200 bg-slate-50\/50 px-5 py-2\.5/)
  for (const label of ['成果库', '搜索项目名称', '登记成果', '查看成果']) assert.match(source, new RegExp(label))
  for (const label of ['项目', '已入库成果', '本月新增成果', '最近更新']) assert.match(source, new RegExp(label))
  for (const label of ['项目名称', '状态', '项目负责人', '企业教练', '成果数量', '最近更新', '操作']) assert.match(source, new RegExp(label))
  assert.match(source, /fetchAchievements\(project\.id\)/)
  assert.match(source, /查看成果/)
})

test('achievement library never renders the Bowei Consulting suffix', () => {
  assert.doesNotMatch(source, /博维咨询/)
})

test('achievement project names use a prominent project identity treatment', () => {
  assert.match(source, /achievement-project-identity/)
  assert.match(source, /achievement-project-identity__name/)
  assert.doesNotMatch(source, /achievement-project-identity__icon/)
})

test('achievement detail keeps only total, monthly, and latest-update summary cards', () => {
  assert.match(source, /sm:grid-cols-3/)
  assert.match(source, /stats\.latestUpdated/)
  assert.doesNotMatch(source, /\{stats\.ai\}/)
  assert.doesNotMatch(source, /\{stats\.manual\}/)
  assert.doesNotMatch(source, /\{stats\.taskCount\}/)
})

test('achievement detail includes managed attachment upload, preview, retry, and download affordances', () => {
  assert.match(source, /fetchAchievementAttachments/)
  assert.match(source, /uploadAchievementAttachment/)
  assert.match(source, /deleteAchievementAttachment/)
  assert.match(source, /attachmentQueue/)
  assert.match(source, /accept="\.pdf,\.doc,\.docx,\.xls,\.xlsx,\.ppt,\.pptx,\.jpg,\.jpeg,\.png,\.gif,\.webp,\.zip,\.rar"/)
  assert.match(source, /attachment\.original_name/)
  assert.match(source, /downloadAchievementAttachment/)
  assert.match(source, /isPreviewableImage/)
})
