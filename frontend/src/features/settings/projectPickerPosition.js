const DEFAULT_GAP = 8
const DEFAULT_MARGIN = 16

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

export function getPickerPosition(anchorRect, panelSize, viewport, options = {}) {
  const gap = options.gap ?? DEFAULT_GAP
  const margin = options.margin ?? DEFAULT_MARGIN
  const minLeft = margin
  const maxLeft = Math.max(margin, viewport.width - panelSize.width - margin)
  const maxTop = Math.max(margin, viewport.height - panelSize.height - margin)

  const spaceBelow = viewport.height - anchorRect.bottom - gap - margin
  const spaceAbove = anchorRect.top - gap - margin
  const shouldPlaceAbove = spaceBelow < panelSize.height && spaceAbove > spaceBelow

  const left = clamp(anchorRect.left, minLeft, maxLeft)
  const top = shouldPlaceAbove
    ? clamp(anchorRect.top - gap - panelSize.height, margin, maxTop)
    : clamp(anchorRect.bottom + gap, margin, maxTop)

  return {
    left,
    top,
    placement: shouldPlaceAbove ? 'top' : 'bottom',
  }
}
