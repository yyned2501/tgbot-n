from .client import Client, CommandScope
from .config import API_ID, API_HASH, BOT_TOKEN, PROXY, DATABASE_URL
from .database import async_session, init_db, get_setting, set_setting
from .models import Base, SystemSetting, ZhuqueResult
from .manager import manager
from .logger import logger
from pyrogram import filters, enums, idle, errors
from pyrogram.filters import Filter
from pyrogram.types import Message, CallbackQuery, InlineQuery, InlineKeyboardMarkup, InlineKeyboardButton

# 导出动态配置
PREFIX = manager.prefix

__all__ = [
    "Client", 
    "CommandScope",
    "filters", 
    "Filter",
    "enums", 
    "idle", 
    "errors",
    "Message", 
    "CallbackQuery", 
    "InlineQuery",
    "InlineKeyboardMarkup",
    "InlineKeyboardButton",
    "API_ID",
    "API_HASH",
    "BOT_TOKEN",
    "PREFIX",
    "PROXY",
    "DATABASE_URL",
    "Base",
    "SystemSetting",
    "ZhuqueResult",
    "async_session",
    "init_db",
    "get_setting",
    "set_setting",
    "manager",
    "logger"
]
