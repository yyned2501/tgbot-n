from .manager import manager
from .config import API_ID, API_HASH, BOT_TOKEN, PROXY, DATABASE_URL
from .logger import logger

# 动态前缀
PREFIX = manager.prefix

__all__ = [
    "manager", "logger", "PREFIX",
    "API_ID", "API_HASH", "BOT_TOKEN", "PROXY", "DATABASE_URL"
]
