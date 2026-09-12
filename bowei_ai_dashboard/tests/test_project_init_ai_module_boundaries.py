from app.services import project_init_ai_agent as facade


def test_facade_reexports_contract_types():
    from app.services import project_init_ai_contracts as contracts

    assert facade.AgentTask is contracts.AgentTask
    assert facade.AgentSubTask is contracts.AgentSubTask
    assert facade.Evidence is contracts.Evidence
    assert facade.ProjectInitAiResult is contracts.ProjectInitAiResult
    assert facade.ProjectInitAiError is contracts.ProjectInitAiError
    assert facade.SourceChunk.__module__ == "app.services.project_init_file_parser"


def test_facade_reexports_normalization_helpers():
    from app.services import project_init_ai_normalization as normalization

    assert facade.normalize_agent_result is normalization.normalize_agent_result
    assert facade._merge_tasks is normalization._merge_tasks
    assert facade.has_cross_batch_task_conflict is normalization.has_cross_batch_task_conflict
