import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..excel_importer import import_excel_data
from ..permissions import get_current_user_name, require_tech_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(current_user: str, db: Session):
    require_tech_admin(current_user, db)



@router.post("/import-excel")
async def import_excel(
    file: UploadFile = File(...),
    replace: bool = False,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "仅支持 .xlsx / .xlsm 格式")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        result = import_excel_data(db, tmp_path, replace=replace)
        db.commit()
        return {"ok": True, "imported": result}
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"导入失败：{e}")
    finally:
        tmp_path.unlink(missing_ok=True)
