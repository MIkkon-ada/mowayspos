import type { BatchPersonItem } from '../../api/people'
import { SYSTEM_ROLES, SYSTEM_ROLE_NORMAL, SYSTEM_ROLE_LABELS } from '../../domain/roles'

export { SYSTEM_ROLES }

export function fmtLogTime(s?: string) {
  if (!s) return '-'
  const d = new Date(s.endsWith('Z') ? s : `${s}Z`)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function parsePeopleText(raw: string): BatchPersonItem[] {
  const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean)
  if (!lines.length) return []

  const isTsv = lines.some((l) => l.includes('\t'))
  if (isTsv) {
    const headerIdx = lines.findIndex((l) => l.includes('姓名') || l.includes('名字') || l.includes('name'))
    const dataLines = headerIdx >= 0 ? lines.slice(headerIdx + 1) : lines
    const header = headerIdx >= 0 ? lines[headerIdx].split('\t').map((h) => h.trim()) : []
    const col = (row: string[], ...keys: string[]) => {
      for (const k of keys) {
        const i = header.findIndex((h) => h.includes(k))
        if (i >= 0 && row[i]) return row[i].trim()
      }
      return ''
    }
    return dataLines
      .map((l) => {
        const row = l.split('\t').map((c) => c.trim())
        const name = header.length ? col(row, '姓名', '名字', 'name') : row[0]
        if (!name) return null
        return {
          name,
          role: col(row, '职务', '职位', '岗位', 'role') || '',
          department: col(row, '部门', '团队', 'dept') || '',
          system_role: (() => {
            const raw = col(row, '系统角色', '权限', 'system_role')
            const found = Object.entries(SYSTEM_ROLE_LABELS).find(([, label]) => raw.includes(label))
            return found ? found[0] : SYSTEM_ROLE_NORMAL
          })(),
          contact: col(row, '联系', '电话', '邮件', 'contact') || '',
        }
      })
      .filter(Boolean) as BatchPersonItem[]
  }

  return lines.map((name) => ({ name, role: '', department: '', system_role: SYSTEM_ROLE_NORMAL, contact: '' }))
}
