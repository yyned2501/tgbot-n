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


def user_command(commands, prefixes=None):
    """
    自定义命令过滤器 - 运行时从 client._prefix 读取当前 Userbot 的前缀。

    用法::

        @Client.on_message(user_command("ping") & filters.me)

    流程:
        1. 消息到达时读取 client._prefix（account_manager 启动时缓存）
        2. 回退到 app.PREFIX（未设置 _prefix 时）
        3. 若显式传入 prefixes 则使用传入值
        4. 构造 filters.command() 并执行匹配

    参数:
        commands: 命令名字符串或列表
        prefixes: 可选，显式覆盖前缀
    """
    if isinstance(commands, str):
        commands = [commands]

    async def func(flt, client: Client, message: Message):
        # 1. 确定前缀：优先用显式传入的，其次用 client 缓存，最后用全局
        if prefixes is not None:
            resolved_prefixes = prefixes
        else:
            user_prefix = getattr(client, "_prefix", None)
            if user_prefix:
                resolved_prefixes = [user_prefix]
            else:
                from . import app
                resolved_prefixes = [app.PREFIX]

        # 2. 构造原生 filters.command 并执行匹配
        cmd_filter = filters.command(commands, resolved_prefixes)
        return await cmd_filter(client, message)

    return filters.create(func)


__all__ = [
    "Client", "CommandScope", "filters", "Filter", "enums",
    "idle", "errors", "Message", "CallbackQuery",
    "InlineQuery", "InlineKeyboardMarkup", "InlineKeyboardButton",
    "KeyboardFactory", "Keyboards", "delete_later", "user_command",
]
