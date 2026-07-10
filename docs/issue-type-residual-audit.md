# issue_type 裸字符串残留审计

审计范围：`bowei_ai_dashboard/app/**/*.py`、`bowei_ai_dashboard/tests/**/*.py`

审计时间：2026-07-10

## 审计背景

上一轮提交：

- `0bec4b0 feat: normalize backend issue types`

本轮只做残留审计，不改业务代码，不做历史迁移，不重构 `issue_flow.py`。

## 0bec4b0 实际变更文件核对

`git show --name-only --oneline 0bec4b0` 的结果如下：

- `bowei_ai_dashboard/app/domain/issue_type.py`
- `bowei_ai_dashboard/app/routers/confirmations.py`
- `bowei_ai_dashboard/app/routers/dashboard.py`
- `bowei_ai_dashboard/app/routers/issues.py`
- `bowei_ai_dashboard/app/services/extractor.py`
- `bowei_ai_dashboard/tests/test_issue_type.py`
- `docs/issue-type-normalize-audit.md`

结论：

- `workflow.py` 不在 `0bec4b0` 的实际变更文件里。
- 本轮重新审计后，`workflow.py` 也没有发现 `issue_type` 相关命中。

## 残留命中清单

| 文件 | 行/位置 | 命中内容 | 类型 | 是否需要修复 | 风险等级 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- | --- |
| `bowei_ai_dashboard/app/excel_importer.py` | 371, 386 | `issue_type="问题"` / `issue_type="决策事项"` | 写入点 | 建议后续小步修 | P2 | 如后续统一写入语义，可在导入入口接 helper，再由 helper 输出稳定 key 或显式兼容映射 |
| `bowei_ai_dashboard/app/services/extractor.py` | 399-423 | `_issue_type()` 返回 `"决策" / "风险" / "待协调" / "问题"`，`_classify_issue_text()` 返回中文 `issue_type` | 后端判断 / 旧兼容 | 建议后续小步修 | P2 | 若后续希望提取层也统一稳定 key，可逐步让 extractor 输出标准 key，再由展示层做 label 映射 |
| `bowei_ai_dashboard/app/services/extractor.py` | 530 | ` _si.get("issue_type") or "问题"` | 写入点 / 旧兼容 | 建议后续小步修 | P2 | 保留兼容默认值即可；后续可改成 helper 默认值或统一 normalize 后再写入 |
| `bowei_ai_dashboard/app/services/extractor.py` | 647, 748, 852 | `IF.normalize_type(...)` | 旧兼容 | 暂不需要立刻修 | P2 | 这是旧 `issue_flow.py` 兼容层，当前仍能工作；若以后整体收口，可单独做小任务 |
| `bowei_ai_dashboard/app/domain/issue_flow.py` | 全文件 | `TYPE_ISSUE / TYPE_RISK / TYPE_COORDINATE / TYPE_DECISION`、`normalize_type()`、`default_status_for_type()` | 旧兼容 | 否 | 兼容层 | 保持不动，本轮不重构 |
| `bowei_ai_dashboard/app/routers/issues.py` | 全文件 | 未发现 `issue_type == "决策"` 之类裸比较；已使用 `IT.normalize / IT.is_decision / _issue_type_matches_filter` | 后端判断 | 否 | 无需处理 | 保持现状 |
| `bowei_ai_dashboard/app/routers/confirmations.py` | 全文件 | 未发现直接比较 `issue_type` 中文值的业务判断；已使用 `IT.normalize / IT.is_decision` | 后端判断 | 否 | 无需处理 | 保持现状 |
| `bowei_ai_dashboard/app/routers/dashboard.py` | 全文件 | 未发现裸字符串 issue_type 判断；看板统计已改用 `IT.is_decision()` | 后端判断 | 否 | 无需处理 | 保持现状 |
| `bowei_ai_dashboard/tests/test_issue_type.py` | 全文件 | 中文/英文别名输入测试 | 测试 | 否 | 无需处理 | 保留，作为兼容性回归测试 |
| `bowei_ai_dashboard/app/domain/issue_type.py` | 全文件 | 别名表、label、标准 key | alias / helper | 否 | 无需处理 | 保留为统一入口 |

## workflow.py 专项结论

- 是否存在 `issue_type` 相关裸字符串判断：没有。
- 是否需要下一轮接入 `issue_type` helper：不需要，至少在当前仓库事实下不需要。
- 原因：`git grep` 对 `bowei_ai_dashboard/app/services/workflow.py` 无命中；`0bec4b0` 的实际变更文件里也没有 `workflow.py`。

## extractor.py / confirmations.py / issues.py 专项结论

### extractor.py

- 仍有中文 `issue_type` 字面量与分类逻辑，主要用于提取器内部输出、兼容默认值和风险项归类。
- 已经接入了 `IT.is_decision()` 处理明确的决策分支。
- 后续如果要进一步统一，建议单独把提取层输出标准 key，再在展示层做 label 映射。

### confirmations.py

- 没有继续看到直接用中文字符串比较 `issue_type` 的业务判断。
- subtask issue 的解析和入库已接入 helper。
- 现存的中文 prefix 主要是兼容旧文本输入，不是新的裸判断问题。

### issues.py

- 没有继续看到 `issue_type == "决策"` 这类裸字符串业务判断。
- 新建、更新、筛选、企业教练上报都已接入 helper。
- 现存中文更多是展示文案和兼容输入，不属于本轮残留问题。

## 总结结论

本轮总结结论：B. 发现少量 P1/P2 残留，建议后续小步修。

说明：

- 没有发现会直接导致“决策事项无法上报企业教练”或“问题库筛选完全失效”的 P0 残留。
- 最高风险残留集中在 `extractor.py` 和 `excel_importer.py` 的中文写入/分类口径，风险等级是 P2。
- `workflow.py` 经过本轮重新核对，确认不需要接入 `issue_type` helper。
