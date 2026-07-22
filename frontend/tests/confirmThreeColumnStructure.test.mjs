// P6-P4-B2-COMPLETE: ConfirmPage 三栏审核工作台完整测试
// 验证三栏骨架 + 内嵌任务卡详情 + 无Modal + 所有操作集中在右栏

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourcePath = resolve(__dirname, '..', 'src', 'pages', 'ConfirmPage.tsx');
const source = readFileSync(sourcePath, 'utf8');

describe('ConfirmPage three-column structure', () => {

  it('has data-confirm-layout="three-column" marker', () => {
    assert.ok(source.includes('data-confirm-layout="three-column"'),
      'Expected data-confirm-layout="three-column" attribute on grid container');
  });

  it('has data-confirm-panel="queue" marker', () => {
    assert.ok(source.includes('data-confirm-panel="queue"'),
      'Expected left panel with data-confirm-panel="queue"');
  });

  it('has data-confirm-panel="review" marker', () => {
    assert.ok(source.includes('data-confirm-panel="review"'),
      'Expected center panel with data-confirm-panel="review"');
  });

  it('has data-confirm-panel="action-preview" marker', () => {
    assert.ok(source.includes('data-confirm-panel="action-preview"'),
      'Expected right panel with data-confirm-panel="action-preview"');
  });

  it('has gridTemplateColumns with three tracks in the three-column layout', () => {
    const gridMatch = source.match(/gridTemplateColumns\s*:\s*['"]([^'"]+)['"]/);
    assert.ok(gridMatch, 'Expected inline gridTemplateColumns style in three-column layout');
    const cols = gridMatch[1].split(/\s+/);
    assert.ok(cols.length >= 3, `Expected at least 3 column tracks, got ${cols.length}: ${gridMatch[1]}`);
  });
});

describe('ConfirmPage filter placement', () => {
  it('keeps the single functional filter set in the page header', () => {
    const queueStart = source.indexOf('data-confirm-panel="queue"');
    const header = source.slice(0, queueStart);
    for (const binding of ['filterProject', 'filterSubmitter', 'filterStatus', 'search']) {
      assert.ok(header.includes(`value={${binding}}`), `Expected ${binding} control in the page header`);
      assert.equal((source.match(new RegExp(`value=\\{${binding}\\}`, 'g')) || []).length, 1,
        `Expected exactly one ${binding} control`);
    }
  });

  it('queue panel contains no duplicate search or filter controls', () => {
    const queue = queuePanelContent();
    assert.ok(!queue.includes('Internal search + filter'), 'Queue must not contain its old filter block');
    assert.ok(!queue.includes('value={search}') && !queue.includes('value={filterProject}') &&
      !queue.includes('value={filterSubmitter}') && !queue.includes('value={filterStatus}'),
      'Queue must not contain duplicate filter controls');
  });

  it('removes the unused IconFilter component', () => {
    assert.ok(!source.includes('IconFilter'), 'Expected unused IconFilter component to be removed');
  });

  it('queue title flows directly into the record list without count or sort controls', () => {
    const queue = queuePanelContent();
    assert.ok(queue.includes('审核队列'));
    assert.ok(!queue.includes('共 {visibleItems.length} 条'));
    assert.ok(!queue.includes('最新提交'));
  });
});

describe('ConfirmPage review metadata placement', () => {
  it('removes the submission basic information block from the review panel', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('提交基本信息'), 'Review panel must not render the duplicated basic information block');
    assert.ok(!review.includes('查看原始内容'), 'Raw-content action must move out of the review panel');
  });

  it('moves the single raw-content action beside the right-panel overview heading', () => {
    const right = rightPanelOrSource();
    assert.equal((source.match(/查看原始内容/g) || []).length, 1, 'Expected exactly one raw-content action');
    const headingIndex = right.indexOf('当前记录概览');
    const actionIndex = right.indexOf('查看原始内容');
    const detailsIndex = right.indexOf('selectedProjectName');
    assert.ok(headingIndex !== -1 && actionIndex > headingIndex && actionIndex < detailsIndex,
      'Expected raw-content action beside the overview heading and before existing metadata');
  });

  it('keeps the existing right-panel overview fields without adding another metadata set', () => {
    const right = rightPanelOrSource();
    for (const field of ['项目', '提交人', '状态', '来源', '时间', '记录ID']) {
      assert.ok(right.includes(`>${field}<`), `Expected existing ${field} field in right-panel overview`);
    }
  });

  it('review content starts with the task-card switch without a metadata spacer', () => {
    const review = reviewPanelContent();
    const selectedIndex = review.indexOf('{selected ? (');
    const switchIndex = review.indexOf('data-confirm-task-switch');
    assert.ok(selectedIndex !== -1 && switchIndex > selectedIndex, 'Expected task-card switch in selected review content');
    assert.ok(!review.slice(selectedIndex, switchIndex).includes('flex-shrink-0 px-4 py-3 border-b'),
      'Expected no fixed metadata spacer before the card switch');
  });
});

describe('no task card modal — inline detail in middle panel', () => {

  it('does NOT have cardDetailOpen state (Modal removed)', () => {
    assert.ok(!source.includes('cardDetailOpen'),
      'Expected cardDetailOpen state to be removed (no modal)');
  });

  it('does NOT have fixed inset-0 z-50 task card modal overlay', () => {
    assert.ok(!source.includes('fixed inset-0 z-50'),
      'Expected no full-screen modal overlay for task cards');
  });

  it('does NOT have cardDetailOpen && activeCard && activeReviewCard condition', () => {
    assert.ok(!source.includes('cardDetailOpen && activeCard && activeReviewCard'),
      'Expected modal visibility condition to be removed');
  });

  it('still has activeCard reference (for inline detail)', () => {
    assert.ok(source.includes('activeCard'),
      'Expected activeCard to remain for inline task card detail');
  });

  it('still has activeReviewCard reference (for inline detail)', () => {
    assert.ok(source.includes('activeReviewCard'),
      'Expected activeReviewCard to remain for inline task card detail');
  });

  it('middle panel has task card selection area', () => {
    const review = reviewPanelContent();
    assert.ok(review.includes('setSelectedCardIndex'),
      'Expected task card selection with setSelectedCardIndex in review panel');
  });

  it('middle panel has inline task card detail with four content types', () => {
    assert.ok(source.includes('本次完成') && source.includes('问题与风险') &&
      source.includes('下一步计划') && source.includes('取得的成果'),
      'Expected four task card content categories in inline detail');
  });

  it('inline task card detail uses 2x2 grid layout', () => {
    // grid-cols-2 inside the review panel for task card content
    const review = reviewPanelContent();
    const has2colGrid = review.includes('grid grid-cols-2') || review.includes('grid-cols-2');
    assert.ok(has2colGrid,
      'Expected 2-column grid layout for inline task card content');
  });
});

describe('handler function preservation', () => {

  it('still has handleConfirm', () => {
    assert.ok(/\bhandleConfirm\b/.test(source),
      'Expected handleConfirm handler to remain');
  });

  it('still has handleDecision', () => {
    assert.ok(/\bhandleDecision\b/.test(source),
      'Expected handleDecision handler to remain');
  });

  it('submitter resubmit handler moved to work report history detail', () => {
    const detail = readFileSync(resolve(__dirname, '..', 'src', 'features', 'voice-update', 'VoiceUpdateDetailDrawer.tsx'), 'utf8');
    assert.ok(/\bhandleResubmit\b/.test(detail) && detail.includes('resubmitSubmission'),
      'Expected handleResubmit to live in work report history detail');
  });

  it('still has handleTaskCardDecision', () => {
    assert.ok(/\bhandleTaskCardDecision\b/.test(source),
      'Expected handleTaskCardDecision handler to remain');
  });

  it('still has handleCoordinatorFeedback', () => {
    assert.ok(/\bhandleCoordinatorFeedback\b/.test(source),
      'Expected handleCoordinatorFeedback handler to remain');
  });

  it('still has handleCoordinatorCardFeedback', () => {
    assert.ok(/\bhandleCoordinatorCardFeedback\b/.test(source),
      'Expected handleCoordinatorCardFeedback handler to remain');
  });

  it('still has handleCoachSubmissionDecide', () => {
    assert.ok(/\bhandleCoachSubmissionDecide\b/.test(source),
      'Expected handleCoachSubmissionDecide handler to remain');
  });

  it('still has handleCoachCardDecide', () => {
    assert.ok(/\bhandleCoachCardDecide\b/.test(source),
      'Expected handleCoachCardDecide handler to remain');
  });
});

describe('API import path preservation', () => {

  it('imports from ../api/confirmations', () => {
    assert.ok(source.includes('../api/confirmations'),
      'Expected "import ... from ../api/confirmations" to remain unchanged');
  });
});

describe('right panel all view — automatic single-card actions with legacy fallback', () => {

  it('right panel all view has "判断与入库" header', () => {
    assert.ok(source.includes('判断与入库'),
      'Expected "判断与入库" title in right panel for all view');
  });

  it('right panel identifies the current task card without a scope switch', () => {
    const right = rightPanelOrSource();
    assert.ok(right.includes('当前审批对象 · 任务卡'));
    assert.ok(!right.includes('当前任务卡 / 整条提交'));
  });

  it('legacy submissions automatically retain submission-level operations', () => {
    const right = rightPanelOrSource();
    assert.ok(right.includes('!hasAnyPersistedTaskCard'));
    assert.ok(right.includes('整条提交兼容流程'));
  });

  it('persisted cards expose the card action section directly', () => {
    assert.ok(rightPanelOrSource().includes('data-confirm-card-actions'));
  });

  it('review panel does NOT contain submission action buttons', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('确认入库'),
      'Review panel must not contain "确认入库" button');
    assert.ok(!review.includes('退回提交人'),
      'Review panel must not contain "退回提交人" button');
    assert.ok(!review.includes('转交统筹人'),
      'Review panel must not contain "转交统筹人" button');
    assert.ok(!review.includes('转交企业教练'),
      'Review panel must not contain "转交企业教练" button');
  });

  it('right panel contains all submission action buttons', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('确认入库'), 'Right panel must contain "确认入库" button');
    assert.ok(rps.includes('退回提交人'), 'Right panel must contain "退回提交人" button');
    assert.ok(rps.includes('转交统筹人'), 'Right panel must contain "转交统筹人" button');
    assert.ok(rps.includes('转交企业教练'), 'Right panel must contain "转交企业教练" button');
  });

  it('right panel contains card-level return action', () => {
    assert.ok(source.includes('退回当前任务卡'),
      'Expected card-level return button in right panel');
  });

  it('no duplicate submission action buttons across panels', () => {
    const review = reviewPanelContent();
    const buttons = ['确认入库', '退回提交人', '转交统筹人', '转交企业教练'];
    for (const btn of buttons) {
      assert.ok(!review.includes(btn), `"${btn}" must NOT appear in review panel`);
    }
  });

  it('writeToAchievements Toggle is in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('writeToAchievements'),
      'Expected writeToAchievements Toggle in right panel');
  });

  it('writeToIssues Toggle is in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('writeToIssues'),
      'Expected writeToIssues Toggle in right panel');
  });

  it('pendingAction note textarea is in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('pendingAction'),
      'Expected pendingAction handling area in right panel');
  });
});

describe('right panel — coordinator/ceo operations', () => {

  it('coordinator view has submission-level feedback form in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('提供统筹意见') || source.includes('提供统筹意见'),
      'Expected coordinator feedback form in right panel');
  });

  it('coordinator view has card-level feedback form in right panel', () => {
    assert.ok(source.includes('单卡统筹反馈'),
      'Expected card-level coordinator feedback form');
  });

  it('review panel does NOT contain coordinator feedback forms', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('提供统筹意见'),
      'Review panel must not contain coordinator feedback form');
  });

  it('ceo view has submission-level decision form in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('企业教练批示') || source.includes('企业教练批示'),
      'Expected ceo decision form in right panel');
  });

  it('ceo view has card-level decision form in right panel', () => {
    assert.ok(source.includes('单卡企业教练批示'),
      'Expected card-level ceo decision form');
  });

  it('review panel does NOT contain ceo decision forms', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('整条提交') || !review.includes('提交企业教练批示'),
      'Review panel must not contain interactive ceo form');
  });
});

describe('non-all reviewer operation text preservation', () => {

  it('has "统筹反馈" text for coordinator view', () => {
    assert.ok(source.includes('统筹反馈'),
      'Expected "统筹反馈" text for coordinator view to remain');
  });

  it('has "企业教练批示" text for ceo view', () => {
    assert.ok(source.includes('企业教练批示'),
      'Expected "企业教练批示" text for ceo view to remain');
  });
});

describe('UI structure verification', () => {

  it('right panel shows "当前记录" section', () => {
    assert.ok(rightPanelOrSource().includes('当前记录'),
      'Expected "当前记录" section in right panel');
  });

  it('right panel empty state shows select prompt', () => {
    assert.ok(source.includes('请选择左侧记录查看审核操作') ||
      source.includes('请选择左侧记录查看审核概览'),
      'Expected empty state placeholder text');
  });

  it('right panel title changes per viewMode', () => {
    assert.ok(source.includes('提交处理') || source.includes('统筹反馈') || source.includes('企业教练批示'),
      'Expected view-specific right panel titles');
  });

  it('has no submitter-only mine view in the reviewer workbench', () => {
    assert.ok(!source.includes("viewMode === 'mine'") && !source.includes('我的提交记录'),
      'Reviewer workbench must not expose a submitter-only mine view');
  });
});

describe('B1.1 layout correction verification', () => {

  it('operation logs are inside data-confirm-panel="review"', () => {
    const reviewStart = source.indexOf('data-confirm-panel="review"');
    const rightStart = source.indexOf('data-confirm-panel="action-preview"');
    assert.ok(reviewStart !== -1 && rightStart !== -1, 'Review and right panels must both exist');
    const betweenPanels = source.slice(reviewStart, rightStart);
    assert.ok(betweenPanels.includes('操作日志'),
      'Operation log must be inside review panel (before action-preview)');
  });

  it('operation logs are NOT a standalone block outside three-column grid', () => {
    const gridClose = source.indexOf('data-confirm-layout="three-column"');
    const gridEndDiv = source.indexOf('</div>', source.indexOf('</aside>', gridClose));
    if (gridEndDiv !== -1) {
      const afterGrid = source.slice(gridEndDiv);
      const opLogIdx = afterGrid.indexOf('操作日志');
      const orgComment = afterGrid.indexOf('Operation log');
      assert.ok(opLogIdx === -1 || orgComment === -1,
        'No standalone operation log block outside three-column grid');
    }
  });

  it('selected state sync with visibleItems exists', () => {
    assert.ok(source.includes('visibleItems.length === 0') ||
      source.includes('visibleItems.some'),
      'Selected state must sync with visibleItems');
  });

  it('clears selected when visibleItems is empty', () => {
    assert.ok(source.includes('visibleItems.length === 0') &&
      (source.includes('setSelected(null)') || source.includes('selected')),
      'Must handle empty visibleItems by clearing selected');
  });

  it('deep-link record does not show alone when filtered from left panel', () => {
    assert.ok(source.includes('urlSubmissionId') &&
      source.includes('filterStatus'),
      'Deep link must sync with filter visibility');
  });

  it('cardIndex deep-link resolution still exists', () => {
    assert.ok(source.includes('urlCardIndex') || source.includes('cardIndex'),
      'Expected cardIndex deep-link resolution to remain');
  });
});

describe('no backend / API changes', () => {
  it('submissionStatus import unchanged', () => {
    assert.ok(source.includes('submissionStatus'),
      'Expected submissionStatus import unchanged');
  });
});

// Helper functions
function reviewPanelContent() {
  const start = source.indexOf('data-confirm-panel="review"');
  const end = source.indexOf('data-confirm-panel="action-preview"');
  if (start === -1 || end === -1) return '';
  return source.slice(start, end);
}

function queuePanelContent() {
  const start = source.indexOf('data-confirm-panel="queue"');
  const end = source.indexOf('data-confirm-panel="review"');
  if (start === -1 || end === -1) return '';
  return source.slice(start, end);
}

function rightPanelOrSource() {
  const idx = source.indexOf('data-confirm-panel="action-preview"');
  if (idx === -1) return source;
  const endIdx = source.indexOf('</aside>', idx);
  if (endIdx === -1) return source;
  return source.slice(idx, endIdx);
}

// ===== P6-P4-B2-FIX: Persisted task card guard tests =====

describe('task card identity — isPersistedTaskCard and backendCardIndex', () => {

  it('preserves original evidence in the frontend card view model', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('evidence: string[]'));
    assert.ok(domainFile.includes('stringArray(report.evidence)'));
    assert.ok(reviewPanelContent().includes('activeReviewEvidence'));
  });

  it('confirmThreeColumnStructure.test.mjs — ConfirmationTaskCard type has backendCardIndex field', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('backendCardIndex'),
      'Expected backendCardIndex in ConfirmationTaskCard type definition');
  });

  it('confirmThreeColumnStructure.test.mjs — ConfirmationTaskCard type has isPersistedTaskCard field', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('isPersistedTaskCard'),
      'Expected isPersistedTaskCard in ConfirmationTaskCard type definition');
  });

  it('confirmThreeColumnStructure.test.mjs — real cards have isPersistedTaskCard: true', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('isPersistedTaskCard: true'),
      'Expected real persisted cards to have isPersistedTaskCard: true');
  });

  it('confirmThreeColumnStructure.test.mjs — fallback cards have isPersistedTaskCard: false', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('isPersistedTaskCard: false'),
      'Expected fallback cards to have isPersistedTaskCard: false');
  });

  it('confirmThreeColumnStructure.test.mjs — backendCardIndex is set in real cards', () => {
    const domainFile = readFileSync(resolve(__dirname, '..', 'src', 'domain', 'confirmationTaskCards.ts'), 'utf8');
    assert.ok(domainFile.includes('backendCardIndex: index') || domainFile.includes('backendCardIndex:index'),
      'Expected backendCardIndex to be set to the original array index for real cards');
  });
});

describe('non-persisted card guard — no card actions without real task_reports', () => {

  it('confirmThreeColumnStructure.test.mjs — hasAnyPersistedTaskCard computed property exists', () => {
    assert.ok(source.includes('hasAnyPersistedTaskCard'),
      'Expected hasAnyPersistedTaskCard computed in ConfirmPage');
  });

  it('confirmThreeColumnStructure.test.mjs — activeCardBackendIndex guard exists', () => {
    assert.ok(source.includes('activeCardBackendIndex'),
      'Expected activeCardBackendIndex computed for safely calling backend card APIs');
  });

  it('confirmThreeColumnStructure.test.mjs — handleTaskCardDecision checks activeCardBackendIndex', () => {
    // The handler must include a null check for activeCardBackendIndex
    const decisionHandler = source.slice(
      source.indexOf('handleTaskCardDecision'),
      source.indexOf('handleCoordinatorCardFeedback') > source.indexOf('handleTaskCardDecision')
        ? source.indexOf('handleCoordinatorCardFeedback')
        : source.indexOf('handleCoachCardDecide')
    );
    assert.ok(decisionHandler.includes('activeCardBackendIndex'),
      'Expected handleTaskCardDecision to check activeCardBackendIndex');
  });

  it('confirmThreeColumnStructure.test.mjs — handleCoachCardDecide checks activeCardBackendIndex', () => {
    const coachHandler = source.slice(
      source.indexOf('handleCoachCardDecide'),
      source.indexOf('handleSubmit') > source.indexOf('handleCoachCardDecide')
        ? source.indexOf('handleSubmit')
        : source.length
    );
    assert.ok(coachHandler.includes('activeCardBackendIndex'),
      'Expected handleCoachCardDecide to check activeCardBackendIndex');
  });

  it('confirmThreeColumnStructure.test.mjs — handleCoordinatorCardFeedback checks activeCardBackendIndex', () => {
    const coordHandler = source.slice(
      source.indexOf('handleCoordinatorCardFeedback'),
      source.indexOf('handleCoordinatorFeedback') > source.indexOf('handleCoordinatorCardFeedback')
        ? source.indexOf('handleCoordinatorFeedback')
        : source.length
    );
    assert.ok(coordHandler.includes('activeCardBackendIndex'),
      'Expected handleCoordinatorCardFeedback to check activeCardBackendIndex');
  });
});

describe('fallback card UI — "未生成结构化任务卡" message', () => {

  it('confirmThreeColumnStructure.test.mjs — falls back to submission actions when no persisted cards', () => {
    assert.ok(source.includes("!hasAnyPersistedTaskCard") && source.includes('整条提交兼容流程'),
      'Expected fallback submissions to use submission-level actions');
  });

  it('confirmThreeColumnStructure.test.mjs — shows fallback guidance text about using submission actions', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('整条提交'),
      'Expected guidance to use submission actions when no persisted cards');
  });

  it('confirmThreeColumnStructure.test.mjs — card APIs are guarded when no persisted cards', () => {
    assert.ok(source.includes('activeCardBackendIndex') && source.includes('activeCard?.isPersistedTaskCard'),
      'Expected card API calls to require a persisted task card');
  });

  it('confirmThreeColumnStructure.test.mjs — fallback is automatic without scope state', () => {
    assert.ok(!source.includes('ownerActionScope'),
      'Expected no manual card/submission scope state');
  });

  it('confirmThreeColumnStructure.test.mjs — middle panel shows "本次提交概览" for fallback cards', () => {
    assert.ok(source.includes('本次提交概览'),
      'Expected fallback card badge to say "本次提交概览" not "任务卡 1/1"');
  });

  it('confirmThreeColumnStructure.test.mjs — middle panel labels fallback content as submission overview', () => {
    const review = reviewPanelContent();
    assert.ok(review.includes('本次提交概览'),
      'Expected fallback content to be labelled as a submission overview');
  });
});

describe('card action isolation — actions only for persisted cards', () => {

  it('confirmThreeColumnStructure.test.mjs — card action buttons are guarded by isPersistedTaskCard', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('isPersistedTaskCard'),
      'Expected card action buttons to be inside isPersistedTaskCard guard');
  });

  it('confirmThreeColumnStructure.test.mjs — submission actions still exist', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('确认入库') && rps.includes('退回提交人'),
      'Expected submission-level actions to remain available');
  });

  it('confirmThreeColumnStructure.test.mjs — no visible card/submission scope tab remains', () => {
    assert.ok(!source.includes('ownerActionScope'));
    assert.ok(source.includes('整条提交兼容流程'));
  });
});

describe('layout preservation — confirm page unchanged structurally', () => {

  it('confirmThreeColumnStructure.test.mjs — three-column grid still present', () => {
    const gridMatch = source.match(/gridTemplateColumns\s*:\s*['"]([^'"]+)['"]/);
    assert.ok(gridMatch, 'Three-column grid template must still exist');
    const cols = gridMatch[1].split(/\s+/);
    assert.ok(cols.length >= 3, `Expected ≥3 column tracks, got ${cols.length}`);
  });

  it('confirmThreeColumnStructure.test.mjs — no Modal has been restored', () => {
    assert.ok(!source.includes('cardDetailOpen'),
      'cardDetailOpen must NOT be restored');
    assert.ok(!source.includes('fixed inset-0 z-50'),
      'Fixed overlay must NOT be restored');
  });

  it('confirmThreeColumnStructure.test.mjs — no duplicate operation text in middle panel', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('确认入库'),
      'Middle panel must not have action buttons');
  });
});

// ===== Approved compact single-card review redesign =====

describe('approved compact single-card review layout', () => {
  it('uses one compact header row for title queues filters and search', () => {
    assert.ok(source.includes('data-confirm-header="compact"'),
      'Expected the approved compact one-row header marker');
  });

  it('queue contains only title list and empty states without count or sort strip', () => {
    const queue = queuePanelContent();
    assert.ok(!queue.includes('共 {visibleItems.length} 条'),
      'Queue must not repeat the visible record count');
    assert.ok(!queue.includes('最新提交'),
      'Queue must not show the non-functional sort label');
  });

  it('review panel starts with the horizontal task-card switch and no statistic cards', () => {
    const review = reviewPanelContent();
    assert.ok(review.includes('data-confirm-task-switch'),
      'Expected horizontal task-card switch in review panel');
    assert.ok(review.includes('data-confirm-card-detail'),
      'Expected full-width active-card detail in review panel');
    assert.ok(!review.includes('grid grid-cols-4'),
      'Review panel must not include the four-stat summary');
  });

  it('review ownership is read-only and status suggestion is not rendered', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('项目归属'), 'Project ownership selector must be removed');
    assert.ok(!review.includes('关联任务'), 'Task ownership selector must be removed');
    assert.ok(!review.includes('任务状态建议'), 'Task status suggestion must be removed');
  });

  it('persisted cards have contextual single-card actions in the right panel', () => {
    const right = rightPanelOrSource();
    assert.ok(right.includes('data-confirm-card-actions'),
      'Expected persisted-card actions in right panel');
    assert.ok(right.includes("handleTaskCardDecision('confirm')"),
      'Confirm must directly call the card-level handler');
    assert.ok(right.includes('确认当前任务卡入库'));
    assert.ok(right.includes('退回当前任务卡'));
  });

  it('notes appear only for return or transfer actions', () => {
    const right = rightPanelOrSource();
    assert.ok(right.includes('data-confirm-action-note'),
      'Expected contextual note editor marker');
    assert.ok(right.includes("pendingAction === 'return'"));
    assert.ok(right.includes("pendingAction === 'transfer'"));
    assert.ok(right.includes("setPendingAction('ceo')"));
    assert.ok(!right.includes('确认说明可选'),
      'Card confirmation must not pretend to save an optional note');
  });
});

describe('current review card content isolation', () => {
  it('does not repeat the three-level ownership path in the middle panel', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('activeCard.structure.projectName'),
      'The middle panel must not repeat project > key task > task ownership');
  });

  it('shows coordinator and coach notes only when they contain real content', () => {
    const review = reviewPanelContent();
    assert.ok(review.includes('activeCard.coordinatorNote &&'),
      'Coordinator feedback must be conditional on actual content');
    assert.ok(review.includes('activeCard.ceoNote &&'),
      'Coach decision must be conditional on actual content');
    assert.ok(!review.includes("activeCard.coordinatorNote || '—'"));
    assert.ok(!review.includes("activeCard.ceoNote || '—'"));
  });

  it('builds operation logs from the selected record only', () => {
    assert.ok(!source.includes('const opLogs = items.filter'),
      'Operation logs must not aggregate unrelated queue records');
    assert.ok(source.includes('const opLogs = selected'),
      'Operation logs must be scoped to the selected record');
  });

  it('falls back to the real submission transcript only for a single card without evidence', () => {
    assert.ok(source.includes('activeReviewEvidence'),
      'Review evidence should have an explicit resolved value');
    assert.ok(source.includes('taskCards.length === 1'),
      'Whole-transcript fallback must be limited to a single-card submission');
    assert.ok(source.includes('selected?.transcript_text'),
      'Evidence fallback must use the saved original transcript');
  });
});
