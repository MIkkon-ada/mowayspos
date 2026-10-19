import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import type { SubTaskItem } from '../../types'
import { fetchSubTasksBatch } from '../../api/subtasks'
import { PlanTableViewV2, type Props as PlanProps } from './PlanTableViewV2'
import { buildPlanRows } from './planTableViewModel'
import type { GridRecord, GridCellChange } from './WorkProgressGrid'
import { GRID_COLUMNS, DEFAULT_GRID_VIEW, normalizeGridView, readSavedGridViews, buildCellChange, mergeGridDraft, type GridDrafts, type GridEdit, type GridFilters, type GridView, type SavedGridView, type GridColumnKey } from './workProgressGridModel'
import { ChevronDownIcon } from '../icons/ChevronDownIcon'
import './workProgressGrid.css'
const WorkProgressGrid = lazy(() => import('./WorkProgressGrid').then(module => ({ default: module.WorkProgressGrid })))

type Props = PlanProps & {
  storageScope: string
  memberNames: string[]
  filters: GridFilters
  onFiltersChange: (filters: GridFilters) => void
  onSave?: (edits: GridEdit[]) => Promise<void>
}
function loadLayout(key: string): GridView {
  try { return normalizeGridView(JSON.parse(localStorage.getItem(key) || JSON.stringify(DEFAULT_GRID_VIEW))) }
  catch { return { ...DEFAULT_GRID_VIEW } }
}
function loadDrafts(key: string): GridDrafts {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || '{}')
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  } catch { return {} }
}
export function WorkProgressGridWorkspace(props: Props) {
  const storageKey = `wp-grid:v1:${props.storageScope}`
  const [view, setView] = useState<GridView>(() => loadLayout(`${storageKey}:layout`))
  const [savedViews, setSavedViews] = useState<SavedGridView[]>(() => readSavedGridViews(localStorage.getItem(`${storageKey}:views`)))
  const [activeView, setActiveView] = useState(() => { try { return localStorage.getItem(`${storageKey}:active`) || 'all' } catch { return 'all' } })
  const [viewName, setViewName] = useState('')
  const [savingView, setSavingView] = useState(false)
  const [columnsOpen, setColumnsOpen] = useState(false)
  const [textMode, setTextMode] = useState(false)
  const [drafts, setDrafts] = useState<GridDrafts>(() => loadDrafts(`${storageKey}:drafts`))
  const [selected, setSelected] = useState<GridRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reviewRows, setReviewRows] = useState<SubTaskItem[] | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const draftCount = Object.keys(drafts).length
  const canEdit = Boolean(props.onSave)
  useEffect(() => {
    const entry = savedViews.find(view => view.id === activeView)
    if (entry) props.onFiltersChange(entry.filters)
    else if (activeView === 'overdue' || activeView === 'issues') props.onFiltersChange({ search: '', status: '', owner: '', quickFilter: activeView })
  }, [storageKey])
  useEffect(() => { try { localStorage.setItem(`${storageKey}:active`, activeView) } catch { /* The view itself can still be used without persistence. */ } }, [storageKey, activeView])
  useEffect(() => {
    try { localStorage.setItem(`${storageKey}:layout`, JSON.stringify(view)) }
    catch { setError('浏览器无法保存列设置，请检查存储空间。') }
  }, [storageKey, view])
  useEffect(() => {
    try { sessionStorage.setItem(`${storageKey}:drafts`, JSON.stringify(drafts)) }
    catch { setError('浏览器无法暂存修改，请及时保存，避免关闭页面后丢失。') }
  }, [storageKey, drafts])
  useEffect(() => {
    if (!draftCount) return
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [draftCount])
  const rows = useMemo(() => buildPlanRows(props), [props.project, props.tasks, props.taskSubMap, props.searchText, props.statusFilter, props.ownerFilter, props.quickFilter, props.issueTaskIds, props.issueSubtaskIds])
  const records = useMemo<GridRecord[]>(() => rows.map(plan => {
    const source = plan.subtask
    const item = source ? { ...source, ...drafts[source.id]?.changes } : null
    const progress = source?.latest_confirmed_progress, submission = source?.latest_confirmed_submission
    const summary = progress?.summary || submission?.summary || (source?.has_any_submission === false ? '尚未汇报' : '暂无已确认进展')
    const actor = progress?.source_label === '个人提交' ? progress.confirmed_by : progress?.actor
    const meta = [progress?.confirmed_at?.slice(0, 10) || submission?.confirmed_at?.slice(0, 10), actor || submission?.confirmed_by, progress?.source_label || submission?.source_label].filter(Boolean).join(' · ')
    const pending = source?.latest_unconfirmed_submission
    const risk = [plan.risk, ...plan.statusMarkers.filter(marker => ['overdue', 'risk', 'date_unknown'].includes(marker.kind)).map(marker => marker.label), pending && `${pending.confirm_status} · ${pending.submitter}`].filter(value => value && value !== '—')
    return {
      _source: source, _plan: plan, _dirty: Boolean(source && drafts[source.id]),
      workstream: plan.workstream, keyTask: item?.title || plan.keyTask, owner: item?.assignee || plan.responsible,
      startDate: item?.start_date || '', dueDate: item?.due_date || item?.due_label || (item?.due_kind === 'unknown' ? '待确认' : ''),
      status: plan.status, risk: [...new Set(risk)].join('\n'), latestProgress: `${summary}${meta ? `\n${meta}` : ''}`, nextStep: plan.nextStep === '—' ? '' : plan.nextStep,
      expectedOutcome: item?.expected_outcome || '', goal: item?.goal || '', boweiRole: item?.bowei_role || '', acceptance: item?.completion_criteria || plan.acceptance, notes: item?.notes || '',
    }
  }), [rows, drafts])
  useEffect(() => {
    setSelected(previous => previous ? records.find(record => record._source?.id === previous._source?.id) ?? null : null)
  }, [records])

  function changeCells(cells: GridCellChange[]) {
    try {
      if (!canEdit || saving) throw new Error('当前表格只读或正在保存')
      let next = drafts
      cells.forEach(cell => { next = mergeGridDraft(next, cell.source, buildCellChange(cell.source, cell.key, cell.value, props.memberNames)) })
      if (Object.keys(next).length > 200) throw new Error('每批最多保存 200 行，请先保存当前修改')
      // Validate dates after merging the entire paste, allowing both dates to move together.
      for (const edit of Object.values(next)) {
        const original = Object.values(props.taskSubMap).flat().find(row => row.id === edit.id)
        const merged = { ...original, ...edit.changes }
        if (merged.start_date && merged.due_date && merged.start_date > merged.due_date) throw new Error('截止日期不得早于开始日期；本次粘贴未应用')
      }
      setDrafts(next); setError(''); setNotice(''); return true
    } catch (failure) { setError(failure instanceof Error ? failure.message : '修改失败'); return false }
  }
  async function save() {
    if (!props.onSave || saving) return
    setSaving(true); setError(''); setNotice('')
    try { await props.onSave(Object.values(drafts)); setDrafts({}); setNotice('修改已保存') }
    catch (failure) { setError(`${failure instanceof Error ? failure.message : '保存失败'}。输入已保留，可核对后重试。`) }
    finally { setSaving(false) }
  }
  async function reviewLatest() {
    setReviewLoading(true)
    try {
      const batch = await fetchSubTasksBatch(props.tasks.map(task => task.id))
      const latest = Object.values(batch).flat().filter(row => drafts[row.id])
      if (latest.length !== draftCount || latest.some(row => !row.edit_version)) throw new Error('部分记录已移除，请保留需要的文字后放弃修改并刷新')
      if (latest.some(row => ['已完成', '完成', 'completed'].includes(row.status))) throw new Error('部分任务已完成，请从详情重新打开后再修改')
      setReviewRows(latest)
    } catch (failure) { setError(failure instanceof Error ? failure.message : '最新记录加载失败，输入已保留') }
    finally { setReviewLoading(false) }
  }
  function acceptReviewedRows() {
    if (!reviewRows) return
    setDrafts(previous => Object.fromEntries(Object.entries(previous).map(([id, edit]) => [id, { ...edit, expected_updated_at: reviewRows.find(row => row.id === edit.id)!.edit_version! }])))
    setReviewRows(null); setError(''); setNotice('已保留你的修改，请点击保存修改')
  }
  function persistViews(next: SavedGridView[]) {
    try { localStorage.setItem(`${storageKey}:views`, JSON.stringify(next)); setSavedViews(next); return true }
    catch { setError('视图未保存，浏览器存储不可用'); return false }
  }
  function saveView() {
    const name = viewName.trim()
    if (!name) return
    const existing = savedViews.find(item => item.name === name)
    if (!existing && savedViews.length >= 20) { setError('最多保存 20 个个人视图，请先删除不用的视图'); return }
    const entry = { id: existing?.id ?? crypto.randomUUID(), name, layout: view, filters: props.filters }
    const next = existing ? savedViews.map(item => item.id === existing.id ? entry : item) : [...savedViews, entry]
    if (persistViews(next)) { setActiveView(entry.id); setSavingView(false); setViewName(''); setNotice('个人视图已保存到当前浏览器') }
  }
  function preset(id: string) {
    setActiveView(id)
    if (id === 'all') props.onFiltersChange({ search: '', status: '', owner: '', quickFilter: 'all' })
    else if (id === 'overdue' || id === 'issues') props.onFiltersChange({ search: '', status: '', owner: '', quickFilter: id })
    else {
      const entry = savedViews.find(item => item.id === id)
      if (entry) { setView(entry.layout); props.onFiltersChange(entry.filters) }
    }
  }
  function moveColumn(index: number, direction: number) {
    const columns = [...view.columns], other = index + direction
    if (other < 0 || other >= columns.length) return
    ;[columns[index], columns[other]] = [columns[other], columns[index]]
    setView({ ...view, columns })
  }
  if (props.loading) return <div className="wp-empty" role="status">正在加载工作推进表…</div>
  if (props.loadError) return <div className="wp-empty" role="alert"><p>{props.loadError}</p><button className="wp-header-button" onClick={props.onRetryLoading}>重试加载关键任务</button></div>
  return <section className="wp-grid-workspace" aria-label="工作推进表工作台">
    <div className="wp-grid-viewbar" aria-label="工作推进表视图">
      <div className="wp-grid-tabs">
        {[{ id: 'all', name: '全部工作' }, { id: 'overdue', name: '延期任务' }, { id: 'issues', name: '关联问题' }, ...savedViews].map(item => <button key={item.id} type="button" aria-pressed={activeView === item.id} onClick={() => preset(item.id)}>{item.name}</button>)}
      </div>
      <button type="button" className="wp-grid-text-button" onClick={() => { setSavingView(!savingView); setViewName(savedViews.find(item => item.id === activeView)?.name || '') }}>保存视图</button>
      {savedViews.some(item => item.id === activeView) && <button type="button" className="wp-grid-text-button" aria-label="删除当前个人视图" onClick={() => { if (persistViews(savedViews.filter(item => item.id !== activeView))) preset('all') }}>删除视图</button>}
    </div>
    {savingView && <form className="wp-grid-save-view" onSubmit={event => { event.preventDefault(); saveView() }}><label>视图名称<input autoFocus value={viewName} maxLength={40} onChange={event => setViewName(event.target.value)} /></label><span>仅保存在当前账号、当前项目的浏览器中</span><button type="submit" disabled={!viewName.trim()}>确认保存视图</button><button type="button" onClick={() => setSavingView(false)}>取消</button></form>}
    <div className="wp-grid-toolbar">
      <label className="wp-grid-select">分组<select aria-label="分组方式" disabled={saving} value={view.groupBy} onChange={event => setView({ ...view, groupBy: event.target.value as GridView['groupBy'] })}><option value="workstream">按重点工作</option><option value="owner">按负责人</option><option value="status">按状态</option><option value="none">不分组</option></select><ChevronDownIcon /></label>
      <label className="wp-grid-select">冻结<select aria-label="冻结列数" value={view.frozen} onChange={event => setView({ ...view, frozen: Number(event.target.value) })}>{Array.from({ length: Math.min(3, view.columns.length) + 1 }, (_, i) => <option key={i} value={i}>{i ? `前 ${i} 列` : '不冻结'}</option>)}</select><ChevronDownIcon /></label>
      <div className="wp-grid-column-anchor"><button className="wp-grid-tool" type="button" aria-expanded={columnsOpen} onClick={() => setColumnsOpen(!columnsOpen)}>列配置 <span>{view.columns.length}</span><ChevronDownIcon /></button>
        {columnsOpen && <div className="wp-grid-column-panel" role="dialog" aria-label="表格列配置"><header><strong>显示与排列字段</strong><button type="button" onClick={() => setColumnsOpen(false)} aria-label="关闭列配置">×</button></header>{[...view.columns.map(key => GRID_COLUMNS.find(column => column.key === key)!), ...GRID_COLUMNS.filter(column => !view.columns.includes(column.key))].map(column => {
          const index = view.columns.indexOf(column.key)
          return <div className="wp-grid-column-choice" key={column.key}><label><input type="checkbox" disabled={column.key === 'keyTask'} checked={index >= 0} onChange={event => setView(normalizeGridView({ ...view, columns: event.target.checked ? [...view.columns, column.key] : view.columns.filter(key => key !== column.key) }))} />{column.label}</label>{index >= 0 && <span><button type="button" disabled={index === 0} aria-label={`前移${column.label}`} onClick={() => moveColumn(index, -1)}><ChevronDownIcon className="wp-grid-chevron-up" /></button><button type="button" disabled={index === view.columns.length - 1} aria-label={`后移${column.label}`} onClick={() => moveColumn(index, 1)}><ChevronDownIcon /></button></span>}</div>
        })}<button className="wp-grid-text-button" type="button" onClick={() => setView({ ...DEFAULT_GRID_VIEW })}>恢复默认列</button></div>}
      </div>
      <span className="wp-grid-toolbar-divider" />
      <button className="wp-grid-tool" disabled={!selected?._source} onClick={() => selected?._source && props.onOpenSubTask?.(selected._source)}>打开任务详情</button>
      <button type="button" className="wp-grid-text-button" aria-pressed={textMode} onClick={() => setTextMode(!textMode)}>{textMode ? '返回表格工作台' : '文字视图'}</button>
      <span className="wp-grid-count">{records.filter(record => record._source).length} 项关键任务</span>
    </div>
    <div className="wp-grid-instruction">{canEdit ? '双击单元格编辑 · 框选复制 · 选中起始格后粘贴 · 修改后统一保存' : props.project?.status === 'archived' ? '已归档 · 可以查看和复制历史记录' : '查看模式 · 可以选择、复制记录，或打开任务详情'}<span>状态、已确认进展和下一步计划从业务记录同步</span></div>
    {error && <div className="wp-grid-message is-error" role="alert"><span>{error}</span>{draftCount > 0 && canEdit && <button type="button" className="wp-grid-review-button" disabled={reviewLoading || saving} onClick={() => { void reviewLatest() }}>{reviewLoading ? '加载中…' : '刷新并核对'}</button>}<button onClick={() => setError('')} aria-label="关闭错误提示">×</button></div>}
    {notice && <div className="wp-grid-message" role="status">{notice}</div>}
    {draftCount > 0 && <div className="wp-grid-drafts"><strong>{draftCount} 行待保存</strong><span>浅黄色行尚未入库 · 当前会话已暂存</span><button type="button" disabled={saving || !canEdit} onClick={() => { void save() }}>{saving ? '保存中…' : '保存修改'}</button><button type="button" disabled={saving} onClick={() => { setDrafts({}); setError(''); setNotice('已放弃本次修改') }}>放弃修改</button></div>}
    {textMode ? <PlanTableViewV2 {...props} /> : records.length ? <Suspense fallback={<div className="wp-empty" role="status">正在加载表格…</div>}><WorkProgressGrid records={records} view={view} canEdit={canEdit && !saving} memberNames={props.memberNames} onChanges={changeCells} onSelect={record => setSelected(record?._source ? record : null)} onError={setError} onWidths={widths => setView(previous => ({ ...previous, widths: { ...previous.widths, ...widths } }))} /></Suspense> : <div className="wp-empty">当前条件下没有匹配的重点工作或关键任务，请调整筛选条件。</div>}
    <footer className="wp-grid-footer">{selected?._source ? <><button onClick={() => props.onOpenSubTask?.(selected._source as SubTaskItem)}>{selected._source.title}</button><span>{selected._plan.workstream} · {selected._source.assignee} · {selected._plan.status}</span></> : <span>选择一条关键任务，可以打开详情查看汇报、问题与成果</span>}<span className="wp-grid-footer-right">{canEdit ? '项目管理权限' : '只读'} · 个人视图</span></footer>
    {reviewRows && <div className="wp-modal-backdrop" onKeyDown={event => { if (event.key === 'Escape') setReviewRows(null) }}><section className="wp-grid-review-modal" role="dialog" aria-modal="true" aria-labelledby="wp-grid-review-title"><header><h2 id="wp-grid-review-title">核对最新记录与待保存修改</h2><p>请逐项检查。确认后保留你的修改，其余字段继续使用系统最新值。</p></header><div className="wp-grid-review-body">{reviewRows.map(row => <section key={row.id}><h3>{row.title}</h3><table><thead><tr><th>字段</th><th>系统最新值</th><th>你的修改</th></tr></thead><tbody>{Object.entries(drafts[row.id]?.changes ?? {}).map(([field, value]) => <tr key={field}><th>{GRID_COLUMNS.find(column => column.field === field)?.label || field}</th><td>{String(row[field as keyof SubTaskItem] ?? '（空）')}</td><td>{String(value ?? '（清空）')}</td></tr>)}</tbody></table></section>)}</div><footer><button type="button" onClick={() => setReviewRows(null)}>取消</button><button type="button" autoFocus onClick={acceptReviewedRows}>已核对，使用最新版本</button></footer></section></div>}
  </section>
}
