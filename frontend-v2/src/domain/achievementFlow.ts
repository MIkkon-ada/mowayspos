export type AchievementAddressAction =
  | { ok: true; url: string }
  | { ok: false; message: string }

export function getAchievementAddressAction(fileLink?: string | null): AchievementAddressAction {
  const url = (fileLink || '').trim()
  const missingValues = new Set(['无', '-', '暂无', '未填写', '无地址'])
  if (!url || missingValues.has(url)) {
    return { ok: false, message: '该成果暂未登记存储地址' }
  }
  return { ok: true, url }
}
