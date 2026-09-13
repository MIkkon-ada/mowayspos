from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import schemas
from ..ai.contracts import AIServiceError
from ..database import get_db
from ..domain.project_permissions import A_BATCH_IMPORT
from ..permissions import get_current_user_name
from ..services.project_init_ai_contracts import ProjectInitAiError
from ..services.project_init_file_parser import ProjectInitFileParseError, UnsupportedProjectInitFile
from ..services.project_plan_ai_import import (
    MAX_UPLOAD_BYTES,
    analyze_project_plan_upload,
)
from ..services.project_plan_import import (
    ProjectPlanImportValidationError,
    import_project_plan_rows,
)
from ..services.project_access import authorize_global_project_action


router = APIRouter(prefix="/api/projects/ai-plan-import", tags=["project-plan-ai-import"])


def _preview_response(draft) -> dict[str, object]:
    result = draft.result
    warnings = [warning.model_dump(mode="json") for warning in result.project_profile.warnings]
    warnings.extend(
        warning.model_dump(mode="json")
        for task in result.tasks
        for warning in task.warnings
    )
    return {
        "project_profile": result.project_profile.model_dump(mode="json"),
        "tasks": [task.model_dump(mode="json") for task in result.tasks],
        "warnings": warnings,
        "source_files": list(draft.source_files),
        "provider": result.provider,
        "model_name": result.model_name,
        "fallback_mode": draft.fallback_mode,
    }


@router.post("/preview", response_model=schemas.ProjectPlanAiImportPreviewResponse)
async def preview_ai_work_plan(
    file: UploadFile = File(...),
    project_name: str = Form(default=""),
    target_project_id: int | None = Form(default=None),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    authorize_global_project_action(current_user, A_BATCH_IMPORT, db)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        draft = analyze_project_plan_upload(
            db,
            content,
            file.filename or "工作计划.xlsx",
            actor=current_user,
            project_name=project_name,
            target_project_id=target_project_id,
        )
        return _preview_response(draft)
    except (ValueError, ProjectInitFileParseError, UnsupportedProjectInitFile) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProjectInitAiError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail="AI 导入服务暂不可用，请检查 AI 配置后重试") from exc
    finally:
        await file.close()


@router.post("/apply")
def apply_ai_work_plan(
    payload: schemas.ProjectBatchImportPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    authorize_global_project_action(current_user, A_BATCH_IMPORT, db)
    try:
        return import_project_plan_rows(db, payload.rows, current_user)
    except ProjectPlanImportValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "errors": exc.errors},
        ) from exc
