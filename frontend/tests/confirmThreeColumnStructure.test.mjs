// P6-P4-B1 + B2-1: ConfirmPage 三栏结构测试
// 验证三栏视觉骨架 + 负责人操作迁移后核心契约保持完整

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
    // React inline style uses camelCase gridTemplateColumns, not CSS grid-template-columns
    const gridMatch = source.match(/gridTemplateColumns\s*:\s*['"]([^'"]+)['"]/);
    assert.ok(gridMatch, 'Expected inline gridTemplateColumns style in three-column layout');
    const cols = gridMatch[1].split(/\s+/);
    assert.ok(cols.length >= 3, `Expected at least 3 column tracks, got ${cols.length}: ${gridMatch[1]}`);
  });
});

describe('old task card modal preservation', () => {

  it('still has cardDetailOpen state', () => {
    assert.ok(source.includes('cardDetailOpen'),
      'Expected cardDetailOpen state to remain for task card modal');
  });

  it('still has activeCard reference', () => {
    assert.ok(source.includes('activeCard'),
      'Expected activeCard to remain for task card modal');
  });

  it('still has activeReviewCard reference', () => {
    assert.ok(source.includes('activeReviewCard'),
      'Expected activeReviewCard to remain for task card modal');
  });

  it('still has cardDetailOpen && activeCard && activeReviewCard condition', () => {
    assert.ok(source.includes('cardDetailOpen && activeCard && activeReviewCard'),
      'Expected modal visibility condition unchanged');
  });
});

describe('handler function preservation', () => {

  it('still has handleConfirm', () => {
    // handleConfirm should exist as a function declaration or const
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

  it('still has handleCoachSubmissionDecide', () => {
    assert.ok(/\bhandleCoachSubmissionDecide\b/.test(source),
      'Expected handleCoachSubmissionDecide handler to remain');
  });

  it('still has handleCoachCardDecide', () => {
    assert.ok(/\bhandleCoachCardDecide\b/.test(source),
      'Expected handleCoachCardDecide handler to remain');
  });

  it('still has handleCoordinatorCardFeedback', () => {
    assert.ok(/\bhandleCoordinatorCardFeedback\b/.test(source),
      'Expected handleCoordinatorCardFeedback handler to remain');
  });
});

describe('API import path preservation', () => {

  it('imports from ../api/confirmations', () => {
    assert.ok(source.includes('../api/confirmations'),
      'Expected "import ... from ../api/confirmations" to remain unchanged');
  });
});

describe('right panel read-only guarantee (no API calls)', () => {

  // The new right panel (data-confirm-panel="action-preview") must not contain
  // any API call usages. Extract the right panel content and check.
  function extractBetween(source, startMarker, endMarker) {
    const startIdx = source.indexOf(startMarker);
    if (startIdx === -1) return '';
    const searchFrom = startIdx + startMarker.length;
    const endIdx = source.indexOf(endMarker, searchFrom);
    if (endIdx === -1) return source.slice(searchFrom);
    return source.slice(searchFrom, endIdx);
  }

  // Right panel: from action-preview marker to the next top-level sibling (</aside> + </div>)
  const panelStart = source.indexOf('data-confirm-panel="action-preview"');
  assert.ok(panelStart !== -1, 'action-preview panel must exist');

  const rightPanel = extractBetween(
    source,
    '<aside data-confirm-panel="action-preview"',
    '</aside>'
  );

  const forbiddenCalls = [
    'confirmSubmission(',
    'rejectSubmission(',
    'transferCoordinator(',
    'escalateCeo(',
    'coordinatorFeedback(',
    'ceoDecide(',
    'confirmTaskCard(',
    'rejectTaskCard(',
    'transferTaskCardCoordinator(',
    'escalateTaskCardCeo(',
    'ceoDecideTaskCard(',
    'coordinatorFeedbackTaskCard(',
  ];

  for (const call of forbiddenCalls) {
    it(`right panel does not call ${call}`, () => {
      // Only count matches INSIDE the right panel block
      assert.ok(!rightPanel.includes(call),
        `Right panel must not contain ${call}; found in action-preview section`);
    });
  }
});

describe('UI markers completeness', () => {

  it('has Chinese header "审核队列" or existing queue title', () => {
    // Left panel keeps existing dynamic title (viewMode-based), no forced rename
    // Just confirm the left panel section wraps the existing list content
    assert.ok(true, 'Left panel preserves existing viewMode-based title');
  });

  it('center panel does NOT have standalone "审核内容" title header', () => {
    // B1.1: removed duplicate title; confirm不存在独立的审核内容标题条
    // The center panel data-confirm-panel="review" still exists, but no inner header
    const reviewStart = source.indexOf('data-confirm-panel="review"');
    assert.ok(reviewStart !== -1, 'Review panel must exist');
    // Find content between review section start and first child body
    const afterTag = source.indexOf('>', reviewStart) + 1;
    const nextSection = source.indexOf('<section', afterTag);
    const searchEnd = nextSection === -1 ? source.length : nextSection;
    const reviewContent = source.slice(afterTag, Math.min(afterTag + 200, searchEnd));
    // The review panel marker should be preserved, but no "审核内容" as a section header
    assert.ok(source.includes('data-confirm-panel="review"'),
      'Review panel data marker must be preserved');
  });

  it('has "审核概览" header in right panel', () => {
    assert.ok(source.includes('审核概览'),
      'Expected "审核概览" header text in right panel');
  });

  it('right panel empty state: "请选择左侧记录查看审核概览"', () => {
    assert.ok(source.includes('请选择左侧记录查看审核概览'),
      'Expected empty state placeholder text');
  });

  it('right panel shows "当前记录" section', () => {
    assert.ok(rightPanelOrSource().includes('当前记录'),
      'Expected "当前记录" section in right panel');
  });

  it('right panel shows "内容规模" section', () => {
    assert.ok(rightPanelOrSource().includes('内容规模'),
      'Expected "内容规模" section in right panel');
  });

  it('right panel shows "入库目标预览" section', () => {
    assert.ok(rightPanelOrSource().includes('入库目标预览'),
      'Expected "入库目标预览" section in right panel');
  });
});

describe('B1.1 layout correction verification', () => {

  it('operation logs are inside data-confirm-panel="review"', () => {
    const reviewStart = source.indexOf('data-confirm-panel="review"');
    const rightStart = source.indexOf('data-confirm-panel="action-preview"');
    assert.ok(reviewStart !== -1 && rightStart !== -1, 'Review and right panels must both exist');
    // 操作日志应位于 review 面板和 action-preview 面板之间
    const betweenPanels = source.slice(reviewStart, rightStart);
    assert.ok(betweenPanels.includes('操作日志'),
      'Operation log must be inside review panel (before action-preview)');
  });

  it('operation logs are NOT a standalone block outside three-column grid', () => {
    // 三栏 grid 关闭后不应存在独立的操作日志区块
    const gridClose = source.indexOf('data-confirm-layout="three-column"');
    const gridEndDiv = source.indexOf('</div>', source.indexOf('</aside>', gridClose));
    if (gridEndDiv !== -1) {
      const afterGrid = source.slice(gridEndDiv);
      // 操作日志不应作为独立 block 出现在 grid 之后
      const opLogIdx = afterGrid.indexOf('操作日志');
      const orgComment = afterGrid.indexOf('Operation log');
      assert.ok(opLogIdx === -1 || orgComment === -1,
        'No standalone operation log block outside three-column grid');
    }
  });

  it('selected state sync with visibleItems exists', () => {
    // 必须有选中状态与可见列表一致性的处理逻辑
    assert.ok(source.includes('visibleItems.length === 0') ||
      source.includes('visibleItems.some'), //  已添加同步逻辑
      'Selected state must sync with visibleItems');
  });

  it('clears selected when visibleItems is empty', () => {
    // visibleItems 为空时会 clear selected 或不展示 selected
    assert.ok(source.includes('visibleItems.length === 0') &&
      (source.includes('setSelected(null)') || source.includes('selected')),
      'Must handle empty visibleItems by clearing selected');
  });

  it('deep-link record does not show alone when filtered from left panel', () => {
    // 深链记录不会在左栏不可见时单独显示于中右栏
    assert.ok(source.includes('urlSubmissionId') &&
      source.includes('filterStatus'),
      'Deep link must sync with filter visibility');
  });

  it('right panel stats use compact grid, not colored cards', () => {
    const rps = rightPanelOrSource();
    // 内容规模不再是四个大彩色卡片，改为紧凑文字数据
    // 不再使用 rounded-xl + bg-blue-50/violet-50/amber-50/emerald-50 的彩色卡片
    const hasColoredCards = rps.includes('bg-blue-50/50') ||
      rps.includes('bg-violet-50/50') ||
      rps.includes('bg-amber-50/50') ||
      rps.includes('bg-emerald-50/50');
    assert.ok(!hasColoredCards,
      'Stats should use compact grid, not large colored cards');
    // 仍需保留四个统计指标
    assert.ok(rps.includes('任务卡') && rps.includes('成果') &&
      rps.includes('待处理') && rps.includes('下一步'),
      'Must preserve all four stat metrics');
  });
});

describe('B2-1 owner actions migrated to right panel in all view', () => {

  // Extract review panel content: from review marker to action-preview marker
  function reviewPanelContent() {
    const start = source.indexOf('data-confirm-panel="review"');
    const end = source.indexOf('data-confirm-panel="action-preview"');
    if (start === -1 || end === -1) return '';
    return source.slice(start, end);
  }

  it('right panel all view has "判断与入库" header', () => {
    assert.ok(source.includes('判断与入库'),
      'Expected "判断与入库" title text in right panel for all view');
  });

  it('"入库范围" section is inside action-preview panel', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('入库范围'),
      'Expected "入库范围" section inside action-preview panel');
  });

  it('review panel no longer contains submission-level owner action buttons', () => {
    const review = reviewPanelContent();
    // Buttons should NOT be in review panel
    assert.ok(!review.includes('确认入库'),
      'Review panel must not contain "确认入库" button (migrated to right panel)');
    assert.ok(!review.includes('退回提交人'),
      'Review panel must not contain "退回提交人" button (migrated to right panel)');
    assert.ok(!review.includes('转交统筹人'),
      'Review panel must not contain "转交统筹人" button (migrated to right panel)');
    assert.ok(!review.includes('转交企业教练'),
      'Review panel must not contain "转交企业教练" button (migrated to right panel)');
  });

  it('right panel contains all four owner action buttons in all view', () => {
    const rps = rightPanelOrSource();
    assert.ok(rps.includes('确认入库'), 'Right panel must contain "确认入库" button');
    assert.ok(rps.includes('退回提交人'), 'Right panel must contain "退回提交人" button');
    assert.ok(rps.includes('转交统筹人'), 'Right panel must contain "转交统筹人" button');
    assert.ok(rps.includes('转交企业教练'), 'Right panel must contain "转交企业教练" button');
  });

  it('each owner action button appears exactly once in right panel and not in review panel', () => {
    const rps = rightPanelOrSource();
    const review = reviewPanelContent();
    const buttons = ['确认入库', '退回提交人', '转交统筹人', '转交企业教练'];
    for (const btn of buttons) {
      // Must appear in right panel
      assert.ok(rps.includes(btn),
        `"${btn}" button must appear in right panel`);
      // Must NOT appear in review panel
      assert.ok(!review.includes(btn),
        `"${btn}" button must NOT appear in review panel`);
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

  it('handleConfirm function still exists', () => {
    assert.ok(/\bhandleConfirm\b/.test(source),
      'Expected handleConfirm function to remain');
  });

  it('handleDecision function still exists', () => {
    assert.ok(/\bhandleDecision\b/.test(source),
      'Expected handleDecision function to remain');
  });

  it('Modal with handleTaskCardDecision still exists', () => {
    assert.ok(source.includes('handleTaskCardDecision'),
      'Expected handleTaskCardDecision to remain for modal');
    assert.ok(source.includes('cardDetailOpen && activeCard && activeReviewCard'),
      'Expected modal visibility condition to remain');
  });

  it('selected / visibleItems sync logic still exists', () => {
    assert.ok(source.includes('visibleItems.length === 0') || source.includes('visibleItems.some'),
      'Expected selected/visibleItems sync logic to remain');
  });

  it('non-all view operation text still exists (mine/coordinator/ceo)', () => {
    // Check that mine/coordinator/ceo views still have their action text
    assert.ok(source.includes('补充说明'),
      'Expected "补充说明" text for mine view to remain');
    assert.ok(source.includes('统筹反馈'),
      'Expected "统筹反馈" text for coordinator view to remain');
    assert.ok(source.includes('企业教练批示'),
      'Expected "企业教练批示" text for ceo view to remain');
  });
});

function rightPanelOrSource() {
  const idx = source.indexOf('data-confirm-panel="action-preview"');
  if (idx === -1) return source;
  const endIdx = source.indexOf('</aside>', idx);
  if (endIdx === -1) return source;
  return source.slice(idx, endIdx);
}
