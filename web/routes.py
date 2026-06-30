"""
Web 配置面板 - API 路由

包含：认证、插件配置、账号管理、日志查看。
"""
import json
import logging
from collections import deque
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from core import db, app
from core.account_manager import account_manager
from core.config import CONFIG
from core.logger import logger

from .schemas import PLUGIN_SCHEMAS, get_schema, get_all_schemas

router = APIRouter()

# ─── 日志捕获 Handler ───────────────────────────────────
_log_buffer: deque[dict] = deque(maxlen=500)


class WebLogHandler(logging.Handler):
    """捕获日志到内存环形缓冲区，供 Web 面板查看。"""

    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "time": self.format(record),
                "level": record.levelname,
                "module": record.module,
                "message": record.getMessage(),
            }
            _log_buffer.append(entry)
        except Exception:
            pass


# 注册日志 handler
_handler = WebLogHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s", datefmt="%H:%M:%S"))
logger.addHandler(_handler)


# ─── 认证依赖 ──────────────────────────────────────────
def get_current_user(request: Request) -> dict:
    """从 Authorization header 或 cookie 中提取并验证 JWT"""
    from .server import decode_jwt

    # 优先从 header 获取
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = request.cookies.get("token", "")

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return payload


def require_owner(user: dict) -> None:
    """要求当前用户是 Bot Owner"""
    if user["user_id"] != app.manager.owner_id:
        raise HTTPException(status_code=403, detail="需要 Bot Owner 权限")


# ═══════════════════════════════════════════════════════
# 认证相关
# ═══════════════════════════════════════════════════════

@router.get("/auth/info")
async def auth_info():
    """公开端点：返回 Bot 用户名等信息，供前端渲染 Login Widget。"""
    bot_username = CONFIG.get("web", {}).get("bot_username", "")
    return {"bot_username": bot_username}


@router.post("/auth/telegram")
async def auth_telegram(data: dict):
    """
    Telegram Login Widget 回调。
    验证签名 → 检查是否为合法用户 → 签发 JWT。
    """
    from .server import verify_telegram_auth, create_jwt

    if not verify_telegram_auth(data):
        raise HTTPException(status_code=401, detail="Telegram 验证失败")

    user_id = int(data.get("id", 0))
    if not user_id:
        raise HTTPException(status_code=400, detail="无效的用户 ID")

    # 检查是否为已绑定用户（owner 或 user_accounts 中的用户）
    owner_id = app.manager.owner_id
    account_record = await account_manager.get_account_record(user_id)

    if user_id != owner_id and not account_record:
        raise HTTPException(
            status_code=403,
            detail="此 Telegram 账号未绑定到系统",
        )

    token = create_jwt(
        user_id=user_id,
        username=data.get("username", ""),
        first_name=data.get("first_name", ""),
    )

    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": data.get("username", ""),
            "first_name": data.get("first_name", ""),
            "is_owner": user_id == owner_id,
        },
    }


@router.get("/auth/me")
async def auth_me(request: Request):
    """获取当前用户信息"""
    user = get_current_user(request)
    owner_id = app.manager.owner_id
    return {
        "id": user["user_id"],
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "is_owner": user["user_id"] == owner_id,
    }


# ═══════════════════════════════════════════════════════
# 插件配置
# ═══════════════════════════════════════════════════════

@router.get("/plugins")
async def list_plugins(request: Request):
    """获取所有可配置插件列表"""
    get_current_user(request)  # 验证登录
    return {"plugins": get_all_schemas()}


@router.get("/plugins/{plugin_id}/schema")
async def get_plugin_schema(plugin_id: str, request: Request):
    """获取指定插件的配置 schema"""
    get_current_user(request)
    schema = get_schema(plugin_id)
    if not schema:
        raise HTTPException(status_code=404, detail="插件不存在")
    return schema


class ConfigUpdate(BaseModel):
    values: dict


@router.get("/plugins/{plugin_id}/config")
async def get_plugin_config(
    plugin_id: str,
    request: Request,
    account_id: Optional[int] = Query(None),
):
    """
    获取插件配置。
    - 无 account_id: 返回全局默认配置
    - 有 account_id: 返回该账号的配置（未配置则回退全局）
    """
    user = get_current_user(request)
    schema = get_schema(plugin_id)
    if not schema:
        raise HTTPException(status_code=404, detail="插件不存在")

    # 非 owner 只能查看自己的配置
    if user["user_id"] != app.manager.owner_id:
        account_id = user["user_id"]

    owner_id = account_id or 0

    raw = await db.get_setting(f"plugin_config:{plugin_id}", "{}", owner_id=owner_id)
    try:
        config = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        config = {}

    # 用 schema 默认值填充缺失字段
    for field in schema["fields"]:
        if field["key"] not in config:
            config[field["key"]] = field["default"]

    return {"plugin_id": plugin_id, "account_id": owner_id, "config": config}


@router.put("/plugins/{plugin_id}/config")
async def update_plugin_config(
    plugin_id: str,
    body: ConfigUpdate,
    request: Request,
    account_id: Optional[int] = Query(None),
):
    """保存插件配置"""
    user = get_current_user(request)
    schema = get_schema(plugin_id)
    if not schema:
        raise HTTPException(status_code=404, detail="插件不存在")

    # 非 owner 只能修改自己的配置
    if user["user_id"] != app.manager.owner_id:
        account_id = user["user_id"]

    owner_id = account_id or 0

    # 验证字段值类型
    validated = {}
    field_map = {f["key"]: f for f in schema["fields"]}
    for key, value in body.values.items():
        if key not in field_map:
            continue  # 忽略未知字段
        field = field_map[key]
        # 类型转换
        if field["type"] == "slider":
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = field["default"]
        validated[key] = value

    await db.set_setting(
        f"plugin_config:{plugin_id}",
        json.dumps(validated, ensure_ascii=False),
        owner_id=owner_id,
    )

    logger.info(f"[Web] 保存插件配置: {plugin_id} (account={owner_id})")
    return {"ok": True, "saved": validated}


@router.delete("/plugins/{plugin_id}/config")
async def delete_plugin_config(
    plugin_id: str,
    request: Request,
    account_id: Optional[int] = Query(None),
):
    """删除插件配置（恢复默认值）"""
    user = get_current_user(request)
    require_owner(user)

    owner_id = account_id or 0
    await db.delete_setting(f"plugin_config:{plugin_id}", owner_id=owner_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# 账号管理
# ═══════════════════════════════════════════════════════

@router.get("/accounts")
async def list_accounts(request: Request):
    """获取所有账号信息"""
    user = get_current_user(request)

    if user["user_id"] == app.manager.owner_id:
        # Owner 可看所有账号
        accounts = await account_manager.get_accounts_info()
    else:
        # 普通用户只看自己
        accounts = await account_manager.get_accounts_info(user["user_id"])

    return {"accounts": accounts}


@router.post("/accounts/{owner_id}/toggle-module")
async def toggle_module(
    owner_id: int,
    request: Request,
    module_name: str = Query(...),
):
    """切换账号的插件启用状态"""
    user = get_current_user(request)
    require_owner(user)

    enabled = await account_manager.toggle_module(owner_id, module_name)
    return {"ok": True, "module": module_name, "enabled": enabled}


@router.get("/accounts/{owner_id}/modules")
async def get_account_modules(owner_id: int, request: Request):
    """获取账号的插件启用状态"""
    user = get_current_user(request)
    if user["user_id"] != app.manager.owner_id and user["user_id"] != owner_id:
        raise HTTPException(status_code=403, detail="无权访问")

    disabled = await account_manager.load_disabled_modules(owner_id)
    plugins = app.manager.get_user_plugin_info()

    for p in plugins:
        p["enabled"] = p["module"] not in disabled

    return {"owner_id": owner_id, "plugins": plugins}


@router.post("/accounts/{owner_id}/restart")
async def restart_account(owner_id: int, request: Request):
    """重启指定账号的 Userbot"""
    user = get_current_user(request)
    require_owner(user)

    success = await account_manager.restart_account(owner_id)
    return {"ok": success}


@router.post("/accounts/{owner_id}/prefix")
async def set_account_prefix(
    owner_id: int,
    request: Request,
    prefix: str = Query(...),
):
    """设置账号的指令前缀"""
    user = get_current_user(request)
    if user["user_id"] != app.manager.owner_id and user["user_id"] != owner_id:
        raise HTTPException(status_code=403, detail="无权访问")

    await account_manager.save_prefix(owner_id, prefix)
    client = account_manager.get_account(owner_id)
    if client:
        client._prefix = prefix
    return {"ok": True, "prefix": prefix}


# ═══════════════════════════════════════════════════════
# 系统状态 & 日志
# ═══════════════════════════════════════════════════════

@router.get("/system/status")
async def system_status(request: Request):
    """获取系统状态概览"""
    user = get_current_user(request)

    accounts = account_manager.get_all_accounts()
    account_list = []
    for oid, client in accounts.items():
        try:
            me = await client.get_me()
            account_list.append({
                "owner_id": oid,
                "username": me.username or "N/A",
                "first_name": me.first_name or "",
                "is_connected": True,
            })
        except Exception:
            account_list.append({
                "owner_id": oid,
                "username": "N/A",
                "first_name": "在线",
                "is_connected": True,
            })

    return {
        "owner_id": app.manager.owner_id,
        "prefix": app.manager.prefix,
        "accounts": account_list,
        "account_count": len(account_list),
        "bot_connected": app.manager.bot is not None and app.manager.bot.is_connected,
    }


@router.get("/logs")
async def get_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    level: Optional[str] = Query(None),
):
    """获取最近的日志"""
    get_current_user(request)

    logs = list(_log_buffer)
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]

    return {"logs": logs[-limit:], "total": len(_log_buffer)}
