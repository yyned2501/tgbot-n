import asyncio
from enum import Enum
from pyrogram import Client as PyrogramClient, filters, enums, idle
from pyrogram.types import Message, CallbackQuery, InlineQuery, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeDefault
from .config import PROXY

class CommandScope(Enum):
    DEFAULT = BotCommandScopeDefault()
    PRIVATE = BotCommandScopeAllPrivateChats()

# 核心 Client 类，继承自 Pyrogram 的 Client
class Client(PyrogramClient):
    # 用于存储待注册的机器人命令
    _registered_commands = []

    def __init__(self, name: str, **kwargs):
        # 代理自动加载逻辑
        if "proxy" not in kwargs and PROXY.get("enabled"):
            kwargs["proxy"] = {
                "scheme": PROXY.get("scheme", "socks5"),
                "hostname": PROXY.get("hostname", "127.0.0.1"),
                "port": PROXY.get("port", 7890),
                "username": PROXY.get("username"),
                "password": PROXY.get("password")
            }
        super().__init__(name, **kwargs)
        self._pending_asks = {}
        
        # 注册通过 @bot_command 装饰的命令
        self._register_custom_commands()

        # 注册一个高优先级的处理器来拦截等待中的回复
        from pyrogram.handlers import MessageHandler
        self.add_handler(
            MessageHandler(self._ask_interceptor),
            group=-100
        )

    def add_handler(self, handler, group: int = 0):
        """
        重写 add_handler，实现模块级开关拦截
        """
        from .manager import manager
        
        original_callback = handler.callback
        module_name = getattr(original_callback, "__module__", "")

        # 只有 Userbot 的插件才受此拦截器影响
        if self.name == "my_userbot" and module_name.startswith("plugins.user"):
            async def wrapped_callback(client, message, *args, **kwargs):
                if not manager.is_module_enabled(module_name):
                    return
                return await original_callback(client, message, *args, **kwargs)
            
            handler.callback = wrapped_callback
        
        super().add_handler(handler, group)

    def _register_custom_commands(self):
        """
        注册通过 @bot_command 装饰的命令处理器
        """
        for cmd in self._registered_commands:
            # 根据插件目录过滤，避免 Bot 加载 User 插件的命令，反之亦然
            module_name = cmd["func"].__module__
            if self.name == "my_assistant_bot" and not module_name.startswith("plugins.bot"):
                continue
            if self.name == "my_userbot" and not module_name.startswith("plugins.user"):
                continue

            from pyrogram.handlers import MessageHandler
            from pyrogram import filters
            
            cmd_filter = filters.command(cmd["command"])
            if cmd["filters"]:
                cmd_filter &= cmd["filters"]
            
            self.add_handler(
                MessageHandler(cmd["func"], cmd_filter),
                group=cmd["group"]
            )

    @classmethod
    def bot_command(cls, command: str, description: str, filters=None, group: int = 0, scopes: list[CommandScope] = None):
        """
        装饰器：注册机器人命令并记录描述，用于自动生成菜单
        """
        if scopes is None:
            scopes = [CommandScope.PRIVATE]
            
        def decorator(func):
            # 记录命令信息
            cls._registered_commands.append({
                "command": command,
                "description": description,
                "filters": filters,
                "group": group,
                "func": func,
                "scopes": scopes
            })
            return func
        return decorator

    async def sync_bot_commands(self):
        """
        同步已注册的命令到 Telegram 菜单，支持不同 Scope
        """
        if not self.me or not self.me.is_bot:
            return
        
        from .logger import logger
        
        # 准备不同 Scope 的命令字典
        scopes_dict: dict[CommandScope, list[BotCommand]] = {
            scope: [] for scope in CommandScope
        }
        
        # 清除旧命令
        try:
            await self.delete_bot_commands()
        except Exception as e:
            logger.error(f"清除旧命令失败: {e}")

        # 归类新命令
        for cmd in self._registered_commands:
            if not cmd["func"].__module__.startswith("plugins.bot"):
                continue
                
            bot_cmd = BotCommand(cmd["command"], cmd["description"])
            for scope in cmd["scopes"]:
                scopes_dict[scope].append(bot_cmd)
        
        # 按 Scope 设置命令
        logger.info("正在同步机器人命令菜单...")
        for scope, commands in scopes_dict.items():
            if not commands:
                continue
            try:
                logger.info(f"设置命令菜单: Scope={scope.name}, Count={len(commands)}")
                await self.set_bot_commands(commands, scope=scope.value)
            except Exception as e:
                logger.error(f"设置命令菜单失败 (Scope={scope.name}): {e}")

    async def _ask_interceptor(self, client, message: Message):
        """
        拦截器：检查消息是否是某个 ask 的回复
        """
        from .logger import logger
        logger.debug(f"[{self.name}] 收到消息: {message.text or '[媒体]'} (来自: {message.from_user.id if message.from_user else '未知'})")
        
        chat_id = message.chat.id
        if chat_id in self._pending_asks:
            future = self._pending_asks[chat_id]
            if not future.done():
                future.set_result(message)
                message.stop_propagation()

    async def ask(self, chat_id, text, timeout=300):
        """
        发送消息并等待回复
        """
        await self.send_message(chat_id, text)
        
        # 创建一个 Future 用于等待回复
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_asks[chat_id] = future
        
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("等待回复超时")
        finally:
            self._pending_asks.pop(chat_id, None)

# 导出常用组件
__all__ = ["Client", "filters", "enums", "idle", "Message", "CallbackQuery", "InlineQuery"]
