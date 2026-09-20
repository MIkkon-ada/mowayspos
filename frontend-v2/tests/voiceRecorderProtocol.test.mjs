import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')

async function loadModule() {
  const source = fs.readFileSync(
    path.join(root, 'src/features/voice-update/voiceRecorderProtocol.ts'),
    'utf8',
  )
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

test('partial result replaces the current segment', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = emptyTranscript('已有文字')
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成', final: false,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成联调', final: false,
  })
  assert.equal(composeTranscript(state), '已有文字\n本周完成联调')
})

test('final result is idempotent by segment id', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  const event = {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成联调。', final: true,
  }
  let state = mergeTranscript(emptyTranscript(''), event)
  state = mergeTranscript(state, event)
  assert.deepEqual(state.order, ['seg-0'])
  assert.equal(composeTranscript(state), '本周完成联调。')
})

test('corrected final replaces the same segment without duplicating its order', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = mergeTranscript(emptyTranscript(''), {
    type: 'transcript', segment_id: 'seg-0', text: '完成连调', final: true,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '完成联调', final: true,
  })
  assert.deepEqual(state.order, ['seg-0'])
  assert.equal(composeTranscript(state), '完成联调')
})

test('multiple final segments preserve first-seen order', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = mergeTranscript(emptyTranscript(''), {
    type: 'transcript', segment_id: 'seg-1', text: '第一句。', final: true,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-2', text: '第二句。', final: true,
  })
  assert.equal(composeTranscript(state), '第一句。第二句。')
})

test('a final for another segment does not clear the current partial', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = mergeTranscript(emptyTranscript(''), {
    type: 'transcript', segment_id: 'seg-2', text: '正在说', final: false,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-1', text: '第一句。', final: true,
  })
  assert.deepEqual(state.partial, { segmentId: 'seg-2', text: '正在说' })
  assert.equal(composeTranscript(state), '第一句。正在说')
})

test('a late partial for an already confirmed segment is ignored', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = mergeTranscript(emptyTranscript(''), {
    type: 'transcript', segment_id: 'seg-0', text: '最终结果。', final: true,
  })
  const confirmedState = state
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '迟到的中间结果', final: false,
  })
  assert.equal(state, confirmedState)
  assert.equal(composeTranscript(state), '最终结果。')
})

test('empty transcript trims base text and only separates base from recognized text', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  assert.deepEqual(emptyTranscript('  '), {
    baseText: '',
    order: [],
    confirmed: {},
    partial: null,
  })
  assert.equal(composeTranscript(emptyTranscript('  已有文字  ')), '已有文字')

  let state = mergeTranscript(emptyTranscript('  已有文字  '), {
    type: 'transcript', segment_id: 'seg-1', text: '第一句。', final: true,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-2', text: '第二', final: false,
  })
  assert.equal(composeTranscript(state), '已有文字\n第一句。第二')
})

test('parser accepts and reconstructs every valid server message', async () => {
  const { parseServerMessage } = await loadModule()
  const cases = [
    [{ type: 'ready' }, { type: 'ready' }],
    [
      {
        type: 'started',
        model: 'fun-asr-realtime',
        session_id: 'session-1',
        packet_duration_ms: 100,
        stop_timeout_seconds: 8,
      },
      {
        type: 'started',
        model: 'fun-asr-realtime',
        session_id: 'session-1',
        packet_duration_ms: 100,
        stop_timeout_seconds: 8,
      },
    ],
    [
      {
        type: 'transcript',
        segment_id: 'seg-1',
        text: '结果',
        final: false,
        begin_time: 0,
        end_time: null,
      },
      {
        type: 'transcript',
        segment_id: 'seg-1',
        text: '结果',
        final: false,
        begin_time: 0,
        end_time: null,
      },
    ],
    [
      { type: 'done', session_id: 'session-1', duration_ms: 1234 },
      { type: 'done', session_id: 'session-1', duration_ms: 1234 },
    ],
    [
      { type: 'error', code: 'FAILED', message: '请重试', retryable: true },
      { type: 'error', code: 'FAILED', message: '请重试', retryable: true },
    ],
  ]

  for (const [wireValue, expected] of cases) {
    assert.deepEqual(parseServerMessage(JSON.stringify(wireValue)), expected)
  }
})

test('parser rejects malformed JSON, unknown types, non-objects, arrays, and missing fields', async () => {
  const { parseServerMessage } = await loadModule()
  const invalid = [
    'not json',
    'null',
    '[]',
    '"ready"',
    '{"type":"unknown"}',
    '{}',
    '{"type":"started","model":"fun-asr-realtime"}',
    '{"type":"started","model":"fun-asr-realtime","session_id":"session-1"}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果"}',
    '{"type":"done","session_id":"session-1"}',
    '{"type":"error","code":"FAILED","message":"请重试"}',
  ]
  for (const raw of invalid) assert.equal(parseServerMessage(raw), null)
})

test('parser rejects malformed fields for every message type', async () => {
  const { parseServerMessage } = await loadModule()
  const invalidValues = [
    { type: 'ready', unexpectedTypeConstraint: null, typeOverride: true },
    { type: 'started', model: 1, session_id: 'session-1', packet_duration_ms: 100, stop_timeout_seconds: 8 },
    { type: 'started', model: 'model', session_id: false, packet_duration_ms: 100, stop_timeout_seconds: 8 },
    { type: 'transcript', segment_id: 1, text: '结果', final: false },
    { type: 'transcript', segment_id: 'seg-1', text: 1, final: false },
    { type: 'transcript', segment_id: 'seg-1', text: '结果', final: 'false' },
    {
      type: 'transcript',
      segment_id: 'seg-1',
      text: '结果',
      final: false,
      begin_time: '0',
    },
    {
      type: 'transcript',
      segment_id: 'seg-1',
      text: '结果',
      final: false,
      end_time: false,
    },
    { type: 'done', session_id: 1, duration_ms: 1234 },
    { type: 'done', session_id: 'session-1', duration_ms: '1234' },
    { type: 'error', code: 1, message: '请重试', retryable: true },
    { type: 'error', code: 'FAILED', message: false, retryable: true },
    { type: 'error', code: 'FAILED', message: '请重试', retryable: 'true' },
  ]
  invalidValues[0].type = 1
  for (const value of invalidValues) {
    assert.equal(parseServerMessage(JSON.stringify(value)), null)
  }
})

test('parser rejects blank semantic fields and blank transcript text', async () => {
  const { parseServerMessage } = await loadModule()
  const invalidValues = [
    { type: 'started', model: ' ', session_id: 'session-1' },
    { type: 'started', model: 'model', session_id: '\t' },
    { type: 'transcript', segment_id: '\n', text: '结果', final: false },
    { type: 'transcript', segment_id: 'seg-1', text: '  ', final: false },
    { type: 'done', session_id: ' ', duration_ms: 1 },
    { type: 'error', code: ' ', message: '请重试', retryable: true },
    { type: 'error', code: 'FAILED', message: ' ', retryable: true },
  ]
  for (const value of invalidValues) {
    assert.equal(parseServerMessage(JSON.stringify(value)), null)
  }
})

test('parser trims identifiers, model, error code, and error message', async () => {
  const { parseServerMessage } = await loadModule()
  assert.deepEqual(
    parseServerMessage(
      JSON.stringify({
        type: 'started',
        model: ' fun-asr-realtime ',
        session_id: ' session-1 ',
        packet_duration_ms: 100,
        stop_timeout_seconds: 8,
      }),
    ),
    {
      type: 'started',
      model: 'fun-asr-realtime',
      session_id: 'session-1',
      packet_duration_ms: 100,
      stop_timeout_seconds: 8,
    },
  )
  assert.deepEqual(
    parseServerMessage(
      JSON.stringify({
        type: 'transcript',
        segment_id: ' seg-1 ',
        text: ' 识别结果 ',
        final: true,
      }),
    ),
    {
      type: 'transcript',
      segment_id: 'seg-1',
      text: ' 识别结果 ',
      final: true,
    },
  )
  assert.deepEqual(
    parseServerMessage(
      JSON.stringify({
        type: 'error',
        code: ' FAILED ',
        message: ' 请重试 ',
        retryable: true,
      }),
    ),
    { type: 'error', code: 'FAILED', message: '请重试', retryable: true },
  )
})

test('parser rejects invalid durations and transcript time ranges', async () => {
  const { parseServerMessage } = await loadModule()
  const invalidRawValues = [
    '{"type":"done","session_id":"session-1","duration_ms":-1}',
    '{"type":"done","session_id":"session-1","duration_ms":1e309}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果","final":true,"begin_time":-1}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果","final":true,"end_time":-1}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果","final":true,"begin_time":1e309}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果","final":true,"end_time":1e309}',
    '{"type":"transcript","segment_id":"seg-1","text":"结果","final":true,"begin_time":20,"end_time":10}',
  ]
  for (const raw of invalidRawValues) {
    assert.equal(parseServerMessage(raw), null)
  }
})

test('parser filters extra and prototype-shaped properties from accepted messages', async () => {
  const { parseServerMessage } = await loadModule()
  const parsed = parseServerMessage(
    '{"type":"started","model":"model","session_id":"session-1","packet_duration_ms":100,"stop_timeout_seconds":8,"extra":"drop","__proto__":{"polluted":true}}',
  )
  assert.deepEqual(parsed, {
    type: 'started',
    model: 'model',
    session_id: 'session-1',
    packet_duration_ms: 100,
    stop_timeout_seconds: 8,
  })
  assert.equal(Object.hasOwn(parsed, 'extra'), false)
  assert.equal(Object.hasOwn(parsed, '__proto__'), false)
  assert.equal(parsed.polluted, undefined)
})

test('parser accepts started timing contract boundaries', async () => {
  const { parseServerMessage } = await loadModule()
  for (const timing of [
    { packet_duration_ms: 40, stop_timeout_seconds: 2 },
    { packet_duration_ms: 100, stop_timeout_seconds: 2.5 },
    { packet_duration_ms: 250, stop_timeout_seconds: 30 },
  ]) {
    assert.deepEqual(
      parseServerMessage(JSON.stringify({
        type: 'started',
        model: 'model',
        session_id: 'session-1',
        ...timing,
      })),
      {
        type: 'started',
        model: 'model',
        session_id: 'session-1',
        ...timing,
      },
    )
  }
})

test('parser rejects out-of-range, non-integer, and non-finite started timing fields', async () => {
  const { parseServerMessage } = await loadModule()
  const invalidTimings = [
    { packet_duration_ms: 39, stop_timeout_seconds: 8 },
    { packet_duration_ms: 251, stop_timeout_seconds: 8 },
    { packet_duration_ms: 100.5, stop_timeout_seconds: 8 },
    { packet_duration_ms: 100, stop_timeout_seconds: 1.99 },
    { packet_duration_ms: 100, stop_timeout_seconds: 31 },
    { packet_duration_ms: 100, stop_timeout_seconds: Number.POSITIVE_INFINITY },
  ]
  for (const timing of invalidTimings) {
    assert.equal(parseServerMessage(JSON.stringify({
      type: 'started',
      model: 'model',
      session_id: 'session-1',
      ...timing,
    })), null)
  }
})
