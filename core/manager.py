import os
import importlib
from typing import Dict, List, Optional
from .client import Client
from . import config
from .logger import logger

class AppManager:
    def __init__(self):
        self.user: Optional[Client] = None
        self.bot: Optional[Client] = None

    @property
    def owner_id(self) -> int:
        return config.OWNER_ID

    def _load_plugin_modules(self, root_dir: str, prefix: str = ""):
        """
        手动导入插件模块以触发装饰器
        """
        modules = self._get_plugin_modules(root_dir, prefix=prefix)
        for module in modules:
            try:
                # 模块名已经是 user.ping 或 bot.login 这种形式
                full_module_name = f"plugins.{module}"
                importlib.import_module(full_module_name)
                logger.debug(f"手动加载插件模块: {full_module_name}")
            except Exception as e:
                logger.error(f"无法导入插件 {module}: {e}")

    def _get_plugin_modules(self, root_dir: str, prefix: str = "") -> List[str]:
        """
        递归获取插件模块列表
        """
        if not os.path.exists(root_dir):
            return []
        
        modules = []
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    relative_path = os.path.relpath(os.path.join(root, file), root_dir)
                    module_name = relative_path.replace(os.sep, ".").replace(".py", "")
                    if prefix:
                        module_name = f"{prefix}.{module_name}"
                    modules.append(module_name)
        return modules

    def init_apps(self):
        # 1. 初始化 Userbot (人形脚本)
        if config.SESSION_STRING:
            self._init_userbot(config.SESSION_STRING)

        # 2. 初始化 Assistant Bot (辅助机器人)
        if config.BOT_TOKEN:
            # 提前加载插件以触发装饰器
            self._load_plugin_modules("plugins/bot", prefix="bot")
            
            # 获取 plugins/bot 下的插件，前缀设为 bot
            bot_plugin_modules = self._get_plugin_modules("plugins/bot", prefix="bot")
            logger.info(f"加载 Bot 插件: {bot_plugin_modules}")
            self.bot = Client(
                "my_assistant_bot",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                bot_token=config.BOT_TOKEN,
                plugins=dict(root="plugins", include=bot_plugin_modules) if bot_plugin_modules else None
            )

    def _init_userbot(self, session_string: str):
        # 提前加载插件以触发装饰器
        self._load_plugin_modules("plugins/user", prefix="user")
        
        # 获取 plugins/user 下的插件，前缀设为 user
        user_plugin_modules = self._get_plugin_modules("plugins/user", prefix="user")
        # 同时也加载 plugins/ 根目录下的插件（兼容旧结构，无前缀）
        for f in os.listdir("plugins"):
            if f.endswith(".py") and f != "__init__.py":
                user_plugin_modules.append(f.replace(".py", ""))
        
        logger.info(f"加载 Userbot 插件: {user_plugin_modules}")
        self.user = Client(
            "my_userbot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=session_string,
            plugins=dict(root="plugins", include=user_plugin_modules) if user_plugin_modules else None
        )

    async def start_userbot(self, session_string: str):
        """
        动态启动 Userbot
        """
        if self.user:
            logger.info("Userbot 已在运行，正在尝试重启...")
            await self.user.stop()
        
        # 更新配置并初始化
        config.update_session_string(session_string)
        self._init_userbot(session_string)
        
        logger.info("正在动态启动 Userbot...")
        await self.user.start()
        
        # 获取并更新 Owner ID
        me = await self.user.get_me()
        config.update_owner_id(me.id)
        logger.info(f"Userbot 已启动，Owner ID: {me.id}")
        
        return True

    async def start_all(self):
        if self.user:
            logger.info("正在启动 Userbot...")
            await self.user.start()
            # 获取并更新 Owner ID
            me = await self.user.get_me()
            config.update_owner_id(me.id)
            logger.info(f"Userbot 已启动，Owner ID: {me.id}")
            
        if self.bot:
            logger.info("正在启动 Assistant Bot...")
            await self.bot.start()
            # 同步机器人命令菜单
            await self.bot.sync_bot_commands()

    async def stop_all(self):
        if self.user:
            await self.user.stop()
        if self.bot:
            await self.bot.stop()

    async def send_bot_message(self, text: str):
        """
        使用 Assistant Bot 向 Owner 发送消息
        """
        if self.bot and self.owner_id:
            try:
                await self.bot.send_message(self.owner_id, text)
            except Exception as e:
                logger.error(f"Bot 发送消息失败: {e}")
        else:
            logger.warning("Bot 未启动或 Owner ID 未设置，无法发送消息")

# 全局单例
manager = AppManager()
