export type PickerRect = {
  top: number
  left: number
  bottom: number
  width: number
  height: number
}

export type PickerSize = {
  width: number
  height: number
}

export type PickerViewport = {
  width: number
  height: number
}

export type PickerPosition = {
  left: number
  top: number
  placement: 'top' | 'bottom'
}

export type PickerPositionOptions = {
  gap?: number
  margin?: number
}

export function getPickerPosition(
  anchorRect: PickerRect,
  panelSize: PickerSize,
  viewport: PickerViewport,
  options?: PickerPositionOptions,
): PickerPosition

