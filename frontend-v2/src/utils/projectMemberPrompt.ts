import { getProjectMembers } from '../api/projects'
import type { ProjectMember } from '../types'

export async function promptProjectMember(projectId: number, title: string): Promise<ProjectMember | null> {
  const members = await getProjectMembers(projectId)
  if (!members.length) throw new Error('当前项目没有可选成员')

  const choices = members
    .map((member, index) => `${index + 1}. ${member.person_name_snapshot}（人员编号 ${member.person_id}）`)
    .join('\n')
  const value = window.prompt(`${title}\n${choices}\n请输入成员序号`)
  if (value == null) return null

  const choice = Number(value.trim())
  if (!Number.isInteger(choice) || choice < 1 || choice > members.length) {
    throw new Error('请输入列表中的有效序号')
  }
  return members[choice - 1]
}
