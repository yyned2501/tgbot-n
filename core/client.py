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

    def __init__(self, name: str, owner_id: int = 0, **kwargs):
        # 代理自动加载逻辑
        if "proxy" not in kwargs and PROXY.get("enabled"):
            kwargs["proxy"] = {
                "scheme": PROXY.get("scheme", "socks5"),
                "hostname": PROXY.get("hostname", "127.0.0.1"),
                "port": PROXY.get("port", 7890),
                "username": PROXY.get("username"),
                "password": PROXY.get("password")
            }
        # owner_id 必须在 super().__init__ 之前设置，
        # 因为 Pyrogram 在 __init__ 期间就会通过 add_handler 注册插件 handler，
        # add_handler 依赖 _owner_id 来判断当前实例是 Bot 还是 Userbot
        if owner_id:
            self._owner_id = owner_id
        # _prefix 缓存当前 userbot 的指令前缀（默认 "."，启动后由 account_manager 覆写）
        self._prefix = "."
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
        重写 add_handler，实现：
        1. Bot/Userbot 模块隔离：Bot 不加载 User 插件，Userbot 不加载 Bot 插件
        2. Userbot 模块级开关拦截
        """
        from .account_manager import account_manager
        from .logger import logger

        original_callback = handler.callback
        module_name = getattr(original_callback, "__module__", "")

        is_userbot = hasattr(self, "_owner_id")
        identity = f"Userbot({self._owner_id})" if is_userbot else "Bot"

        # 1. 模块隔离：Bot 只处理 plugins.bot，Userbot 只处理 plugins.user
        if module_name.startswith("plugins."):
            if not is_userbot and module_name.startswith("plugins.user"):
                return  # Bot 不注册 User 插件的 handler
            if is_userbot and module_name.startswith("plugins.bot"):
                return  # Userbot 不注册 Bot 插件的 handler

        # 2. Userbot 模块级开关拦截
        if is_userbot and module_name.startswith("plugins.user"):
            owner_id = self._owner_id
            async def wrapped_callback(client, message, *args, **kwargs):
                try:
                    if not await account_manager.is_module_enabled(owner_id, module_name):
                        logger.debug(f"[Userbot({owner_id})] 模块 {module_name} 已禁用，跳过")
                        return
                except Exception as e:
                    logger.warning(f"[Userbot({owner_id})] 模块检查失败 ({module_name}): {e}，放行")
                return await original_callback(client, message, *args, **kwargs)

            handler.callback = wrapped_callback
            logger.info(f"[{identity}] 注册 User 插件 handler: {module_name}")

        super().add_handler(handler, group)

    def _register_custom_commands(self):
        """
        注册通过 @bot_command 装饰的命令处理器
        """
        from .logger import logger
        is_userbot = hasattr(self, "_owner_id")
        identity = f"Userbot({self._owner_id})" if is_userbot else "Bot"
        
        for cmd in self._registered_commands:
            # 根据插件目录过滤，避免 Bot 加载 User 插件的命令，反之亦然
            module_name = cmd["func"].__module__
            command = cmd["command"]
            
            if not is_userbot and not module_name.startswith("plugins.bot"):
                logger.debug(f"[{identity}] 跳过非 Bot 命令 /{command} (模块: {module_name})")
                continue
            if is_userbot and not module_name.startswith("plugins.user"):
                logger.debug(f"[{identity}] 跳过非 User 命令 /{command} (模块: {module_name})")
                continue

            from pyrogram.handlers import MessageHandler
            from pyrogram import filters
            
            cmd_filter = filters.command(cmd["command"])
            if cmd["filters"]:
                cmd_filter &= cmd["filters"]
            
            logger.debug(f"[{identity}] 注册命令 /{command} (模块: {module_name})")
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
        is_userbot = hasattr(self, "_owner_id")
        identity = f"Userbot({self._owner_id})" if is_userbot else "Bot"
        
        # 记录所有收到的消息，用于诊断 Userbot 是否错误地处理了 Bot 命令
        msg_text = message.text or '[媒体/非文本]'
        from_id = message.from_user.id if message.from_user else '未知'
        chat_id = message.chat.id
        logger.debug(f"[{identity}] _ask_interceptor 收到消息: '{msg_text}' (来自: {from_id}, 聊天: {chat_id})")
        
        if chat_id in self._pending_asks:
            future = self._pending_asks[chat_id]
            if not future.done():
                logger.debug(f"[{identity}] 消息匹配等待中的 ask，设置结果并停止传播")
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
