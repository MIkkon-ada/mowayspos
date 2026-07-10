import { useEffect, useRef, useState } from 'react'

type UseVoiceRecorderArgs = {
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}

const TARGET_SAMPLE_RATE = 16000
const PROCESSOR_BUFFER_SIZE = 4096

function downsample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input
  const ratio = fromRate / toRate
  const outLen = Math.round(input.length / ratio)
  const out = new Float32Array(outLen)
  for (let i = 0; i < outLen; i++) {
    const start = Math.round(i * ratio)
    const end = Math.round((i + 1) * ratio)
    let sum = 0, count = 0
    for (let j = start; j < end && j < input.length; j++) { sum += input[j]; count++ }
    out[i] = count > 0 ? sum / count : 0
  }
  return out
}

function float32ToInt16(buf: Float32Array): ArrayBuffer {
  const out = new Int16Array(buf.length)
  for (let i = 0; i < buf.length; i++) {
    const s = Math.max(-1, Math.min(1, buf[i]))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out.buffer
}

export function useVoiceRecorder({ setText, setError }: UseVoiceRecorderArgs) {
  const [recording, setRecording] = useState(false)
  const [transcribing] = useState(false)
  const [timer, setTimer] = useState(0)

  const timerRef = useRef<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const committedRef = useRef('')
  const partialRef = useRef('')

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      _cleanup()
    }
  }, [])

  function _cleanup() {
    processorRef.current?.disconnect()
    processorRef.current = null
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    const ws = wsRef.current
    wsRef.current = null
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('stop')
      // 让服务端发完最后结果后再关闭；3s 后强制关
      setTimeout(() => { if (ws.readyState !== WebSocket.CLOSED) ws.close() }, 3000)
    }
  }

  async function startRecording() {
    setError(null)

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('麦克风权限被拒绝，请在浏览器地址栏左侧点击锁形图标允许麦克风访问')
      return
    }
    streamRef.current = stream

    committedRef.current = ''
    partialRef.current = ''

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/transcribe/stream`)
    wsRef.current = ws

    const opened = await new Promise<boolean>((resolve) => {
      const t = setTimeout(() => resolve(false), 6000)
      ws.addEventListener('open', () => { clearTimeout(t); resolve(true) }, { once: true })
      ws.addEventListener('error', () => { clearTimeout(t); resolve(false) }, { once: true })
    })

    if (!opened || ws.readyState !== WebSocket.OPEN) {
      setError('实时转写连接失败，请检查网络或 API Key 配置')
      stream.getTracks().forEach(t => t.stop())
      wsRef.current = null
      return
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as { text?: string; final?: boolean; error?: string }
        if (data.error) { setError(data.error); return }
        if (data.text) {
          if (data.final) {
            committedRef.current += data.text
            partialRef.current = ''
          } else {
            partialRef.current = data.text
          }
          setText(committedRef.current + partialRef.current)
        }
      } catch { /* ignore malformed messages */ }
    }

    ws.onerror = () => setError('实时转写出错，请重试')

    const audioCtx = new AudioContext()
    audioCtxRef.current = audioCtx
    const source = audioCtx.createMediaStreamSource(stream)
    // eslint-disable-next-line deprecation/deprecation
    const processor = audioCtx.createScriptProcessor(PROCESSOR_BUFFER_SIZE, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (e) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
      const input = e.inputBuffer.getChannelData(0)
      const resampled = downsample(input, audioCtx.sampleRate, TARGET_SAMPLE_RATE)
      wsRef.current.send(float32ToInt16(resampled))
    }

    source.connect(processor)
    processor.connect(audioCtx.destination)

    setRecording(true)
    setTimer(0)
    timerRef.current = window.setInterval(() => setTimer(t => t + 1), 1000)
  }

  function stopRecording() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    _cleanup()
    setRecording(false)
  }

  return { recording, transcribing, timer, startRecording, stopRecording }
}
