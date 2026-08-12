export type MenuTriggerBounds = Pick<DOMRect, 'bottom'>

export function getMyTaskMenuPlacement(
  trigger: MenuTriggerBounds,
  viewportHeight: number,
  menuHeight: number,
  gap: number,
): 'top' | 'bottom' {
  return viewportHeight - trigger.bottom < menuHeight + gap ? 'top' : 'bottom'
}
