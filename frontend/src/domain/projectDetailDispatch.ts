type DispatchResult = {
  ok: boolean
  dispatched_to: number
}

type ProjectDetailDispatchDependencies<TProject> = {
  dispatch: (projectId: number) => Promise<DispatchResult>
  refresh: (projectId: number) => Promise<TProject>
  onSuccess: (recipientCount: number) => void
  onDispatchError: (message: string) => void
  onRefreshError: () => void
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export async function runProjectDetailDispatch<TProject>(
  projectId: number,
  dependencies: ProjectDetailDispatchDependencies<TProject>,
): Promise<TProject | null> {
  let result: DispatchResult
  try {
    result = await dependencies.dispatch(projectId)
  } catch (error) {
    dependencies.onDispatchError(errorMessage(error, '下发失败'))
    return null
  }

  dependencies.onSuccess(result.dispatched_to)
  try {
    return await dependencies.refresh(projectId)
  } catch {
    dependencies.onRefreshError()
    return null
  }
}

export function createProjectDetailDispatcher<TProject>(
  dependencies: ProjectDetailDispatchDependencies<TProject>,
): (projectId: number) => Promise<TProject | null> | null {
  let inFlight = false

  return (projectId: number) => {
    if (inFlight) return null
    inFlight = true
    return runProjectDetailDispatch(projectId, dependencies).finally(() => {
      inFlight = false
    })
  }
}
