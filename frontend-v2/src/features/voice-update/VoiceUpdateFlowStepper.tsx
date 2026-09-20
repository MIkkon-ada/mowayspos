import { getVoiceFlowStep, type Phase } from './voiceUpdateResultTypes'

const FLOW_STEPS = ['汇报范围', '输入内容', 'AI 提取', '人工检查'] as const

type VoiceUpdateFlowStepperProps = {
  phase: Phase
  hasContent: boolean
}

export function VoiceUpdateFlowStepper({ phase, hasContent }: VoiceUpdateFlowStepperProps) {
  const currentStep = getVoiceFlowStep(phase, hasContent)
  const steps = [...FLOW_STEPS, phase === 'submitted' ? '完成' : '提交确认']

  return (
    <nav className="voice-update-stepper" aria-label="工作汇报流程">
      {steps.map((label, index) => {
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
            {index < steps.length - 1 && <span className="voice-update-step-line" aria-hidden="true" />}
          </div>
        )
      })}
    </nav>
  )
}
