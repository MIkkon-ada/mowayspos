# issue_type 归一化覆盖审计

审计范围：`bowei_ai_dashboard/app/**/*.py`、`bowei_ai_dashboard/tests/**/*.py`

审计时间：2026-07-10

## 结论先行

- 本轮已经补了统一的 `issue_type` 归一化 helper，并接入了最明确的后端判断/写入点。
- 目前没有发现必须立刻大改 `issue_flow.py` 或前端 UI 的必要性。
- 因为前端与部分 API 仍直接展示中文 `issue_type`，本轮保留了兼容中文落库口径，没有做大迁移。

最终结论：B. 发现少量兼容残留，建议后续小步收口。

## 本轮覆盖点

| 文件位置 | 当前写法 | 类别 | 是否需要修复 | 建议修复方式 | 风险等级 |
| --- | --- | --- | --- | --- | --- |
| `bowei_ai_dashboard/app/domain/issue_type.py` | 新增统一 helper：`normalize / is_issue / is_risk / is_coordination / is_decision / label / aliases_for` | helper | 否 | 作为后续唯一归一化入口 | P2 |
| `bowei_ai_dashboard/app/routers/issues.py` | 新建/更新/筛选/上报企业教练决策都接入 helper；落库仍保持当前中文展示值 | 后端判断 / 写入点 | 否 | 保持兼容写入，内部判断统一走 helper | P1 |
| `bowei_ai_dashboard/app/routers/confirmations.py` | AI 确认入库的 issue 生成逻辑接入 helper；写入时继续保留中文展示值 | 后端判断 / 写入点 | 否 | 保持 helper 归一化，落库仍走兼容中文值 | P1 |
| `bowei_ai_dashboard/app/routers/dashboard.py` | CEO 决策统计 / 看板判断从裸字符串切到 helper | 后端判断 | 否 | 保持 helper 判断，避免继续直接匹配中文 | P1 |
| `bowei_ai_dashboard/app/services/extractor.py` | 只修了明确的 decision 判定分支，避免裸字符串判断 | 后端判断 | 否 | 保持文本提取中文输出，不扩展到展示层 | P2 |
| `bowei_ai_dashboard/tests/test_issue_type.py` | 新增 helper、别名、筛选逻辑测试 | 测试 | 否 | 保留，作为后续收口回归保护 | P2 |

## 未覆盖点

这些点本轮刻意没有扩大处理范围：

- `bowei_ai_dashboard/app/domain/issue_flow.py` 未做大改，继续保留旧中文语义层。
- `bowei_ai_dashboard/app/schemas.py` 与 `bowei_ai_dashboard/app/models.py` 的 `issue_type` 默认值未统一成英文 key。
- `bowei_ai_dashboard/app/excel_importer.py` 仍沿用旧中文写入口径。
- `frontend/src/**` 未修改，仍按现有中文展示与筛选工作。
- 历史数据未迁移。

## 后续建议

1. 如果后面要进一步统一，优先考虑把 `issue_flow.py` 的旧中文别名与新 helper 接口对齐，但要单独拆成一个小任务。
2. 如果前端未来要支持英文 key 展示，再补一层前端映射，不要和后端归一化混在一起。
3. 对导入器和种子数据，只在确认不会影响现有 UI 的前提下再收口。

## 明确结论

- 本轮已经解决的，是“后端判断里直接比较中文 `issue_type`”的问题。
- 本轮刻意保留的，是“中文展示/中文落库兼容”。
- 还不需要做大范围状态迁移，也不建议现在把 `issue_flow.py` 重构成新系统。
