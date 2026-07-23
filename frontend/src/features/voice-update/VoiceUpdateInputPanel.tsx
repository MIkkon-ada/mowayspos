import type { RefObject } from 'react'
import type { Phase } from './voiceUpdateResultTypes'

type AvailableProvider = { provider: string; display_name: string; model: string }
export type VoiceInputMode = 'text' | 'voice' | 'upload'

type VoiceUpdateInputPanelProps = {
  mode: VoiceInputMode
  onModeChange: (mode: VoiceInputMode) => void
  providers: AvailableProvider[]
  selectedProvider: string
  onSelectedProviderChange: (provider: string) => void
  phase: Phase
  controlsLocked: boolean
  extractDisabled: boolean
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
  onExtract: () => void
}

const MODE_OPTIONS: { key: VoiceInputMode; label: string; path: string }[] = [
  { key: 'text', label: '文本输入', path: 'M4 6h16M4 12h16M4 18h10' },
  { key: 'voice', label: '录音输入', path: 'M12 3a3 3 0 00-3 3v5a3 3 0 006 0V6a3 3 0 00-3-3zm-7 8a7 7 0 0014 0M12 18v3' },
  { key: 'upload', label: '上传音频', path: 'M12 16V4m0 0L8 8m4-4 4 4M5 14v5h14v-5' },
]

export function VoiceUpdateInputPanel({
  mode,
  onModeChange,
  providers,
  selectedProvider,
  onSelectedProviderChange,
  phase,
  controlsLocked,
  extractDisabled,
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
  onExtract,
}: VoiceUpdateInputPanelProps) {
  return (
    <section className="voice-update-input-panel" aria-label="输入汇报内容">
      <header className="voice-update-panel-header voice-update-input-panel-header">
        <div className="voice-update-panel-heading">
          <h2>输入内容</h2>
        </div>
      </header>

      <div className="voice-update-mode-tabs" role="tablist" aria-label="输入方式">
        {MODE_OPTIONS.map(({ key, label, path }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            className={mode === key ? 'is-active' : ''}
            disabled={controlsLocked}
            onClick={() => onModeChange(key)}
          >
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d={path} /></svg>
            {label}
          </button>
        ))}
      </div>

      <div className="voice-update-input-heading">
        <h2>原始汇报内容 <em aria-hidden="true">*</em></h2>
        <span>提交前可继续修改</span>
      </div>

      {mode === 'text' && (
        <>
          <textarea
            className="voice-update-textarea"
            value={text}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="请输入本次完成、下一步计划、遇到的问题和形成的成果…"
            maxLength={5000}
          />
          <div className="voice-update-character-count">{text.length}/5000</div>
        </>
      )}

      {mode === 'voice' && (
        <div className="voice-update-audio-zone">
          <strong>{recording ? '正在录音（实时转写中）' : '录音输入'}</strong>
          <span>{timerLabel}</span>
          <button type="button" className="voice-update-task-detail-button" onClick={recording ? onStopRecording : onStartRecording}>
            {recording ? '停止录音' : '开始录音'}
          </button>
          {text && <p>{text}</p>}
        </div>
      )}

      {mode === 'upload' && (
        <div className="voice-update-audio-zone">
          <input
            ref={uploadInputRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.flac,.aac,.ogg,.wma,.amr,.webm,.mp4"
            hidden
            onChange={(event) => { const file = event.target.files?.[0]; if (file) onUploadFile(file) }}
          />
          <strong>{uploading ? `正在转写「${uploadFileName}」` : '上传音频文件'}</strong>
          <span>支持 MP3、WAV、M4A 等常见音频格式</span>
          <button type="button" className="voice-update-task-detail-button" disabled={uploading} onClick={() => uploadInputRef.current?.click()}>
            选择音频
          </button>
          {text && <p>{text}</p>}
        </div>
      )}

      <div className="voice-update-input-hints">
        <span>建议包含：本次完成、下一步计划、问题、成果</span>
        <span>内容越完整，AI 提取结果越准确</span>
      </div>

      <div className="voice-update-extract-row">
        <label className="voice-update-model-field">
          <span>提取模型</span>
          <span className="voice-update-model-select">
            <select value={selectedProvider} disabled={controlsLocked} onChange={(event) => onSelectedProviderChange(event.target.value)}>
              {providers.map((provider) => <option key={provider.provider} value={provider.provider}>{provider.display_name}（{provider.model}）</option>)}
            </select>
            {selectedProvider === 'deepseek' && <em className="voice-update-recommended">推荐</em>}
          </span>
        </label>
        <button type="button" className="voice-update-extract-button" disabled={extractDisabled} onClick={onExtract}>
          {phase === 'extracting' ? '正在提取…' : 'AI 提取'}
        </button>
      </div>
    </section>
  )
}
