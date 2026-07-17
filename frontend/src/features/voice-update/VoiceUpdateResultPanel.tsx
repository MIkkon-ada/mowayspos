import { VoiceUpdateResultCard } from './VoiceUpdateResultCard'
import type { VoiceUpdateResultCardProps } from './voiceUpdateResultTypes'

type VoiceUpdateResultPanelProps = VoiceUpdateResultCardProps

export function VoiceUpdateResultPanel(props: VoiceUpdateResultPanelProps) {
  return (
    <VoiceUpdateResultCard {...props} />
  )
}
