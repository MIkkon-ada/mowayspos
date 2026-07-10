# source_type 裸字符串残留审计

审计范围：`bowei_ai_dashboard/app/**/*.py`、`bowei_ai_dashboard/tests/**/*.py`，并抽查了前端展示映射。

审计时间：2026-07-10

## 结论先行

- 后端判断层没有发现继续用 `source_type == "人工..."` 这种裸字符串比较的残留。
- 目前残留主要集中在“旧默认值”“兼容别名”“展示文案”“测试输入”和“少量写入侧兜底”。
- 因为这些残留还会影响新对象的缺省写入语义，所以建议后续继续小步收口，但不属于 P0。

最终结论：B. 发现少量 P1/P2 残留，建议后续小步修。

## 发现清单

| 文件位置 | 当前写法 | 类别 | 是否需要修复 | 建议修复方式 | 风险等级 |
| --- | --- | --- | --- | --- | --- |
| `bowei_ai_dashboard/app/domain/source_type.py` | 维护 `manual / voice / meeting / ai_extract / import / unknown` 的别名表与 label 映射 | alias / helper | 否 | 保持作为统一入口，不再分散实现 | P2 |
| `bowei_ai_dashboard/app/models.py` | `Task / Achievement / AchievementSubmission / Issue` 的 `source_type` 默认仍是中文，如 `人工录入`、`人工补录` | 写入默认值 | 建议后续统一，但本轮不动 | 以后如要进一步收口，可逐步改为标准 key；当前已有写入 normalize 兜底 | P2 |
| `bowei_ai_dashboard/app/schemas.py` | `TaskPayload / AchievementPayload / IssuePayload` 的 `source_type` 默认仍是中文 | 写入默认值 | 建议后续统一，但本轮不动 | 后续可改为英文 key 默认值，保持对外兼容不变 | P2 |
| `bowei_ai_dashboard/app/routers/updates.py` | 创建更新时仍用 `payload.source_type or "人工录入"` 作为原始输入，再交给 helper 归一化 | 写入点兜底 | 否，当前已安全 | 继续保留 helper 归一化；如要更统一，可把前端默认也切到标准 key | P2 |
| `bowei_ai_dashboard/app/routers/issues.py` | 写入前已改为 `ST.normalize(payload.source_type or "人工录入")` | 写入点 | 否 | 保持现状即可 | P2 |
| `bowei_ai_dashboard/app/routers/achievements.py` | 写入前已改为 `ST.normalize(payload.source_type or "人工录入")` | 写入点 | 否 | 保持现状即可 | P2 |
| `bowei_ai_dashboard/app/routers/tasks.py` | 写入前已改为 `ST.normalize(...)`，批量导入也走 helper | 写入点 | 否 | 保持现状即可 | P2 |
| `bowei_ai_dashboard/app/routers/confirmations.py` | 任务 / 问题 / 成果落库前都已 normalize | 写入点 | 否 | 保持现状即可 | P2 |
| `bowei_ai_dashboard/app/routers/achievement_submissions.py` | `人工补录`、`人工补录确认` 仍作为输入别名传入 helper | 写入点 / alias 输入 | 否 | 保持兼容输入，不要直接删旧值 | P2 |
| `bowei_ai_dashboard/app/routers/projects.py` | 批量导入仍以 `批量导入` 作为输入，再 normalize | 写入点 / alias 输入 | 否 | 保持兼容输入，不要直接删旧值 | P2 |
| `bowei_ai_dashboard/app/services/workflow.py` | `aliases_for("import")` 参与 planned achievement 匹配，创建时写入标准 key | 后端判断 / 写入点 | 否 | 已经是 helper 驱动，维持即可 | P2 |
| `bowei_ai_dashboard/app/services/extractor.py` | 已使用 `ST.is_meeting(source_type)`，不再直接比较中文字符串 | 后端判断 | 否 | 保持 helper 判断，不回退到裸字符串 | P1 |
| `bowei_ai_dashboard/app/excel_importer.py` | Excel 导入仍以中文输入喂给 helper，但最终写入标准 key | 写入点 | 否 | 保持 helper 归一化 | P2 |
| `bowei_ai_dashboard/app/seed.py` | `source_type="内置兜底数据"` | seed / 初始化数据 | 否 | 仅内部种子数据，不属于业务判断分支 | P2 |
| `bowei_ai_dashboard/tests/test_source_type.py` | 使用中文别名验证 normalize | 测试 | 否 | 保留，覆盖兼容性很有价值 | P2 |
| `frontend/src/domain/confirmationFlow.ts` | `text(data.source_type).includes('会议')` 用于前端展示归类 | 展示 / 兼容推断 | 否 | 本轮不改前端；若后续收口，可迁到前端统一映射表 | P2 |

## 分析

### 1. 合法展示文案

可以保留，不视为风险：

- `人工录入`
- `人工补录`
- `语音提交`
- `会议纪要`
- `AI提取`
- `批量导入`

这些出现在展示、测试、兼容输入或 helper 的别名表里，仍然合理。

### 2. 合法别名表

`bowei_ai_dashboard/app/domain/source_type.py` 已经把旧中文与英文 key 收口到统一 helper。  
这部分不需要改，属于兼容层。

### 3. 测试用例

`bowei_ai_dashboard/tests/test_source_type.py` 使用中文输入来验证兼容性，这是预期行为，不算残留问题。

### 4. AI prompt / 文本

当前审计范围内没有发现需要因为 `source_type` 归一化而修改的 prompt。  
前端或 extractor 的中文提示文本仍可保留。

### 5. 后端判断

本轮没有发现继续用裸字符串做业务判断的 P0 残留。  
`extractor.py` 已切到 `ST.is_meeting(source_type)`，`workflow.py` 也已改为 helper 参与判断。

### 6. 写入点

关键写入点已经尽量接入 helper；目前残留的中文更多是：

- schema / model 的老默认值
- 写入入口的输入兜底
- seed 数据

这些都属于兼容层，不是直接业务判断。

## 迁移建议

### A. 立即应修

本轮没有发现必须马上修的 P0 裸字符串判断残留。

### B. 兼容保留

以下内容建议继续保留，以兼容旧数据和旧输入：

- `人工录入`
- `人工补录`
- `语音提交`
- `会议纪要`
- `AI提取`
- `批量导入`
- `内置兜底数据`

### C. 只展示

以下内容适合只作为展示文案保留，不必英文化：

- 中文标签
- 前端提示语
- 测试里的中文输入样例

## 下一轮 N3-B 建议范围

只建议，不执行：

1. 进一步把 `app/schemas.py` 的 `source_type` 默认值收口为标准 key。
2. 逐步把 `app/models.py` 的 `source_type` 默认值与标准 key 对齐。
3. 如果想进一步统一前端，补一层 `source_type -> label` 的展示映射，而不是页面里直接写中文判断。
4. 保持 `ST.normalize()` 作为唯一的后端归一化入口。

## 明确结论

- 现在最危险的不是裸字符串判断，而是“老默认值仍然可能写进新记录”的兼容风险；级别是 P2。
- 可以以后再迁移的是 schema / model 的中文默认值，以及 seed 里的内部文案。
- 中文可以保留的是展示文案、测试输入、别名兼容值。
- 建议下一轮继续做 normalize helper 的收口审计，但不需要立刻做大迁移。
