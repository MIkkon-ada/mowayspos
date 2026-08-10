import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const apiPath = fileURLToPath(new URL('../src/api/projectInitAi.ts', import.meta.url))

function readApi() {
  assert.equal(existsSync(apiPath), true, 'project init AI API client must exist')
  return readFileSync(apiPath, 'utf8')
}

test('exports the strict project-init AI contract types', () => {
  const source = readApi()
  for (const typeName of [
    'ProjectInitAttachment',
    'ProjectInitAnalysisRunStatus',
    'ProjectInitAnalysisStage',
    'Evidence',
    'AgentSubTask',
    'AgentTask',
    'ProjectInitDraft',
    'ProjectInitApiError',
  ]) {
    assert.match(source, new RegExp(`export (type|interface|class) ${typeName}`), `${typeName} is missing`)
  }
  for (const status of ['queued', 'processing', 'completed', 'partial_failed', 'failed']) {
    assert.match(source, new RegExp(`'${status}'`))
  }
  assert.match(source, /applied_at/)
  assert.match(source, /snapshot/)
  assert.match(source, /error_message/)
})

test('exposes attachment and analysis run operations on the backend paths', () => {
  const source = readApi()
  for (const name of [
    'listInitAttachments',
    'uploadInitAttachments',
    'downloadInitAttachmentUrl',
    'deleteInitAttachment',
    'createInitAnalysisRun',
    'getLatestInitAnalysisRun',
    'getInitAnalysisRun',
    'retryInitAnalysisRun',
    'applyInitAnalysisRun',
  ]) {
    assert.match(source, new RegExp(`export (async )?function ${name}`), `${name} is missing`)
  }
  assert.match(source, /init-attachments/)
  assert.match(source, /init-analysis-runs/)
  assert.match(source, /XMLHttpRequest/)
  assert.match(source, /withCredentials\s*=\s*true/)
  assert.match(source, /onprogress/)
})

test('validates positive IDs, deduplicates attachment IDs, and preserves API errors', () => {
  const source = readApi()
  assert.match(source, /Number\.isInteger/)
  assert.match(source, /<= 0/)
  assert.match(source, /new Set\(attachmentIds\.map/)
  assert.match(source, /status/)
  assert.match(source, /detail/)
  assert.match(source, /JSON_PARSE_ERROR/)
})
