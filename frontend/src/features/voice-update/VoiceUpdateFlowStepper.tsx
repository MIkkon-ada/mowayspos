import { getVoiceFlowStep, type Phase } from './voiceUpdateResultTypes'

const FLOW_STEPS = ['选择任务', '输入内容', 'AI 提取', '人工检查', '提交确认'] as const

type VoiceUpdateFlowStepperProps = {
  phase: Phase
  selectedProjectId: number | null
  selectedSubtaskId: number | null
}

export function VoiceUpdateFlowStepper({ phase, selectedProjectId, selectedSubtaskId }: VoiceUpdateFlowStepperProps) {
  const currentStep = getVoiceFlowStep(phase, selectedProjectId, selectedSubtaskId)

  return (
    <nav className="voice-update-stepper" aria-label="工作汇报流程">
      {FLOW_STEPS.map((label, index) => {
        const step = index + 1
        const completed = step < currentStep
        const current = step === currentStep
        return (
          <div
            key={label}
            className={`voice-update-step${completed ? ' is-complete' : ''}${current ? ' is-current' : ''}`}
            aria-current={current ? 'step' : undefined}
          >
            <span className="voice-update-step-number" aria-hidden="true">{completed ? '✓' : step}</span>
            <span>{label}</span>
            {index < FLOW_STEPS.length - 1 && <span className="voice-update-step-line" aria-hidden="true" />}
          </div>
        )
      })}
    </nav>
  )
}
