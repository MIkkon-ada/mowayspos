"""企业微信登录 API 封装。

包含：
- get_access_token: 获取 access_token（带内存缓存，2h 有效）
- build_qrcode_url: 生成扫码登录 URL
- get_userid_by_code: 用 OAuth code 换企业微信 userid

使用标准库 urllib，零新增依赖。
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Optional

from ..settings import get_settings

# 模块级缓存：access_token 全局唯一，2h 有效，企微有调用频率限制
_access_token: Optional[str] = None
_access_token_expires_at: float = 0

_WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
_WECOM_LOGIN_BASE = "https://open.work.weixin.qq.com/wwopen/sso/qrConnect"


class WecomError(RuntimeError):
    """企业微信 API 调用失败。"""


def _http_get_json(url: str, params: dict | None = None, timeout: float = 10.0) -> dict:
    """用标准库发起 GET 请求，返回 JSON dict。"""
    if params:
        query = urllib.parse.urlencode(params)
        full_url = f"{url}?{query}"
    else:
        full_url = url
    req = urllib.request.Request(full_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise WecomError(f"wecom http error {e.code}: {e.reason}") from e
    except Exception as e:
        raise WecomError(f"wecom request failed: {e}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise WecomError(f"wecom response not json: {body[:200]}") from e


def _http_post_json(url: str, payload: dict, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise WecomError(f"wecom request failed: {e}") from e


def get_access_token() -> str:
    """获取企业微信 access_token，带内存缓存。

    access_token 全局唯一，2h 有效，企微有调用频率限制（同一应用 10000 次/天），
    所以必须缓存，不能每次请求都拿。
    """
    global _access_token, _access_token_expires_at
    # 提前 5 分钟过期，避免边界问题
    if _access_token and time.time() < _access_token_expires_at - 300:
        return _access_token

    s = get_settings()
    data = _http_get_json(
        f"{_WECOM_API_BASE}/gettoken",
        params={"corpid": s.wecom_corpid, "corpsecret": s.wecom_secret},
    )
    if data.get("errcode") != 0:
        raise WecomError(f"wecom gettoken failed: {data}")
    _access_token = data["access_token"]
    _access_token_expires_at = time.time() + data.get("expires_in", 7200)
    return _access_token


def send_text_message(userids: list[str], content: str) -> bool:
    recipients = [userid.strip() for userid in userids if userid and userid.strip()]
    if not recipients:
        return False
    settings = get_settings()
    result = _http_post_json(
        f"{_WECOM_API_BASE}/message/send?access_token={get_access_token()}",
        {"touser": "|".join(recipients), "msgtype": "text", "agentid": int(settings.wecom_agent_id), "text": {"content": content}},
    )
    if result.get("errcode") != 0:
        raise WecomError(f"wecom send message failed: {result}")
    return True


def build_qrcode_url(state: str = "") -> str:
    """生成扫码登录 URL，前端跳转过去让用户扫码。"""
    s = get_settings()
    params = {
        "appid": s.wecom_corpid,
        "agentid": s.wecom_agent_id,
        "redirect_uri": s.wecom_redirect_uri,
        "state": state or "wecom-login",
    }
    return f"{_WECOM_LOGIN_BASE}?{urllib.parse.urlencode(params)}"


def build_silent_auth_url() -> str:
    """生成网页静默授权 URL（snsapi_base）。

    用户从企业微信客户端内打开此 URL 时，企微会自动带上 code 回调，
    无需用户手动扫码。适用于工作台应用入口免登场景。

    授权域：https://open.weixin.qq.com/connect/oauth2/authorize
    scope=snsapi_base：静默授权，不弹窗，自动获取 userid
    """
    s = get_settings()
    params = {
        "appid": s.wecom_corpid,
        "redirect_uri": s.wecom_redirect_uri,
        "response_type": "code",
        "scope": "snsapi_base",
    }
    return f"https://open.weixin.qq.com/connect/oauth2/authorize?{urllib.parse.urlencode(params)}#wechat_redirect"


def get_userid_by_code(code: str) -> str:
    """用 OAuth code 换企业微信 userid。

    code 是企业微信回调时带的临时凭证，5 分钟内有效，只能用一次。
    """
    token = get_access_token()
    data = _http_get_json(
        f"{_WECOM_API_BASE}/auth/getuserinfo",
        params={"access_token": token, "code": code},
    )
    if data.get("errcode") != 0:
        raise WecomError(f"wecom getuserinfo failed: {data}")
    # 企业成员返回 userid；非企业成员返回 openid（这里不处理非企业成员场景）
    return data.get("userid") or ""


def list_department_users(department_id: int = 1, fetch_child: bool = True) -> list[dict]:
    """拉取企业微信通讯录成员（精简列表）。

    Args:
        department_id: 部门 ID，默认 1（根部门）
        fetch_child: 是否递归拉子部门成员，默认 True（一次拿全员）

    Returns:
        [{"userid": "zhangsan", "name": "张三", "department": [1, 2]}, ...]

    需要应用有「通讯录」权限（管理后台 → 应用 → API 接收消息 → 通讯录权限）。
    """
    token = get_access_token()
    data = _http_get_json(
        f"{_WECOM_API_BASE}/user/simplelist",
        params={
            "access_token": token,
            "department_id": department_id,
            "fetch_child": 1 if fetch_child else 0,
        },
    )
    if data.get("errcode") != 0:
        # 60011 表示无通讯录权限，给个明确提示
        if data.get("errcode") == 60011:
            raise WecomError(
                "wecom department permission denied: 应用对所请求部门无查看权限，或该部门不在应用可见范围"
            )
        raise WecomError(f"wecom simplelist failed: {data}")
    return data.get("userlist") or []


def list_department_user_details(department_id: int = 1, fetch_child: bool = True) -> list[dict]:
    """拉取企业微信通讯录成员详情，包含部门 ID 和职位信息。"""
    token = get_access_token()
    data = _http_get_json(
        f"{_WECOM_API_BASE}/user/list",
        params={
            "access_token": token,
            "department_id": department_id,
            "fetch_child": 1 if fetch_child else 0,
        },
    )
    if data.get("errcode") != 0:
        if data.get("errcode") == 60011:
            raise WecomError("wecom department permission denied: 应用对所请求部门无查看权限，或该部门不在应用可见范围")
        raise WecomError(f"wecom user detail list failed: {data}")
    return data.get("userlist") or []


def list_departments() -> list[dict]:
    """拉取企业微信部门树。"""
    data = _http_get_json(
        f"{_WECOM_API_BASE}/department/list",
        params={"access_token": get_access_token()},
    )
    if data.get("errcode") != 0:
        if data.get("errcode") == 60011:
            raise WecomError("wecom department permission denied: 应用对所请求部门无查看权限，或该部门不在应用可见范围")
        raise WecomError(f"wecom department list failed: {data}")
    return data.get("department") or []


def list_visible_department_users(*, details: bool = False) -> tuple[list[dict], list[dict]]:
    """读取应用可见的非根部门成员，避免请求企业根部门全员。"""
    departments = list_departments()
    department_ids: list[int] = []
    seen_department_ids: set[int] = set()
    for department in departments:
        try:
            department_id = int(department.get("id"))
        except (TypeError, ValueError):
            continue
        if department_id == 1 or department_id in seen_department_ids:
            continue
        seen_department_ids.add(department_id)
        department_ids.append(department_id)
    if not department_ids:
        raise WecomError("wecom no visible departments: 请在企业微信管理后台将至少一个业务部门加入应用可见范围")

    fetch_users = list_department_user_details if details else list_department_users
    users: list[dict] = []
    seen_userids: set[str] = set()
    for department_id in department_ids:
        for user in fetch_users(department_id=department_id, fetch_child=False):
            userid = str(user.get("userid") or "").strip()
            if not userid or userid in seen_userids:
                continue
            seen_userids.add(userid)
            users.append(user)
    return users, departments


def build_department_paths(departments: list[dict]) -> dict[int, dict]:
    """把企业微信部门列表整理为可展示的部门路径。"""
    by_id = {int(row["id"]): row for row in departments if row.get("id") is not None}
    result: dict[int, dict] = {}
    for department_id, row in by_id.items():
        names: list[str] = []
        seen: set[int] = set()
        current = department_id
        while current in by_id and current not in seen:
            seen.add(current)
            names.append(str(by_id[current].get("name") or ""))
            parent_id = by_id[current].get("parentid")
            if parent_id in (None, 0, current):
                break
            current = int(parent_id)
        result[department_id] = {
            "id": department_id,
            "name": str(row.get("name") or ""),
            "parent_id": int(row.get("parentid") or 0),
            "path": " / ".join(reversed([name for name in names if name])),
        }
    return result
