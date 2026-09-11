// Unified API client: all requests include cookie credentials and share error handling.
export class ApiError extends Error {
  status: number
  body: unknown
  readonly code: string

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.code = extractCode(body)
  }

  /** 401 means unauthenticated; app layers may redirect to login. */
  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

function extractCode(body: unknown): string {
  if (!body || typeof body !== 'object') return 'API_ERROR'
  const code = (body as { code?: unknown }).code
  return typeof code === 'string' && code.trim() ? code.trim() : 'API_ERROR'
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers,
    body: payload,
  })

  let parsed: unknown = null
  const text = await response.text()
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }

  if (!response.ok) {
    const message = extractMessage(parsed) || `请求失败：${response.status}`
    if (response.status === 401 && !path.startsWith('/api/auth/login')) {
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.replace('/login?reason=session_expired')
      }
    }
    throw new ApiError(response.status, message, parsed)
  }

  return parsed as T
}

function extractMessage(body: unknown): string {
  if (!body || typeof body !== 'object') return ''
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return {
      wecom_directory_disabled: '请先配置 WECOM_CORPID 和 WECOM_SECRET，然后重启后端服务',
      wecom_login_disabled: '企业微信扫码登录尚未配置完整，请检查 WECOM_CORPID、WECOM_AGENT_ID、WECOM_SECRET 和 WECOM_REDIRECT_URI',
    }[detail] || detail
  }
  if (detail && typeof detail === 'object') {
    const msg = (detail as { message?: unknown }).message
    if (typeof msg === 'string') return msg
  }
  return ''
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PATCH', path, body)
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  let parsed: unknown = null
  const text = await response.text()
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }
  if (!response.ok) {
    const detail = parsed && typeof parsed === 'object' ? (parsed as { detail?: unknown }).detail : null
    const msg = typeof detail === 'string' ? detail : `上传失败：${response.status}`
    throw new ApiError(response.status, msg, parsed)
  }
  return parsed as T
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body)
}

export function apiDelete<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('DELETE', path, body)
}
