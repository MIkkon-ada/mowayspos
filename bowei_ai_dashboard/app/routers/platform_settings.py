import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..permissions import get_current_user_name, require_tech_admin

router = APIRouter(prefix="/api/platform-settings", tags=["platform-settings"])

_DEFAULTS: dict = {
    "platform_name": "博维AI升级项目驾驶舱",
    "language": "zh",
    "timezone": "（GMT+08:00）北京、上海、香港",
    "theme_color": "#0369A1",
    "logo_url": None,
    "notify_delay": True,
    "notify_ai": True,
    "notify_decision": True,
    "notify_weekly": False,
    "notify_channels": ["站内信", "企业微信"],
    "confidence": 75,
    "two_fa": True,
    "session_ttl": "8 小时",
}


def _get_row(db: Session) -> models.PlatformSettings:
    row = db.query(models.PlatformSettings).filter_by(id=1).first()
    if not row:
        row = models.PlatformSettings(id=1, data_json=json.dumps(_DEFAULTS))
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("")
def get_settings(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    require_tech_admin(current_user, db)
    row = _get_row(db)
    data = {**_DEFAULTS, **json.loads(row.data_json or "{}")}
    return data


@router.put("")
async def save_settings(
    request_data: dict,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    require_tech_admin(current_user, db)
    row = _get_row(db)
    existing = {**_DEFAULTS, **json.loads(row.data_json or "{}")}
    existing.update(request_data)
    row.data_json = json.dumps(existing, ensure_ascii=False)
    db.commit()
    return existing
