"""
Web 配置面板 - FastAPI 服务

集成 Telegram Login Widget 验证，JWT 会话管理，
与 tgbot-n 共享 asyncio 事件循环和数据库。
"""
import hashlib
import hmac
import secrets
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.config import BOT_TOKEN

from .routes import router

# ─── FastAPI App ────────────────────────────────────────
app = FastAPI(title="tgbot-n Web Panel", docs_url="/api/docs")

# JWT 签名密钥（启动时随机生成）
JWT_SECRET = secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

# 静态文件
_static_dir = Path(__file__).parent / "static"


# ─── 中间件：CORS ───────────────────────────────────────
@app.middleware("http")
async def cors_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ─── 路由 ───────────────────────────────────────────────
app.include_router(router, prefix="/api")


@app.get("/")
async def index():
    return FileResponse(_static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "time": int(time.time())}


# ─── Telegram 验证工具函数 ─────────────────────────────
def verify_telegram_auth(data: dict) -> bool:
    """
    验证 Telegram Login Widget 回调数据。
    使用 BOT_TOKEN 的 SHA256 作为 HMAC 密钥校验 hash。
    """
    check_hash = data.get("hash", "")
    if not check_hash:
        return False

    # 按 key 字母排序，拼接 data_check_string
    items = sorted(
        (k, v) for k, v in data.items() if k != "hash"
    )
    data_check_string = "\n".join(f"{k}={v}" for k, v in items)

    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, check_hash):
        return False

    # 检查过期（默认 24 小时）
    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        return False

    return True


def create_jwt(user_id: int, username: str = "", first_name: str = "") -> str:
    """创建 JWT Token"""
    import jwt

    payload = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "exp": int(time.time()) + JWT_EXPIRE_DAYS * 86400,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """解码 JWT Token，失败返回 None"""
    import jwt

    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ─── 启动函数 ───────────────────────────────────────────
async def start_server(host: str = "0.0.0.0", port: int = 8080):
    """在现有 asyncio 事件循环中启动 uvicorn（非阻塞）"""
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()
