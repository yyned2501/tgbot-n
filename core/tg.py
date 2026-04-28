from .client import Client, CommandScope
from .keyboard import KeyboardFactory, Keyboards
import asyncio
from pyrogram import filters, enums, idle, errors
from pyrogram.filters import Filter
from pyrogram.types import (
    Message, CallbackQuery, InlineQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton
)

async def delete_later(message: Message, delay: int = 60):
    """
    异步延迟删除消息
    """
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

__all__ = [
    "Client", "CommandScope", "filters", "Filter", "enums", 
    "idle", "errors", "Message", "CallbackQuery", 
    "InlineQuery", "InlineKeyboardMarkup", "InlineKeyboardButton",
    "KeyboardFactory", "Keyboards", "delete_later"
]
