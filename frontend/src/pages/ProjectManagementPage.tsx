import { ProjectsMgmtSection } from '../features/settings/ProjectsMgmtSection'

export function ProjectManagementPage() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="h-16 flex items-center px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">项目管理</h1>
          <p className="text-xs text-slate-400 mt-0.5">创建与管理所有项目，配置项目人员，推进立项流程</p>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto p-6" style={{ background: '#F1F5F9' }}>
        <ProjectsMgmtSection />
      </main>
    </div>
  )
}
