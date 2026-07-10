import { VoiceUpdateResultCard } from './VoiceUpdateResultCard'
import { VoiceUpdateSubmitPanel } from './VoiceUpdateSubmitPanel'
import type { VoiceUpdateResultCardProps, VoiceUpdateSubmitPanelProps } from './voiceUpdateResultTypes'

type VoiceUpdateResultPanelProps = VoiceUpdateResultCardProps & VoiceUpdateSubmitPanelProps

export function VoiceUpdateResultPanel(props: VoiceUpdateResultPanelProps) {
  const { selectedProjectName: _selectedProjectName, isProjectSelected: _isProjectSelected, ...cardProps } = props
  return (
    <div className="flex flex-col gap-4 min-w-0">
      <VoiceUpdateResultCard {...cardProps} />
      <VoiceUpdateSubmitPanel {...props} />
    </div>
  )
}
