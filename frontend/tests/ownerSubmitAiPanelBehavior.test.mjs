import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.resolve(here, '../src/features/settings/OwnerSubmitAiPanel.tsx'), 'utf8')

test('panel uses the public new/ignore/supplement decision contract and blocks missing duplicate choices', () => {
  assert.match(source, /ProjectInitAiDecisionAction = 'new' \| 'ignore' \| 'supplement'/)
  assert.match(source, /requiredDecisionKeys\(draft\)\.filter\(/)
  assert.match(source, /requiredDecisionKeys\(draft\)\.some\(/)
  assert.match(source, /decisions\[taskKey\] \?\? 'new'/)
  assert.match(source, /decisions\[key\] \?\? 'new'/)
})

test('panel protects asynchronous work and supports per-file recovery', () => {
  assert.match(source, /nextRun\.id !== runId/)
  assert.match(source, /clearPolling\(\)/)
  assert.match(source, /uploadQueueItem\(item, controller\)/)
  assert.match(source, /retryUpload\(item\)/)
  assert.match(source, /retryable === true/)
  assert.match(source, /setPanelState\('idle'\)/)
})

test('panel aborts analysis requests on close and ignores late results', () => {
  assert.match(source, /analysisRequestIdRef/)
  assert.match(source, /createInitAnalysisRun\(projectId, uploadedIds, currentDraft, analysisController\.signal\)/)
  assert.match(source, /retryInitAnalysisRun\(projectId, run\.id, controller\.signal\)/)
  assert.match(source, /analysisRequestIdRef\.current === requestId/)
  assert.match(source, /!controller\.signal\.aborted && analysisRequestIdRef\.current === requestId/)
  assert.match(source, /analysisRequestIdRef\.current \+= 1/)
  assert.match(source, /function handleClose\(\)[\s\S]*analysisControllerRef\.current\?\.abort\(\)/)
  assert.match(source, /isAbortError\(nextError\) \|\| !isCurrentAnalysisRequest\(requestId, analysisController\)/)
  assert.match(source, /isCurrentAnalysisRequest\(requestId, controller\) && !isAbortError\(nextError\)/)
})

test('panel aborts polling requests and prevents stale polling overlap', () => {
  assert.match(source, /getInitAnalysisRun\(projectId, runId, controller\.signal\)/)
  assert.match(source, /pollControllerRef\.current\?\.abort\(\)/)
  assert.match(source, /pollTokenRef\.current \+= 1/)
  assert.match(source, /pollInFlightTokenRef/)
  assert.match(source, /pollInFlightTokenRef\.current === token/)
})

test('panel exposes attachment actions, complete warnings, partial file results, and awaited apply errors', () => {
  assert.match(source, /downloadInitAttachmentUrl\(projectId, attachment\.id\)/)
  assert.match(source, /deleteInitAttachment\(projectId, item\.attachment\.id\)/)
  assert.match(source, /draft\.warnings\.map\(/)
  assert.match(source, /result_metadata\.file_results/)
  assert.match(source, /await onApplyDraft\(draft, selected\)/)
  assert.match(source, /应用失败：/)
})
