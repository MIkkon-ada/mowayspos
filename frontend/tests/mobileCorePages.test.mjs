import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8')

test('four core pages isolate mobile content below the 800px breakpoint', async () => {
  const pages = await Promise.all([
    read('src/pages/TaskManagementPage.tsx'),
    read('src/pages/ConfirmPage.tsx'),
    read('src/pages/MeetingPage.tsx'),
    read('src/pages/IssuesPage.tsx'),
  ])
  for (const source of pages) {
    assert.match(source, /min-\[800px\]:hidden/)
    assert.match(source, /hidden min-\[800px\]:block|hidden min-\[800px\]:flex/)
  }
})

test('mobile detail workspaces reserve bottom navigation space', async () => {
  const files = await Promise.all([
    read('src/pages/IssueDetailPage.tsx'),
    read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx'),
    read('src/features/meeting/MeetingDetailWorkspace.tsx'),
  ])
  for (const source of files) assert.match(source, /pb-24/)
})

test('core pages delegate mobile cards to existing detail routes and callbacks', async () => {
  const [task, confirm, meeting, issues, taskCards, confirmCards, timeline, issueCards] = await Promise.all([
    read('src/pages/TaskManagementPage.tsx'),
    read('src/pages/ConfirmPage.tsx'),
    read('src/pages/MeetingPage.tsx'),
    read('src/pages/IssuesPage.tsx'),
    read('src/features/mobile-core-pages/MobileTaskList.tsx'),
    read('src/features/mobile-core-pages/MobileConfirmationStream.tsx'),
    read('src/features/mobile-core-pages/MobileMeetingTimeline.tsx'),
    read('src/features/mobile-core-pages/MobileIssueList.tsx'),
  ])
  assert.match(task, /<MobileTaskList/)
  assert.match(task, /onOpenSubTask=\{openSubDetail\}/)
  assert.match(confirm, /<MobileConfirmationStream/)
  assert.match(confirm, /handleTaskCardDecision/)
  assert.match(meeting, /<MobileMeetingTimeline/)
  assert.match(meeting, /\/work\/meetings\/detail\/\$\{meeting\.id\}/)
  assert.match(issues, /<MobileIssueList/)
  assert.match(issues, /\/work\/issues\/\$\{item\.id\}/)
  for (const source of [taskCards, confirmCards, timeline, issueCards]) assert.match(source, /pb-24/)
})

test('mobile confirmation does not create a task card without a selected submission', async () => {
  const source = await read('src/pages/ConfirmPage.tsx')
  assert.match(source, /cards=\{selected \? \(taskCards as unknown as Record<string, unknown>\[\]\) : \[\]\}/)
})
