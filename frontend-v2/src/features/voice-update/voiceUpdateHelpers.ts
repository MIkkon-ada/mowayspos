export function formatTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

// WebM/Blob -> 16kHz mono WAV, for Dashscope Paraformer compatibility.
export async function encodeToWav(blob: Blob): Promise<Blob> {
  const TARGET_RATE = 16000
  const arrayBuffer = await blob.arrayBuffer()
  const audioCtx = new AudioContext()
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)
  await audioCtx.close()

  const targetLength = Math.ceil(audioBuffer.duration * TARGET_RATE)
  const offlineCtx = new OfflineAudioContext(1, targetLength, TARGET_RATE)
  const source = offlineCtx.createBufferSource()
  source.buffer = audioBuffer
  source.connect(offlineCtx.destination)
  source.start(0)
  const resampled = await offlineCtx.startRendering()

  const pcm = resampled.getChannelData(0)
  const length = pcm.length
  const wavBuf = new ArrayBuffer(44 + length * 2)
  const view = new DataView(wavBuf)
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i))
  }

  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + length * 2, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, TARGET_RATE, true)
  view.setUint32(28, TARGET_RATE * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, length * 2, true)

  let off = 44
  for (let i = 0; i < length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    off += 2
  }

  return new Blob([wavBuf], { type: 'audio/wav' })
}
