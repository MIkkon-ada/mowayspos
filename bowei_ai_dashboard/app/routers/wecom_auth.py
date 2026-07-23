"""企业微信登录路由。

提供两个接口：
- GET /api/auth/wecom/qrcode: 返回扫码登录 URL，前端跳转过去
- GET /api/auth/wecom/callback: 企业微信回调入口，拿 code 换 userid 建会话

两个接口都在 /api/auth/ 前缀下，已被 _PUBLIC_PREFIXES 放行，无需登录态。
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_session, record_login_attempt
from ..database import get_db
from ..models import Account
from ..services import wecom
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/wecom", tags=["wecom-auth"])


def _frontend_url(path: str, params: dict | None = None) -> str:
    """构造前端 URL，用于回调后重定向回前端。

    如果配置了 FRONTEND_BASE_URL 用绝对地址，否则用相对路径（同域部署）。
    """
    base = get_settings().frontend_base_url.rstrip("/")
    if base:
        url = f"{base}{path}"
    else:
        url = path
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


@router.get("/qrcode")
def wecom_qrcode():
    """返回扫码登录 URL。

    前端调这个接口拿到 url 后，用 window.location.href 跳转过去，
    用户在企业微信扫码确认后，企业微信会回调 /api/auth/wecom/callback。
    """
    settings = get_settings()
    if not settings.wecom_enabled:
        raise HTTPException(status_code=503, detail="wecom_login_disabled")
    url = wecom.build_qrcode_url()
    return {"url": url}


@router.get("/callback")
def wecom_callback(
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """企业微信 OAuth 回调入口。

    流程：
    1. 用 code 调企业微信 API 换 userid
    2. 用 userid 查 Account.wecom_userid
    3. 找到 → 创建会话，重定向回前端首页
    4. 没找到 → 重定向回登录页，带 reason=wecom_unbound

    任何异常都重定向回登录页，带 reason=wecom_error，不向前端暴露错误细节。
    """
    settings = get_settings()
    if not settings.wecom_enabled:
        return RedirectResponse(_frontend_url("/login", {"reason": "wecom_disabled"}))

    if not code:
        logger.warning("wecom callback missing code")
        return RedirectResponse(_frontend_url("/login", {"reason": "wecom_error"}))

    # 1. 用 code 换 userid
    try:
        userid = wecom.get_userid_by_code(code)
    except Exception as e:
        logger.error("wecom get_userid failed: %s", e)
        return RedirectResponse(_frontend_url("/login", {"reason": "wecom_error"}))

    if not userid:
        logger.warning("wecom callback got empty userid")
        return RedirectResponse(_frontend_url("/login", {"reason": "wecom_error"}))

    # 2. 查账号
    account = db.query(Account).filter(Account.wecom_userid == userid).first()
    if not account:
        logger.info("wecom login unbound userid=%s", userid)
        return RedirectResponse(_frontend_url("/login", {"reason": "wecom_unbound"}))

    # 3. 检查账号状态
    if account.status != "active":
        logger.info("wecom login account disabled: %s", account.username)
        return RedirectResponse(_frontend_url("/login", {"reason": "account_disabled"}))

    # 4. 创建会话
    sid = create_session(account.username)
    record_login_attempt(account.username, success=True, ip_address="", user_agent="wecom")
    logger.info("wecom login success: %s", account.username)

    # 更新最后登录时间
    try:
        from ..time_utils import utc_now
        account.last_login_at = utc_now()
        db.commit()
    except Exception:
        db.rollback()

    # 5. 重定向回前端首页，带 cookie
    resp = RedirectResponse(_frontend_url("/home/dashboard"))
    resp.set_cookie(
        settings.session_cookie_name,
        sid,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return resp
