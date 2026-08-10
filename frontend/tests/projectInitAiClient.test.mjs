import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import ts from 'typescript'

const apiPath = fileURLToPath(new URL('../src/api/projectInitAi.ts', import.meta.url))

function makeClientModule() {
  return `
    export class ApiError extends Error {
      constructor(status, message, body) { super(message); this.status = status; this.body = body }
    }
    export async function apiGet(path) { return globalThis.__projectInitFakeClient.get(path) }
    export async function apiPost(path, body) { return globalThis.__projectInitFakeClient.post(path, body) }
    export async function apiDelete(path) { return globalThis.__projectInitFakeClient.delete(path) }
  `
}

async function loadApi() {
  const source = readFileSync(apiPath, 'utf8')
  const transpiled = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    fileName: apiPath,
  }).outputText
  const clientUrl = `data:text/javascript,${encodeURIComponent(makeClientModule())}`
  const rewritten = transpiled.replace(/from ['"]\.\/client['"]/g, `from ${JSON.stringify(clientUrl)}`)
  return import(`data:text/javascript,${encodeURIComponent(rewritten)}`)
}

class FakeXHR {
  static instances = []

  constructor() {
    this.upload = {}
    this.status = 0
    this.responseText = ''
    this.timeout = 0
    this.aborted = false
    FakeXHR.instances.push(this)
  }

  open(method, url) {
    this.method = method
    this.url = url
  }

  send(form) {
    this.form = form
  }

  abort() {
    this.aborted = true
    this.onabort?.()
  }

  progress(loaded, total) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total })
  }

  respond(status, body) {
    this.status = status
    this.responseText = body === undefined ? '' : JSON.stringify(body)
    this.onload?.()
  }

  timeoutNow() {
    this.ontimeout?.()
  }
}

const originalXHR = globalThis.XMLHttpRequest
const originalClient = globalThis.__projectInitFakeClient
const originalFetch = globalThis.fetch

test.after(() => {
  globalThis.XMLHttpRequest = originalXHR
  globalThis.__projectInitFakeClient = originalClient
  globalThis.fetch = originalFetch
})

test('upload client reports progress and decodes a valid attachment through fake XHR', async () => {
  globalThis.XMLHttpRequest = FakeXHR
  const api = await loadApi()
  const progress = []
  const promise = api.uploadInitAttachments(7, [{ name: 'brief.txt', size: 4 }], (value) => progress.push(value))
  const xhr = FakeXHR.instances.at(-1)
  xhr.progress(2, 4)
  xhr.respond(201, {
    id: 8,
    project_id: 7,
    storage_key: '8.txt',
    original_name: 'brief.txt',
    mime_type: 'text/plain',
    size_bytes: 4,
    uploaded_by: 'owner',
    uploaded_by_person_id: null,
    created_at: '2026-08-10T00:00:00Z',
    updated_at: '2026-08-10T00:00:00Z',
    deleted_at: null,
    deleted_by: '',
  })
  const result = await promise
  assert.equal(result[0].id, 8)
  assert.deepEqual(progress, [50, 100])
  assert.ok(xhr.timeout >= 90_000)
})

test('upload client preserves AbortSignal cancellation and aborts XHR', async () => {
  globalThis.XMLHttpRequest = FakeXHR
  const api = await loadApi()
  const controller = new AbortController()
  const promise = api.uploadInitAttachments(7, [{ name: 'brief.txt', size: 1 }], undefined, controller.signal)
  const xhr = FakeXHR.instances.at(-1)
  controller.abort()
  await assert.rejects(promise, (error) => error?.name === 'AbortError')
  assert.equal(xhr.aborted, true)
})

test('upload client rejects on timeout and preserves FastAPI detail arrays', async () => {
  globalThis.XMLHttpRequest = FakeXHR
  const api = await loadApi()
  const timeoutPromise = api.uploadInitAttachments(7, [{ name: 'brief.txt', size: 1 }])
  const timeoutXhr = FakeXHR.instances.at(-1)
  timeoutXhr.timeoutNow()
  await assert.rejects(timeoutPromise, (error) => error?.name === 'ProjectInitApiError' && error.code === 'TIMEOUT_ERROR')

  const detailPromise = api.uploadInitAttachments(7, [{ name: 'brief.txt', size: 1 }])
  const detailXhr = FakeXHR.instances.at(-1)
  detailXhr.respond(422, { detail: [{ msg: 'file is too large' }, { msg: 'invalid signature' }] })
  await assert.rejects(detailPromise, (error) => error?.name === 'ProjectInitApiError' && error.detail.includes('file is too large') && error.detail.includes('invalid signature'))
})

test('analysis responses reject invalid status and non-positive IDs at runtime', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    text: async () => JSON.stringify({
      id: 0,
      project_id: 7,
      attachment_ids: [8],
      status: 'not-a-status',
      stage: 'reading',
      progress: 0,
      error_message: '',
      draft: [],
      result_metadata: {},
      created_at: null,
      started_at: null,
      finished_at: null,
      applied_at: null,
    }),
  })
  const api = await loadApi()
  await assert.rejects(api.getLatestInitAnalysisRun(7), (error) => error?.name === 'ProjectInitApiError' && error.code === 'RESPONSE_VALIDATION_ERROR')
})

test('failed analysis runs accept an empty draft and preserve status and error message', async () => {
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    text: async () => JSON.stringify({
      id: 9,
      project_id: 7,
      attachment_ids: [8],
      status: 'failed',
      stage: 'failed',
      progress: 100,
      error_message: 'AI provider unavailable',
      draft: { tasks: [], warnings: [] },
      result_metadata: {},
      created_at: null,
      started_at: null,
      finished_at: '2026-08-10T00:00:00Z',
      applied_at: null,
    }),
  })
  const api = await loadApi()
  const run = await api.getInitAnalysisRun(7, 9)
  assert.equal(run.status, 'failed')
  assert.equal(run.error_message, 'AI provider unavailable')
  assert.deepEqual(run.draft, { tasks: [], warnings: [] })
})

test('analysis draft validators still reject invalid task elements and IDs', async () => {
  const baseRun = {
    id: 9,
    project_id: 7,
    attachment_ids: [8],
    status: 'completed',
    stage: 'completed',
    progress: 100,
    error_message: '',
    result_metadata: {},
    created_at: null,
    started_at: null,
    finished_at: '2026-08-10T00:00:00Z',
    applied_at: null,
  }
  const invalidResponses = [
    { ...baseRun, draft: { tasks: [null], warnings: [] } },
    { ...baseRun, attachment_ids: [0], draft: { tasks: [], warnings: [] } },
    { ...baseRun, draft: { tasks: [], warnings: [], provider: 42 } },
  ]

  for (const response of invalidResponses) {
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(response),
    })
    const api = await loadApi()
    await assert.rejects(api.getInitAnalysisRun(7, 9), (error) => error?.name === 'ProjectInitApiError' && error.code === 'RESPONSE_VALIDATION_ERROR')
  }
})

test('analysis creation sends the typed current_draft snapshot and deduplicated attachment IDs', async () => {
  let requestBody
  globalThis.fetch = async (_path, options) => {
    requestBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 201,
      text: async () => JSON.stringify({
        id: 9,
        project_id: 7,
        attachment_ids: [8],
        status: 'queued',
        stage: 'reading',
        progress: 0,
        error_message: '',
        draft: [],
        result_metadata: {},
        created_at: null,
        started_at: null,
        finished_at: null,
        applied_at: null,
      }),
    }
  }
  const api = await loadApi()
  const currentDraft = [{
    title: 'Current task',
    description: 'A snapshot',
    owner: 'Owner',
    helper: '',
    plan_start: '',
    plan_end: '',
    subtasks: [{
      title: 'Current subtask',
      evaluation_standard: '',
      assignee: '',
      assignee_id: null,
      helper: '',
      helper_ids: [],
      plan_start: '',
      plan_end: '',
    }],
  }]
  await api.createInitAnalysisRun(7, [8, 8], currentDraft)
  assert.deepEqual(requestBody, { attachment_ids: [8], current_draft: currentDraft })
})

test('analysis creation and retry forward AbortSignal to fetch', async () => {
  const calls = []
  const responseRun = {
    id: 9,
    project_id: 7,
    attachment_ids: [8],
    status: 'queued',
    stage: 'reading',
    progress: 0,
    error_message: '',
    draft: [],
    result_metadata: {},
    created_at: null,
    started_at: null,
    finished_at: null,
    applied_at: null,
  }
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options })
    return {
      ok: true,
      status: 201,
      text: async () => JSON.stringify(responseRun),
    }
  }
  globalThis.__projectInitFakeClient = {
    get: async () => ({}),
    post: async () => responseRun,
    delete: async () => ({}),
  }
  const api = await loadApi()
  const controller = new AbortController()
  await api.createInitAnalysisRun(7, [8], [], controller.signal)
  await api.retryInitAnalysisRun(7, 9, controller.signal)
  assert.equal(calls.length, 2)
  assert.notEqual(calls[0].options.signal, controller.signal)
  assert.notEqual(calls[1].options.signal, controller.signal)
  assert.equal(calls[0].options.signal.aborted, false)
  assert.equal(calls[1].options.signal.aborted, false)
})

test('analysis run GET forwards cancellation and rejects with a stable abort error', async () => {
  let observedSignal
  let abortObserved = false
  const originalClearTimeout = globalThis.clearTimeout
  let clearCalls = 0
  globalThis.clearTimeout = (handle) => {
    clearCalls += 1
    return originalClearTimeout(handle)
  }
  globalThis.fetch = async (_path, options) => {
    observedSignal = options.signal
    return new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => {
        abortObserved = true
        reject(new DOMException('aborted', 'AbortError'))
      }, { once: true })
    })
  }
  globalThis.__projectInitFakeClient = {
    get: async () => ({}),
    post: async () => ({}),
    delete: async () => ({}),
  }
  try {
    const api = await loadApi()
    const controller = new AbortController()
    const request = api.getInitAnalysisRun(7, 9, controller.signal)
    controller.abort()
    await assert.rejects(request, (error) => error?.name === 'ProjectInitApiError' && error.code === 'ABORT_ERROR')
    assert.ok(observedSignal)
    assert.equal(observedSignal.aborted, true)
    assert.equal(abortObserved, true)
    assert.equal(clearCalls, 1)
  } finally {
    globalThis.clearTimeout = originalClearTimeout
  }
})

test('stalled analysis POST times out and clears its timer', async () => {
  const originalSetTimeout = globalThis.setTimeout
  const originalClearTimeout = globalThis.clearTimeout
  let clearCalls = 0
  globalThis.setTimeout = (callback, delay) => {
    assert.equal(delay, 90_000)
    callback()
    return 123
  }
  globalThis.clearTimeout = (handle) => {
    assert.equal(handle, 123)
    clearCalls += 1
  }
  globalThis.fetch = async () => new Promise(() => {})
  globalThis.__projectInitFakeClient = {
    get: async () => ({}),
    post: async () => ({}),
    delete: async () => ({}),
  }
  try {
    const api = await loadApi()
    await assert.rejects(
      api.createInitAnalysisRun(7, [8], [], new AbortController().signal),
      (error) => error?.name === 'ProjectInitApiError' && error.code === 'TIMEOUT_ERROR',
    )
    assert.equal(clearCalls, 1)
  } finally {
    globalThis.setTimeout = originalSetTimeout
    globalThis.clearTimeout = originalClearTimeout
  }
})
