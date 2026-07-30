import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

const reviewPath = path.join(root, 'src/features/meeting/MeetingChangeSetReviewModal.tsx')
assert.equal(fs.existsSync(reviewPath), true, 'review modal must exist')
const reviewSource = read('src/features/meeting/MeetingChangeSetReviewModal.tsx')
const newMeetingSource = read('src/features/meeting/NewMeetingModal.tsx')
const apiSource = read('src/api/meetings.ts')

assert.match(
  reviewSource,
  /const \[selectedIds, setSelectedIds\] = useState<Set<number>>\(new Set\(\)\)/,
)
assert.match(reviewSource, /checked=\{selectedIds\.has\(proposal\.id\)\}/)
assert.match(reviewSource, /proposal\.validation\.state === 'blocked'/)
assert.match(reviewSource, /proposal\.evidence/)
assert.match(reviewSource, /executeMeetingChangeSet/)
assert.match(reviewSource, /updateMeetingChangeProposal/)
assert.match(reviewSource, /确认执行/)
assert.match(reviewSource, /const requestedCount = selectedIds\.size/)
assert.match(reviewSource, /已完成 \$\{requestedCount\} 项变更/)

assert.match(newMeetingSource, /analysis_id: analysisId/)
assert.match(newMeetingSource, /MeetingChangeSetReviewModal/)
assert.doesNotMatch(newMeetingSource, /generateTaskCards|PushToTasksModal|showPushModal/)

assert.match(apiSource, /fetchMeetingChangeSet/)
assert.match(apiSource, /updateMeetingChangeProposal/)
assert.match(apiSource, /executeMeetingChangeSet/)
assert.equal(
  fs.existsSync(path.join(root, 'src/features/meeting/PushToTasksModal.tsx')),
  false,
)

console.log('meeting change-set review structure OK')
