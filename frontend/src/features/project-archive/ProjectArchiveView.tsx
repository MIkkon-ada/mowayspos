import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import { toast } from '../../utils/toast'
import { ArchiveSectionNav, ARCHIVE_SECTIONS } from './ArchiveSectionNav'
import { ArchiveTimeline } from './ArchiveTimeline'
import { ArchiveOverview } from './ArchiveOverview'
import { ArchiveProgressSnapshot } from './ArchiveProgressSnapshot'
import { ArchiveAssetsSection } from './ArchiveAssetsSection'
import { ArchiveMeetingSection } from './ArchiveMeetingSection'
import { ArchiveCloseReviewSection } from './ArchiveCloseReviewSection'
import { ArchiveOperationSection } from './ArchiveOperationSection'
import { useProjectArchiveData } from './useProjectArchiveData'
import {
  buildArchiveMetrics,
  buildArchiveTimeline,
  buildProgressDistribution,
  buildProgressRows,
  findArchiveLog,
  formatArchiveDateTime,
  getMemberRoleSummary,
  latestApprovedCloseRequest,
} from './projectArchiveViewModel'

function ArchiveSkeleton() {
  return (
    <div className="project-archive-page">
      <div className="archive-toolbar archive-skeleton"><span /><span /></div>
      <div className="archive-main-grid">
        <div className="archive-skeleton archive-skeleton--nav" />
        <div className="archive-content-column">
          <div className="archive-skeleton archive-skeleton--header" />
          <div className="archive-skeleton-metrics">{Array.from({ length: 6 }, (_, index) => <span key={index} />)}</div>
          <div className="archive-skeleton archive-skeleton--card" />
          <div className="archive-skeleton archive-skeleton--card archive-skeleton--tall" />
        </div>
        <div className="archive-skeleton archive-skeleton--timeline" />
      </div>
    </div>
  )
}

function ArchiveStatePanel({ title, detail, ended, projectId, requestId }: { title: string; detail: string; ended: boolean; projectId: number; requestId?: number | null }) {
  const navigate = useNavigate()
  return (
    <div className="project-archive-page project-archive-state-page">
      <div className="archive-state-card">
        <span className="archive-state-icon" aria-hidden="true">▣</span>
        <p className="archive-section-eyebrow">PROJECT ARCHIVE</p>
        <h1>{title}</h1>
        <p>{detail}</p>
        <div className="archive-state-actions archive-print-hidden">
          <button type="button" className="archive-button archive-button--primary" onClick={() => navigate('/home/projects')}>返回项目管理</button>
          {ended && <button type="button" className="archive-button" onClick={() => navigate(`/home/projects?projectId=${projectId}${requestId ? `&closeRequestId=${requestId}` : ''}`)}>查看结束档案</button>}
        </div>
      </div>
    </div>
  )
}

export function ProjectArchiveView() {
  const navigate = useNavigate()
  const { currentUser } = useProject()
  const { projectId, loading, data, projectError, moduleErrors } = useProjectArchiveData()
  const [activeSection, setActiveSection] = useState<string>(ARCHIVE_SECTIONS[0].id)
  const [moreOpen, setMoreOpen] = useState(false)

  useEffect(() => {
    if (!data || data.project.status !== 'archived') return
    const elements = ARCHIVE_SECTIONS.map((item) => document.getElementById(item.id)).filter((item): item is HTMLElement => Boolean(item))
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (visible?.target.id) setActiveSection(visible.target.id)
    }, { rootMargin: '-96px 0px -65% 0px', threshold: [0.05, 0.2, 0.5] })
    elements.forEach((element) => observer.observe(element))
    return () => observer.disconnect()
  }, [data])

  const model = useMemo(() => {
    if (!data) return null
    const closeRequest = latestApprovedCloseRequest(data.closeRequests)
    const archiveLog = findArchiveLog(data.logs)
    const metrics = buildArchiveMetrics({ ...data, closeRequest })
    const progressRows = buildProgressRows(data.tasks, data.subtasks)
    const distribution = buildProgressDistribution(data.subtasks)
    const timeline = buildArchiveTimeline(data)
    const roles = getMemberRoleSummary(data.members, data.project)
    return { closeRequest, archiveLog, metrics, progressRows, distribution, timeline, roles }
  }, [data])

  const scrollToSection = (id: string) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const copyArchiveLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast.success('档案链接已复制')
    } catch {
      toast.error('复制失败，请从浏览器地址栏复制')
    } finally {
      setMoreOpen(false)
    }
  }

  if (loading) return <ArchiveSkeleton />
  if (projectError || !data || !model || projectId === null) {
    return <ArchiveStatePanel title="项目档案无法打开" detail={projectError || '项目档案数据不存在'} ended={false} projectId={projectId ?? 0} />
  }
  if (data.project.status !== 'archived') {
    const ended = data.project.status === 'ended'
    return (
      <ArchiveStatePanel
        title={ended ? '项目已结束但尚未归档' : '当前项目尚未形成归档档案'}
        detail={ended ? '结束材料已经批准，完成归档后可在此查看完整只读档案。' : `当前项目状态为“${data.project.status || '未记录'}”，只有已归档项目可以进入完整档案页。`}
        ended={ended}
        projectId={projectId}
        requestId={model.closeRequest?.id}
      />
    )
  }

  const closeStatus = model.closeRequest?.status === 'approved' ? '已批准' : model.closeRequest?.status || '未记录'

  return (
    <div className="project-archive-page">
      <header className="archive-toolbar archive-print-hidden">
        <div className="archive-breadcrumbs" aria-label="面包屑导航">
          <button type="button" onClick={() => navigate('/home/projects')}>项目管理</button><span>/</span><span>已归档</span><span>/</span><strong>{data.project.name}</strong><span>/</span><b>项目档案</b>
        </div>
        <div className="archive-toolbar__actions">
          <button type="button" className="archive-button archive-button--primary" onClick={() => window.print()}><span aria-hidden="true">⇩</span> 导出档案（PDF）</button>
          <button type="button" className="archive-button" disabled title="原始数据 ZIP 导出尚未接入"><span aria-hidden="true">▣</span> 导出原始数据（ZIP）</button>
          <div className="archive-more-wrap">
            <button type="button" className="archive-button archive-button--more" aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}>更多 <span aria-hidden="true">⋮</span></button>
            {moreOpen && (
              <div className="archive-more-menu">
                <button type="button" onClick={() => void copyArchiveLink()}>复制当前档案链接</button>
                <button type="button" onClick={() => navigate('/home/projects')}>返回项目管理</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="archive-main-grid">
        <aside className="archive-nav-column archive-print-hidden"><ArchiveSectionNav activeId={activeSection} onSelect={scrollToSection} /></aside>

        <main className="archive-content-column">
          <section className="archive-project-header archive-card">
            <div className="archive-project-header__identity">
              <div className="archive-project-title-row"><h1>{data.project.name}</h1><span className="archive-archived-badge">已归档</span></div>
              <div className="archive-project-meta">
                <span><small>项目编号</small><strong>{data.project.code || `PRJ-${data.project.id}`}</strong></span>
                <span><small>归档时间</small><strong>{model.archiveLog ? formatArchiveDateTime(model.archiveLog.created_at) : '未记录'}</strong></span>
                <span><small>归档人</small><strong>{model.archiveLog?.operator || '系统归档'}</strong></span>
                <span><small>项目状态</small><strong>已归档（archived）</strong></span>
                <span><small>结束申请</small><strong>{model.closeRequest ? `#${model.closeRequest.id}（${closeStatus}）` : '未记录'}</strong></span>
              </div>
            </div>
            <div className="archive-role-summary">
              <div><span>项目负责人</span><strong>{model.roles.owner}</strong></div>
              <div><span>企业教练</span><strong>{model.roles.projectCeo}</strong></div>
              <div><span>统筹人</span><strong>{model.roles.coordinator}</strong></div>
              <div><span>项目成员人数</span><strong>{model.roles.count} 人</strong></div>
            </div>
          </section>

          <ArchiveOverview project={data.project} closeRequest={model.closeRequest} members={data.members} metrics={model.metrics} memberError={moduleErrors.members} />
          <ArchiveProgressSnapshot rows={model.progressRows} distribution={model.distribution} error={moduleErrors.tasks || moduleErrors.subtasks} />
          <ArchiveAssetsSection projectId={projectId} achievements={data.achievements} issues={data.issues} achievementError={moduleErrors.achievements} issueError={moduleErrors.issues} />
          <ArchiveMeetingSection projectId={projectId} meetings={data.meetings} error={moduleErrors.meetings} />
          <ArchiveCloseReviewSection latestApproved={model.closeRequest} requests={data.closeRequests} error={moduleErrors.closeRequests} />
          <ArchiveOperationSection events={model.timeline} error={currentUser?.is_tech_admin ? moduleErrors.logs : undefined} administratorView={Boolean(currentUser?.is_tech_admin)} />
        </main>

        <aside className="archive-timeline-column archive-print-hidden"><ArchiveTimeline events={model.timeline} onMore={() => scrollToSection('archive-operations')} /></aside>
      </div>
    </div>
  )
}
