function toDate(s?: string | null): Date | null {
  if (!s) return null
  const raw = s.trim()
  const utcStr = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : raw.replace(' ', 'T') + 'Z'
  const d = new Date(utcStr)
  return Number.isNaN(d.getTime()) ? null : d
}

export function fmtRelativeTime(s?: string | null): string {
  const d = toDate(s)
  if (!d) return '-'
  const diff = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function fmtYmd(year: number, month: number, day: number): string {
  return `${year}/${month}/${day}`
}

function fmtYm(year: number, month: number): string {
  return `${year}/${month}`
}

function normalizeText(s: string): string {
  return s.trim().replace(/\s+/g, '')
}

const YEAR = '\\u5e74'
const MONTH = '\\u6708'
const DAY = '\\u65e5'

function buildMonthPattern() {
  return new RegExp(`^(\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH})?$`)
}

function buildDatePattern() {
  return new RegExp(`^(\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH}|\\/|-)(\\d{1,2})(?:${DAY})?$`)
}

function buildMonthRangePattern() {
  return new RegExp(`^(\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH})?[~\\-鑷冲埌](\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH})?$`)
}

function buildDateRangePattern() {
  return new RegExp(`^(\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH}|\\/|-)(\\d{1,2})(?:${DAY})?[~\\-鑷冲埌](\\d{4})(?:${YEAR}|\\/|-)?(\\d{1,2})(?:${MONTH}|\\/|-)(\\d{1,2})(?:${DAY})?$`)
}

function parseMonthLike(raw: string): { year: number; month: number } | null {
  const m = raw.match(buildMonthPattern())
  if (!m) return null
  return { year: +m[1], month: +m[2] }
}

function parseDateLike(raw: string): { year: number; month: number; day: number } | null {
  const m = raw.match(buildDatePattern())
  if (!m) return null
  return { year: +m[1], month: +m[2], day: +m[3] }
}

function parseMonthRangeLike(raw: string): { sy: number; sm: number; ey: number; em: number } | null {
  const m = raw.match(buildMonthRangePattern())
  if (!m) return null
  return { sy: +m[1], sm: +m[2], ey: +m[3], em: +m[4] }
}

function parseDateRangeLike(raw: string): { sy: number; sm: number; sd: number; ey: number; em: number; ed: number } | null {
  const m = raw.match(buildDateRangePattern())
  if (!m) return null
  return { sy: +m[1], sm: +m[2], sd: +m[3], ey: +m[4], em: +m[5], ed: +m[6] }
}

export function fmtShort(s?: string | null): string {
  const d = toDate(s)
  if (!d) return s ? s.replace('T', ' ').slice(5, 16) : '-'
  return `${fmtYmd(d.getFullYear(), d.getMonth() + 1, d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fmtFull(s?: string | null): string {
  const d = toDate(s)
  if (!d) return s ? s.replace('T', ' ').slice(0, 16) : '-'
  return `${fmtYmd(d.getFullYear(), d.getMonth() + 1, d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fmtTime(s?: string | null): string {
  const d = toDate(s)
  if (!d) return '-'
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fmtDate(s?: string | null): string {
  const d = toDate(s)
  if (!d) return s ? s.slice(0, 10).replace(/-/g, '/') : '-'
  return fmtYmd(d.getFullYear(), d.getMonth() + 1, d.getDate())
}

export function fmtMonth(s?: string | null): string {
  if (!s) return '-'
  const raw = normalizeText(s)
  if (!raw) return '-'

  const range = parseMonthRangeLike(raw)
  if (range) return `${fmtYm(range.sy, range.sm)}~${fmtYm(range.ey, range.em)}`

  const month = parseMonthLike(raw)
  if (month) return fmtYm(month.year, month.month)

  return raw
}

export function fmtPlanTime(s?: string | null): string {
  if (!s) return '-'
  const raw = normalizeText(s)
  if (!raw) return '-'

  const dateRange = parseDateRangeLike(raw)
  if (dateRange) return `${fmtYmd(dateRange.sy, dateRange.sm, dateRange.sd)}~${fmtYmd(dateRange.ey, dateRange.em, dateRange.ed)}`

  const monthRange = parseMonthRangeLike(raw)
  if (monthRange) return `${fmtYm(monthRange.sy, monthRange.sm)}~${fmtYm(monthRange.ey, monthRange.em)}`

  const date = parseDateLike(raw)
  if (date) return fmtYmd(date.year, date.month, date.day)

  const month = parseMonthLike(raw)
  if (month) return fmtYm(month.year, month.month)

  return raw
    .replace(new RegExp(YEAR, 'g'), '/')
    .replace(new RegExp(MONTH, 'g'), '/')
    .replace(new RegExp(DAY, 'g'), '/')
    .replace(/-/g, '/')
}
