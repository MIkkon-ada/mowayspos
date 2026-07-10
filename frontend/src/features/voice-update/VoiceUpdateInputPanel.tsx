import type { RefObject } from 'react'

type AvailableProvider = { provider: string; display_name: string; model: string }
type InputMode = 'voice' | 'upload' | 'text'

type VoiceUpdateInputPanelProps = {
  mode: InputMode
  onModeChange: (mode: InputMode) => void
  providers: AvailableProvider[]
  selectedProvider: string
  onSelectedProviderChange: (provider: string) => void
  phase: 'input' | 'extracting' | 'extracted' | 'submitting' | 'submitted'
  transcribing: boolean
  recording: boolean
  timerLabel: string
  text: string
  onTextChange: (value: string) => void
  uploading: boolean
  uploadFileName: string
  uploadInputRef: RefObject<HTMLInputElement | null>
  onUploadFile: (file: File) => void
  onStartRecording: () => void
  onStopRecording: () => void
  onClearText: () => void
}

export function VoiceUpdateInputPanel({
  mode,
  onModeChange,
  providers,
  selectedProvider,
  onSelectedProviderChange,
  phase,
  transcribing,
  recording,
  timerLabel,
  text,
  onTextChange,
  uploading,
  uploadFileName,
  uploadInputRef,
  onUploadFile,
  onStartRecording,
  onStopRecording,
  onClearText,
}: VoiceUpdateInputPanelProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-2xl border p-1.5 flex gap-1" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
        {([
          { key: 'voice', label: '录音输入', icon: '🎙️' },
          { key: 'upload', label: '上传音频', icon: '📻' },
          { key: 'text', label: '粘贴文本', icon: '📝' },
        ] as { key: InputMode; label: string; icon: string }[]).map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => onModeChange(key)}
            className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
            style={{
              background: mode === key ? '#0369A1' : 'transparent',
              color: mode === key ? 'white' : '#64748B',
              boxShadow: mode === key ? '0 2px 8px rgba(3,105,161,0.3)' : 'none',
            }}
          >
            {icon} {label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border p-4" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
        <label className="block text-xs font-bold text-slate-500 mb-2">提取模型</label>
        <select
          value={selectedProvider}
          onChange={(e) => onSelectedProviderChange(e.target.value)}
          className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-white text-slate-700 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/30"
          disabled={phase === 'extracting'}
        >
          {providers.map((p) => (
            <option key={p.provider} value={p.provider}>
              {p.display_name} ({p.model})
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-2xl border p-5 flex flex-col items-center" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
        <div className="w-full flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-700">本次更新内容</h3>
          <span className="text-xs text-slate-400">提交前可编辑</span>
        </div>

        {mode === 'voice' && (
          <div className="w-full flex flex-col items-center">
            {transcribing && (
              <div className="w-full mb-4 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 flex items-center gap-2">
                <svg className="animate-spin" style={{ width: 14, height: 14 }} fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                正在转写录音，请稍候
              </div>
            )}
            {recording && (
              <div className="flex items-center gap-2 mb-4">
                <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" style={{ animation: 'pulse 1.5s infinite' }} />
                <span className="text-sm font-semibold text-red-500">正在识别...</span>
              </div>
            )}
            <div className="text-5xl font-bold text-slate-800 tracking-tighter mb-4">{timerLabel}</div>

            {recording && (
              <div className="flex items-end gap-1 h-8 mb-4">
                {Array.from({ length: 24 }, (_, i) => (
                  <div
                    key={i}
                    className="w-0.5 rounded-full bg-sky-400"
                    style={{ height: `${6 + Math.sin(i * 0.8) * 10 + 8}px`, animation: `wave ${0.8 + i * 0.05}s ease-in-out infinite` }}
                  />
                ))}
              </div>
            )}

            <button
              onClick={recording ? onStopRecording : onStartRecording}
              disabled={transcribing}
              className="w-16 h-16 rounded-full flex items-center justify-center text-white cursor-pointer mb-4 disabled:opacity-40"
              style={{ background: recording ? '#DC2626' : '#0369A1', boxShadow: recording ? '0 0 0 8px rgba(220,38,38,0.15)' : undefined }}
            >
              {recording ? (
                <svg style={{ width: 24, height: 24 }} fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg style={{ width: 24, height: 24 }} fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              )}
            </button>

            <div className="w-full min-h-16 border border-slate-100 rounded-xl p-3 bg-slate-50 text-sm text-slate-700 leading-relaxed">
              {recording
                ? <span className="text-slate-400 italic">录音中，停止后将自动转写</span>
                : text || <span className="text-slate-300">点击录音按钮开始，停止后自动转为文字</span>
              }
            </div>
            {text && !recording && (
              <button className="mt-2 text-xs text-slate-400 hover:text-red-500" onClick={onClearText}>
                清除
              </button>
            )}
          </div>
        )}

        {mode === 'text' && (
          <div className="w-full">
            <textarea
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              placeholder="请粘贴或输入本次进展内容，AI 将自动提取关键信息"
              className="w-full border border-slate-200 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 resize-none"
              style={{ height: 200 }}
              maxLength={5000}
            />
            <div className="text-right text-xs text-slate-400 mt-1">{text.length}/5000</div>
          </div>
        )}

        {mode === 'upload' && (
          <div className="w-full">
            <input
              ref={uploadInputRef}
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.flac,.aac,.ogg,.wma,.amr,.webm,.mp4"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onUploadFile(f) }}
            />
            <div
              className="w-full flex flex-col items-center justify-center border-2 border-dashed rounded-xl cursor-pointer hover:border-blue-400 transition-colors"
              style={{ height: 140, borderColor: uploading ? '#3B82F6' : '#E2E8F0' }}
              onClick={() => !uploading && uploadInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) onUploadFile(f) }}
            >
              {uploading ? (
                <>
                  <svg className="animate-spin" style={{ width: 32, height: 32, color: '#3B82F6' }} fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <p className="text-sm text-blue-500 font-medium mt-2">正在转写「{uploadFileName}」</p>
                  <p className="text-xs text-slate-400 mt-1">识别中，请稍候</p>
                </>
              ) : (
                <>
                  <svg style={{ width: 36, height: 36, color: '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-sm text-slate-500 font-medium mt-2">点击或拖拽上传音频文件</p>
                  <p className="text-xs text-slate-400 mt-1">支持 MP3、WAV、M4A 等格式</p>
                </>
              )}
            </div>
            {text && (
              <>
                <textarea
                  value={text}
                  onChange={(e) => onTextChange(e.target.value)}
                  placeholder="转写结果将显示在这里，可手动编辑"
                  className="w-full mt-3 border border-slate-200 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 resize-none"
                  style={{ height: 120 }}
                  maxLength={5000}
                />
                <div className="text-right text-xs text-slate-400 mt-1">{text.length}/5000</div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border p-4" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">请围绕以下问题进行说明</h3>
        <div className="space-y-2.5">
          {['本周完成了什么？', '形成了什么成果？', '当前有什么问题？', '下周做什么，需要协调谁？'].map((q, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style={{ background: '#0369A1' }}>{i + 1}</span>
              <span className="text-sm text-slate-700">{q}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
