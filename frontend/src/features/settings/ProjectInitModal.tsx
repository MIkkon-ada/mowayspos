import { createPortal } from 'react-dom'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { Person } from '../../types'
import { getProjectRoleLabel } from '../../domain/roleLabels'
import { getPickerPosition } from './projectPickerPosition.js'

export type TeamMap = {
  owner: number[]
  coordinator: number[]
  member: number[]
  project_ceo: number[]
}

export type NewProjectForm = {
  name: string
  project_type: string
  client_name: string
  background: string
  objectives: string
  expected_outcomes: string
  start_date: string
  end_date: string
}

type TeamRole = 'project_ceo' | 'owner' | 'coordinator' | 'member'

const TEAM_ROLES: TeamRole[] = ['project_ceo', 'owner', 'coordinator', 'member']

const ROLE_LABELS: Record<TeamRole, string> = {
  project_ceo: getProjectRoleLabel('project_ceo'),
  owner: getProjectRoleLabel('owner'),
  coordinator: getProjectRoleLabel('coordinator'),
  member: getProjectRoleLabel('member'),
}

const ROLE_STYLES: Record<TeamRole, { badge: string; border: string; dot: string }> = {
  project_ceo: { badge: 'bg-purple-100 text-purple-700 border-purple-200', border: 'border-purple-100', dot: 'bg-purple-500' },
  owner: { badge: 'bg-blue-100 text-blue-700 border-blue-200', border: 'border-blue-100', dot: 'bg-blue-500' },
  coordinator: { badge: 'bg-emerald-100 text-emerald-700 border-emerald-200', border: 'border-emerald-100', dot: 'bg-emerald-500' },
  member: { badge: 'bg-gray-100 text-gray-700 border-gray-200', border: 'border-gray-200', dot: 'bg-gray-400' },
}

// 头像颜色生成函数
function getAvatarColor(name: string): string {
  const colors = [
    'from-blue-500 to-indigo-600',
    'from-emerald-500 to-teal-600',
    'from-violet-500 to-purple-600',
    'from-orange-500 to-red-500',
    'from-pink-500 to-rose-500',
    'from-cyan-500 to-blue-600',
    'from-amber-500 to-orange-600',
    'from-lime-500 to-green-600',
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

type PickerState = {
  role: TeamRole
  anchorEl: HTMLButtonElement
}

type ProjectInitModalProps = {
  open: boolean
  creating: boolean
  mode?: 'create' | 'edit'
  people: Person[]
  form: NewProjectForm
  setForm: Dispatch<SetStateAction<NewProjectForm>>
  team: TeamMap
  setTeam: Dispatch<SetStateAction<TeamMap>>
  onClose: () => void
  onSubmit: () => void
}

export function ProjectInitModal({
  open,
  creating,
  mode = 'create',
  people,
  form,
  setForm,
  team,
  setTeam,
  onClose,
  onSubmit,
}: ProjectInitModalProps) {
  const [picker, setPicker] = useState<PickerState | null>(null)
  const roleOrder: TeamRole[] = TEAM_ROLES

  useEffect(() => {
    if (!open) setPicker(null)
  }, [open])

  // 允许同一人兼任多个角色，不再互斥过滤
  const allSelectedIds = useMemo(() => new Set<number>([]), [])

  function closeModal() {
    setPicker(null)
    onClose()
  }

  function toggleMember(role: keyof TeamMap, personId: number) {
    setTeam((prev) => {
      const current = prev[role]
      return {
        ...prev,
        [role]: current.includes(personId) ? current.filter((id) => id !== personId) : [...current, personId],
      }
    })
  }

  function removeMember(role: keyof TeamMap, personId: number) {
    setTeam((prev) => ({ ...prev, [role]: prev[role].filter((id) => id !== personId) }))
  }

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-3 backdrop-blur-[2px]"
      onClick={() => {
        if (!creating) closeModal()
      }}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-[1100px] flex-col overflow-hidden rounded-3xl bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15),0_8px_16px_rgba(0,0,0,0.1)]"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Header - 新设计 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-7 py-5 bg-gradient-to-r from-gray-50 to-white">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/30">
              <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <div className="text-lg font-bold text-gray-900 tracking-tight">{mode === 'edit' ? '编辑项目' : '项目立项'}</div>
              <div className="mt-0.5 text-xs font-medium text-gray-500">
                {mode === 'edit' ? '修改基础信息和团队配置后保存。' : '填写完整后创建项目，立项人会自动记录为当前登录用户'}
              </div>
            </div>
          </div>
          
          <button
            type="button"
            onClick={closeModal}
            className="group flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition-all hover:bg-gray-100 hover:text-gray-600 cursor-pointer"
            aria-label="关闭弹窗"
          >
            <svg className="h-5 w-5 transition-transform duration-200 group-hover:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body Content */}
        <div className="custom-scrollbar flex-1 space-y-5 overflow-y-auto px-7 py-6">
          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            
            {/* Left Column */}
            <div className="min-w-0 space-y-5">
              
              {/* Basic Info Section */}
              <section className="rounded-2xl border-2 border-gray-100 bg-white p-6 transition-colors duration-300 hover:border-blue-200 shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)]">
                <div className="mb-5 flex items-center gap-2.5 pb-4 border-b border-gray-100">
                  <div className="h-6 w-1 rounded-full bg-gradient-to-b from-blue-500 to-blue-600"></div>
                  <h3 className="text-sm font-bold uppercase tracking-wide text-gray-800">基本信息</h3>
                </div>

                <div className="space-y-4">
                  {/* Project Type - 新设计 */}
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-700">
                      项目类型 <span className="ml-1 text-red-500">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { type: '博维内部项目', desc: '团队内部优化项目', key: 'internal' },
                        { type: '博维-客户项目', desc: '外部客户委托项目', key: 'client' },
                      ].map(({ type, desc }) => {
                        const isSelected = form.project_type === type
                        return (
                          <button
                            key={type}
                            type="button"
                            onClick={() =>
                              setForm((prev) => ({
                                ...prev,
                                project_type: type,
                                client_name: type === '博维内部项目' ? '' : prev.client_name,
                              }))
                            }
                            className={`group relative cursor-pointer rounded-xl border-2 px-4 py-3 text-left transition-all duration-200 ${
                              isSelected
                                ? 'border-blue-400 bg-blue-50 shadow-md'
                                : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-md'
                            }`}
                          >
                            <div className={`font-semibold text-sm ${isSelected ? 'text-blue-700' : 'text-gray-700 group-hover:text-gray-900'}`}>{type}</div>
                            <div className={`mt-1 text-xs ${isSelected ? 'text-blue-500' : 'text-gray-400'}`}>{desc}</div>
                            <div
                              className={`absolute top-2 right-2 h-5 w-5 rounded-full border-2 transition-all ${
                                isSelected ? 'border-blue-400 bg-blue-500' : 'border-gray-200'
                              }`}
                            ></div>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Project Name */}
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-700">
                      项目名称 <span className="ml-1 text-red-500">*</span>
                    </label>
                    <input
                      autoFocus
                      value={form.name}
                      onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                      placeholder="请输入项目名称..."
                      className="w-full rounded-xl border-2 border-gray-200 px-4 py-3 text-sm font-medium text-gray-800 placeholder:text-gray-400 placeholder:font-normal transition-all duration-200 hover:border-gray-300 focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                    />
                  </div>

                  {/* Date Range */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-700">开始日期</label>
                      <div className="relative">
                        <input
                          type="date"
                          value={form.start_date}
                          onChange={(event) => setForm((prev) => ({ ...prev, start_date: event.target.value }))}
                          className="w-full rounded-xl border-2 border-gray-200 px-4 py-3 pr-10 text-sm font-medium text-gray-800 transition-all duration-200 hover:border-gray-300 focus:border-blue-500 [color-scheme:light] focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                        />
                        <svg className="pointer-events-none absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                          <line x1="16" y1="2" x2="16" y2="6"></line>
                          <line x1="8" y1="2" x2="8" y2="6"></line>
                          <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                      </div>
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-700">结束日期</label>
                      <div className="relative">
                        <input
                          type="date"
                          value={form.end_date}
                          onChange={(event) => setForm((prev) => ({ ...prev, end_date: event.target.value }))}
                          className="w-full rounded-xl border-2 border-gray-200 px-4 py-3 pr-10 text-sm font-medium text-gray-800 transition-all duration-200 hover:border-gray-300 focus:border-blue-500 [color-scheme:light] focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                        />
                        <svg className="pointer-events-none absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                          <line x1="16" y1="2" x2="16" y2="6"></line>
                          <line x1="8" y1="2" x2="8" y2="6"></line>
                          <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* Client Name with icon */}
                  <div id="clientField" style={{ opacity: form.project_type === '博维内部项目' ? 0.4 : 1 }}>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-700">客户名称</label>
                    <div className="relative">
                      <input
                        value={form.client_name}
                        onChange={(event) => setForm((prev) => ({ ...prev, client_name: event.target.value }))}
                        placeholder={form.project_type === '博维内部项目' ? '(内部项目无需填写)' : '请输入客户名称...'}
                        disabled={form.project_type === '博维内部项目'}
                        className="w-full rounded-xl border-2 border-gray-200 pl-11 pr-4 py-3 text-sm font-medium text-gray-800 placeholder:text-gray-400 placeholder:font-normal transition-all duration-200 hover:border-gray-300 focus:border-blue-500 disabled:cursor-not-allowed focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                      />
                      <div className="absolute left-4 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-lg bg-purple-100">
                        <svg className="h-3 w-3 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                          <path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Mobile Team Config */}
              <div className="lg:hidden">
                <TeamConfigCard
                  people={people}
                  team={team}
                  roles={roleOrder}
                  onOpenPicker={(role, anchorEl) => setPicker({ role, anchorEl })}
                  onRemoveMember={removeMember}
                />
              </div>

              {/* Background Section */}
              <section className="rounded-2xl border-2 border-gray-100 bg-white p-6 transition-colors duration-300 hover:border-blue-200 shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)]">
                <label className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-700">
                  <div className="h-4 w-1 rounded-full bg-violet-500"></div>
                  项目背景
                </label>
                <textarea
                  value={form.background}
                  onChange={(event) => setForm((prev) => ({ ...prev, background: event.target.value }))}
                  placeholder="为什么要做这个项目？客户痛点或内部需求是什么？"
                  rows={3}
                  className="w-full resize-none rounded-xl border-2 border-gray-200 px-4 py-3 leading-relaxed text-sm text-gray-800 placeholder:text-gray-400 placeholder:font-normal transition-all duration-200 hover:border-gray-300 focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                />
              </section>

              {/* Objectives Section */}
              <section className="rounded-2xl border-2 border-gray-100 bg-white p-6 transition-colors duration-300 hover:border-blue-200 shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)]">
                <label className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-700">
                  <div className="h-4 w-1 rounded-full bg-emerald-500"></div>
                  项目目标
                </label>
                <textarea
                  value={form.objectives}
                  onChange={(event) => setForm((prev) => ({ ...prev, objectives: event.target.value }))}
                  placeholder="项目完成后要达到什么状态？有哪些关键里程碑？"
                  rows={3}
                  className="w-full resize-none rounded-xl border-2 border-gray-200 px-4 py-3 leading-relaxed text-sm text-gray-800 placeholder:text-gray-400 placeholder:font-normal transition-all duration-200 hover:border-gray-300 focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                />
              </section>

              {/* Deliverables Section */}
              <section className="rounded-2xl border-2 border-gray-100 bg-white p-6 transition-colors duration-300 hover:border-blue-200 shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)]">
                <label className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-700">
                  <div className="h-4 w-1 rounded-full bg-orange-500"></div>
                  预期交付物
                </label>
                <textarea
                  value={form.expected_outcomes}
                  onChange={(event) => setForm((prev) => ({ ...prev, expected_outcomes: event.target.value }))}
                  placeholder="最终交付什么？文档、系统、原型等..."
                  rows={3}
                  className="w-full resize-none rounded-xl border-2 border-gray-200 px-4 py-3 leading-relaxed text-sm text-gray-800 placeholder:text-gray-400 placeholder:font-normal transition-all duration-200 hover:border-gray-300 focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
                />
              </section>
            </div>

            {/* Right Column - Desktop Team Config */}
            <div className="hidden min-w-[340px] lg:block">
              <div className="sticky top-0">
                <TeamConfigCard
                  people={people}
                  team={team}
                  roles={roleOrder}
                  onOpenPicker={(role, anchorEl) => setPicker({ role, anchorEl })}
                  onRemoveMember={removeMember}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions - 新设计 */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-100 px-7 py-5 bg-gradient-to-r from-white to-gray-50">
          <button
            type="button"
            onClick={closeModal}
            disabled={creating}
            className="cursor-pointer rounded-xl border-2 border-gray-200 px-6 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-50 hover:border-gray-300 hover:shadow-md active:scale-[0.98]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={creating || !form.name.trim() || (form.project_type === '博维-客户项目' && !form.client_name.trim())}
            className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 px-7 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/30 transition-all hover:from-blue-500 hover:to-blue-600 hover:shadow-xl hover:shadow-blue-500/40 disabled:opacity-50 active:scale-[0.98]"
          >
            <span>{creating ? (mode === 'edit' ? '保存中...' : '创建中...') : mode === 'edit' ? '保存修改' : '确认立项'}</span>
            {!creating && (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Person Picker Popover - 新设计 */}
      {picker && (
        <ProjectPeoplePickerPopover
          anchorEl={picker.anchorEl}
          people={people}
          selectedIds={team[picker.role]}
          takenIds={allSelectedIds}
          onTogglePerson={(personId) => toggleMember(picker.role, personId)}
          onClose={() => setPicker(null)}
          roleLabel={ROLE_LABELS[picker.role]}
        />
      )}
    </div>,
    document.body,
  )
}

function TeamConfigCard({
  people,
  team,
  roles,
  onOpenPicker,
  onRemoveMember,
}: {
  people: Person[]
  team: TeamMap
  roles: TeamRole[]
  onOpenPicker: (role: TeamRole, anchorEl: HTMLButtonElement) => void
  onRemoveMember: (role: keyof TeamMap, personId: number) => void
}) {
  // 允许同一人兼任多个角色，不再互斥过滤
  const allSelectedIds = useMemo(() => new Set<number>([]), [])

  return (
    <div className="rounded-2xl border-2 border-blue-100/80 bg-gradient-to-br from-slate-50 via-blue-50/40 to-indigo-50/30 p-5 shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)]">
      {/* Team Header - 新设计 */}
      <div className="mb-5 flex items-start gap-3 pb-4 border-b border-blue-100/60">
        <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 text-white shadow-lg shadow-purple-500/30">
          <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        </div>
        <div className="min-w-0 pt-0.5">
          <h3 className="text-base font-bold text-gray-900">团队配置</h3>
          <p className="mt-1 text-xs font-medium leading-relaxed text-gray-500">
            同一人可担任多个角色<br />可立项后再配置，留空也可以 ✓
          </p>
        </div>
      </div>

      {/* Roles List - 新设计 */}
      <div className="space-y-3">
        {roles.map((role) => {
          const style = ROLE_STYLES[role]
          const selected = team[role]
          const selectedPeople = people.filter((person) => selected.includes(person.id))
          const availableCount = people.length

          return (
            <div key={role} className={`group rounded-xl border-2 ${style.border} bg-white/80 backdrop-blur-sm p-4 transition-shadow duration-300 hover:shadow-[0_10px_25px_rgba(0,0,0,0.1),0_6px_10px_rgba(0,0,0,0.08)]`}>
              <div className="mb-3 flex items-center justify-between">
                <span className={`role-badge inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 border text-xs font-bold cursor-default transition-all hover:shadow-[0_2px_8px_currentColor] ${style.badge}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${style.dot} animate-pulse`}></span>
                  {ROLE_LABELS[role]}
                </span>
                <button
                  type="button"
                  onClick={(event) => onOpenPicker(role, event.currentTarget)}
                  className={`select-btn inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 border border-dashed border-gray-300 text-xs font-semibold bg-gray-50 text-gray-600 transition-all active:scale-95 ${
                    role === 'project_ceo' ? 'hover:bg-purple-50 hover:text-purple-700 hover:border-purple-300' :
                    role === 'owner' ? 'hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300' :
                    role === 'coordinator' ? 'hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300' :
                    'hover:bg-gray-100 hover:text-gray-800 hover:border-gray-400'
                  }`}
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  选人
                </button>
              </div>

              {/* Selected Tags */}
              <div className="min-h-[36px] flex flex-wrap gap-2 items-center">
                {selectedPeople.length === 0 ? (
                  <span className="text-xs italic py-1 text-gray-400">暂未配置...</span>
                ) : (
                  selectedPeople.map((person) => (
                    <span
                      key={person.id}
                      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium bg-white shadow-sm transition-shadow hover:shadow-md ${style.badge}`}
                      onClick={() => onRemoveMember(role, person.id)}
                    >
                      <span className={`flex h-5 w-5 items-center justify-center rounded-md bg-gradient-to-br ${getAvatarColor(person.name)} text-[10px] font-bold text-white`}>
                        {person.name.slice(0, 1)}
                      </span>
                      {person.name}
                      <button type="button" className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full text-gray-400 hover:bg-red-100 hover:text-red-500 transition-colors">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </span>
                  ))
                )}
              </div>

              {/* Count Info */}
              <div className="mt-2 flex items-center justify-between text-[11px] text-gray-400">
                <span>已选 <strong className="text-gray-600">{selectedPeople.length}</strong> 人</span>
                <span className="font-medium text-green-600">可分配 {availableCount} 人</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ProjectPeoplePickerPopover({
  anchorEl,
  people,
  selectedIds,
  takenIds,
  disabledIds,
  onTogglePerson,
  onClose,
  roleLabel,
}: {
  anchorEl: HTMLButtonElement
  people: Person[]
  selectedIds: number[]
  takenIds: Set<number>
  disabledIds?: Set<number>
  onTogglePerson: (personId: number) => void
  onClose: () => void
  roleLabel: string
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [position, setPosition] = useState({ top: 0, left: 0 })

  useLayoutEffect(() => {
    let mounted = true

    const updatePosition = () => {
      const rect = anchorEl.getBoundingClientRect()
      const panelWidth = panelRef.current?.getBoundingClientRect().width ?? 320
      const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 400
      const next = getPickerPosition(
        rect,
        { width: Math.max(320, panelWidth), height: Math.min(400, panelHeight) },
        { width: window.innerWidth, height: window.innerHeight },
      )
      if (mounted) setPosition({ top: next.top, left: Math.min(next.left, window.innerWidth - 340) })
    }

    updatePosition()
    const raf = window.requestAnimationFrame(updatePosition)

    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (!target) return
      if (panelRef.current?.contains(target)) return
      if (anchorEl.contains(target)) return
      onClose()
    }

    const handleScroll = (event: Event) => {
      const target = event.target as Node | null
      if (target && panelRef.current?.contains(target)) return
      onClose()
    }

    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', updatePosition)

    return () => {
      mounted = false
      window.cancelAnimationFrame(raf)
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('scroll', handleScroll, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [anchorEl, onClose])

  const eligiblePeople = useMemo(
    () => people.filter((person) => !takenIds.has(person.id) || selectedIds.includes(person.id)),
    [people, selectedIds, takenIds],
  )

  const filteredPeople = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return eligiblePeople
    return eligiblePeople.filter((person) =>
      [person.name, person.department, person.contact]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword)),
    )
  }, [eligiblePeople, query])

  return createPortal(
    <div
      ref={panelRef}
      className="picker-animate fixed z-[9999] w-[320px] overflow-hidden rounded-2xl border border-gray-200 bg-white/95 shadow-[0_8px_30px_rgba(0,0,0,0.12),0_4px_12px_rgba(0,0,0,0.08)] backdrop-blur-[10px]"
      style={{ top: position.top, left: position.left, maxHeight: 450 }}
      role="dialog"
      aria-label={`选择${roleLabel}`}
      onMouseDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      {/* Search Header - 新设计 */}
      <div className="border-b border-gray-100 bg-gradient-to-r from-white to-gray-50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <div className="h-5 w-1 rounded-full bg-gradient-to-b from-blue-500 to-blue-600"></div>
          <h4 className="text-sm font-bold text-gray-800">选择{roleLabel}</h4>
        </div>
        
        <div className="relative mt-3">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索姓名、部门..."
            className="w-full rounded-xl border-2 border-gray-200 py-2.5 pl-10 pr-4 text-sm text-gray-800 placeholder:text-gray-400 transition-all focus:border-blue-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.1)]"
          />
          <svg className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
        </div>
      </div>

      {/* People Grid - 卡片式布局 */}
      <div className="custom-scrollbar grid grid-cols-2 gap-2 overflow-y-auto p-3" style={{ maxHeight: 340 }}>
        {filteredPeople.length === 0 ? (
          <p className="col-span-2 py-8 text-center text-xs text-gray-400">没有可选人员</p>
        ) : (
          filteredPeople.map((person) => {
            const checked = selectedIds.includes(person.id)
            const disabled = disabledIds?.has(person.id) ?? false
            
            return (
              <div
                key={person.id}
                onClick={() => {
                  if (!disabled) onTogglePerson(person.id)
                }}
                className={`person-card cursor-pointer rounded-xl border-2 p-3 transition-all duration-200 ${
                  disabled ? 'cursor-not-allowed opacity-60' : 'hover:border-blue-300 hover:shadow-md'
                } ${
                  checked
                    ? 'border-blue-500 bg-blue-50 scale-[0.98]'
                    : 'border-gray-100 bg-white'
                }`}
                data-id={person.id}
              >
                <div className="flex items-center gap-2.5">
                  {/* Avatar */}
                  <div
                    className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-sm font-bold shadow-md bg-gradient-to-br ${getAvatarColor(person.name)} text-white ${
                      checked ? 'ring-2 ring-blue-500 ring-offset-2' : ''
                    }`}
                  >
                    {person.name.slice(0, 1)}
                  </div>
                  
                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold truncate text-gray-800">{person.name}</div>
                    {person.department && <div className="mt-0.5 text-xs truncate text-gray-500">{person.department}</div>}
                  </div>

                  {/* Check Mark */}
                  <div
                    className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full transition-all ${
                      checked ? 'bg-blue-500' : 'border-2 border-gray-300'
                    }`}
                  >
                    {checked && (
                      <svg className="h-3 w-3 checkmark-animate text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer with count - 新增 */}
      <div className="border-t border-gray-100 bg-gray-50 flex items-center justify-between px-4 py-3">
        <span className="text-xs text-gray-500">
          已选择 <strong className="text-blue-600">{selectedIds.length}</strong> 人
        </span>
        <button
          onClick={onClose}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer"
        >
          关闭
        </button>
      </div>
    </div>,
    document.body,
  )
}


