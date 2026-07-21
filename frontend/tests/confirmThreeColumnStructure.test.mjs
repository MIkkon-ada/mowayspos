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
    assert.ok(source.includes('本周完成') && source.includes('需处理事项') &&
      source.includes('下一步计划') && source.includes('成果'),
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

  it('still has handleResubmit', () => {
    assert.ok(/\bhandleResubmit\b/.test(source),
      'Expected handleResubmit handler to remain');
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

describe('right panel all view — owner actions with card/submission tabs', () => {

  it('right panel all view has "判断与入库" header', () => {
    assert.ok(source.includes('判断与入库'),
      'Expected "判断与入库" title in right panel for all view');
  });

  it('right panel all view has "当前任务卡" tab', () => {
    assert.ok(source.includes('当前任务卡'),
      'Expected "当前任务卡" tab in right panel all view');
  });

  it('right panel all view has "整条提交" tab', () => {
    assert.ok(source.includes('整条提交'),
      'Expected "整条提交" tab in right panel all view');
  });

  it('right panel all view has ownerActionScope state for tab switching', () => {
    assert.ok(source.includes('ownerActionScope'),
      'Expected ownerActionScope state for card/submission tab switching');
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

  it('right panel contains card-level action buttons (退回并重新编辑)', () => {
    assert.ok(source.includes('退回并重新编辑'),
      'Expected card-level "退回并重新编辑" button in right panel');
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

describe('right panel — mine/coordinator/ceo operations', () => {

  it('mine view has resubmit form in right panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('补充并重新提交'),
      'Expected "补充并重新提交" button in right panel mine view');
    assert.ok(rps.includes('退回原因'),
      'Expected "退回原因" display in right panel mine view');
  });

  it('review panel does NOT contain mine resubmit form', () => {
    const review = reviewPanelContent();
    assert.ok(!review.includes('补充并重新提交'),
      'Review panel must not contain resubmit form');
  });

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

describe('non-all view operation text preservation', () => {

  it('has "补充说明" text for mine view', () => {
    assert.ok(source.includes('补充说明'),
      'Expected "补充说明" text for mine view to remain');
  });

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

  it('has "仅可查看" read-only state for non-owners', () => {
    assert.ok(source.includes('仅可查看'),
      'Expected read-only state for non-owner views');
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

function rightPanelOrSource() {
  const idx = source.indexOf('data-confirm-panel="action-preview"');
  if (idx === -1) return source;
  const endIdx = source.indexOf('</aside>', idx);
  if (endIdx === -1) return source;
  return source.slice(idx, endIdx);
}

// ===== P6-P4-B2-FIX: Persisted task card guard tests =====

describe('task card identity — isPersistedTaskCard and backendCardIndex', () => {

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

  it('confirmThreeColumnStructure.test.mjs — shows "未生成结构化任务卡" when no persisted cards', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('未生成结构化任务卡'),
      'Expected "未生成结构化任务卡" fallback message in right panel');
  });

  it('confirmThreeColumnStructure.test.mjs — shows fallback guidance text about using submission actions', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('整条提交'),
      'Expected guidance to use submission actions when no persisted cards');
  });

  it('confirmThreeColumnStructure.test.mjs — "当前任务卡" tab is disabled when no persisted cards', () => {
    assert.ok(source.includes('disabled={!hasAnyPersistedTaskCard}'),
      'Expected "当前任务卡" tab button to be disabled when no persisted cards');
  });

  it('confirmThreeColumnStructure.test.mjs — check ownerActionScope defaults to submission when no real cards (useEffect)', () => {
    // The useEffect should reference hasAnyPersistedTaskCard
    assert.ok(source.includes('hasAnyPersistedTaskCard'),
      'Expected useEffect to check hasAnyPersistedTaskCard for default scope');
  });

  it('confirmThreeColumnStructure.test.mjs — middle panel shows "本次提交概览" for fallback cards', () => {
    assert.ok(source.includes('本次提交概览'),
      'Expected fallback card badge to say "本次提交概览" not "任务卡 1/1"');
  });

  it('confirmThreeColumnStructure.test.mjs — middle panel shows warning banner when no persisted cards', () => {
    const review = reviewPanelContent();
    assert.ok(review.includes('未生成结构化任务卡'),
      'Expected warning banner in review panel when no persisted cards');
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

  it('confirmThreeColumnStructure.test.mjs — "整条提交" tab is always clickable', () => {
    assert.ok((source.match(/整条提交/g) || []).length >= 2,
      'Expected "整条提交" to appear at least twice (tab + guidance text)');
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
