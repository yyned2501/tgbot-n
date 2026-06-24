import os
import importlib
import json
import inspect
from typing import Dict, List, Optional, Set
from .client import Client
from . import config
from .logger import logger
from .database import get_setting, set_setting

class AppManager:
    def __init__(self):
        self.user: Optional[Client] = None
        self.bot: Optional[Client] = None
        self._owner_id: int = 0
        self._prefix: str = "."
        self._session_string: str = ""
        self._disabled_modules: Set[str] = set()

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def session_string(self) -> str:
        return self._session_string

    @property
    def disabled_modules(self) -> Set[str]:
        return self._disabled_modules

    async def load_settings(self):
        """
        从数据库加载动态配置
        """
        self._owner_id = int(await get_setting("owner_id", "0"))
        self._prefix = await get_setting("prefix", ".")
        self._session_string = await get_setting("session_string", "")
        
        # 加载禁用模块列表
        disabled_json = await get_setting("disabled_modules", "[]")
        try:
            self._disabled_modules = set(json.loads(disabled_json))
        except Exception:
            self._disabled_modules = set()
        
        # 同步更新 core.app.PREFIX 变量
        import core
        core.app.PREFIX = self._prefix
        
        logger.info(f"配置已加载: Owner={self._owner_id}, Prefix='{self._prefix}', DisabledModules={len(self._disabled_modules)}")

    async def set_owner_id(self, owner_id: int):
        self._owner_id = owner_id
        await set_setting("owner_id", str(owner_id))
        logger.info(f"Owner ID 已更新为: {owner_id}")

    async def set_prefix(self, prefix: str):
        self._prefix = prefix
        await set_setting("prefix", prefix)
        logger.info(f"指令前缀已更新为: {prefix}")
        # 同步更新 core 模块中的 app.PREFIX 变量（如果存在）
        import core
        core.app.PREFIX = prefix

    async def set_session_string(self, session_string: str):
        self._session_string = session_string
        await set_setting("session_string", session_string)
        logger.info("Session String 已更新并保存至数据库")

    async def toggle_module(self, module_name: str) -> bool:
        """
        切换模块启用状态
        返回: True 表示已启用, False 表示已禁用
        """
        if module_name in self._disabled_modules:
            self._disabled_modules.remove(module_name)
            enabled = True
        else:
            self._disabled_modules.add(module_name)
            enabled = False
        
        await set_setting("disabled_modules", json.dumps(list(self._disabled_modules)))
        logger.info(f"模块 {module_name} 已{'启用' if enabled else '禁用'}")
        return enabled

    def is_module_enabled(self, module_name: str) -> bool:
        """
        检查模块是否启用
        """
        return module_name not in self._disabled_modules

    async def enable_all_in_path(self, modules: List[str]):
        """
        批量启用模块
        """
        for mod in modules:
            if mod in self._disabled_modules:
                self._disabled_modules.remove(mod)
        await set_setting("disabled_modules", json.dumps(list(self._disabled_modules)))
        logger.info(f"已批量启用 {len(modules)} 个模块")

    async def disable_all_in_path(self, modules: List[str]):
        """
        批量禁用模块
        """
        for mod in modules:
            self._disabled_modules.add(mod)
        await set_setting("disabled_modules", json.dumps(list(self._disabled_modules)))
        logger.info(f"已批量禁用 {len(modules)} 个模块")

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

    def load_plugins(self):
        """
        手动导入所有插件模块，以触发装饰器并注册数据库模型
        """
        logger.info("正在预加载所有插件模块...")
        # 1. 加载 Bot 插件
        self._load_plugin_modules("plugins/bot", prefix="bot")
        
        # 2. 加载 User 插件
        self._load_plugin_modules("plugins/user", prefix="user")
        
        # 3. 加载 plugins 根目录下的插件
        count = 0
        for f in os.listdir("plugins"):
            if f.endswith(".py") and f != "__init__.py":
                try:
                    module_name = f"plugins.{f.replace('.py', '')}"
                    importlib.import_module(module_name)
                    logger.debug(f"手动加载根目录插件模块: {module_name}")
                    count += 1
                except Exception as e:
                    logger.error(f"无法导入根目录插件 {f}: {e}")
        logger.info(f"插件模块预加载完成。根目录插件数量: {count}")

    def get_user_plugin_info(self) -> List[dict]:
        """
        获取 Userbot 插件的详细信息 (指令, 说明, 状态)
        """
        modules = self._get_plugin_modules("plugins/user", prefix="user")
        info_list = []
        for mod_name in modules:
            full_mod_name = f"plugins.{mod_name}"
            try:
                # 模块应该已经被 pre-load 了，所以 importlib.import_module 很快
                module = importlib.import_module(full_mod_name)
                
                # 尝试获取模块文档字符串作为说明
                doc = module.__doc__.strip() if module.__doc__ else ""
                
                # 如果模块没有文档，尝试找第一个函数的文档
                if not doc:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (callable(attr) 
                            and not attr_name.startswith("_") 
                            and attr.__doc__ 
                            and inspect.getmodule(attr) == module):
                            doc = attr.__doc__.strip()
                            break
                
                if not doc:
                    doc = "无说明"
                
                # 指令名默认为文件名
                cmd_name = mod_name.split(".")[-1]
                
                info_list.append({
                    "module": full_mod_name,
                    "name": cmd_name,
                    "description": doc.split('\n')[0], # 只取第一行
                    "enabled": self.is_module_enabled(full_mod_name)
                })
            except Exception as e:
                logger.error(f"获取插件信息失败 {full_mod_name}: {e}")
        return info_list

    def init_apps(self):
        """
        初始化 Client 实例
        """
        # 1. 初始化 Userbot
        if self.session_string:
            user_plugin_modules = self._get_plugin_modules("plugins/user", prefix="user")
            # 同时也加载 plugins/ 根目录下的插件
            for f in os.listdir("plugins"):
                if f.endswith(".py") and f != "__init__.py":
                    user_plugin_modules.append(f.replace(".py", ""))
            
            logger.info(f"初始化 Userbot，加载插件: {user_plugin_modules}")
            self.user = Client(
                "my_userbot",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=self.session_string,
                plugins=dict(root="plugins", include=user_plugin_modules) if user_plugin_modules else None
            )

        # 2. 初始化 Assistant Bot
        if config.BOT_TOKEN:
            bot_plugin_modules = self._get_plugin_modules("plugins/bot", prefix="bot")
            logger.info(f"初始化 Bot，加载插件: {bot_plugin_modules}")
            self.bot = Client(
                "my_assistant_bot",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                bot_token=config.BOT_TOKEN,
                plugins=dict(root="plugins", include=bot_plugin_modules) if bot_plugin_modules else None
            )

    def _init_userbot(self, session_string: str):
        """
        内部方法：用于动态启动时的初始化
        """
        user_plugin_modules = self._get_plugin_modules("plugins/user", prefix="user")
        for f in os.listdir("plugins"):
            if f.endswith(".py") and f != "__init__.py":
                user_plugin_modules.append(f.replace(".py", ""))
        
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
        await self.set_session_string(session_string)
        self._init_userbot(session_string)
        
        logger.info("正在动态启动 Userbot...")
        await self.user.start()
        
        # 获取并更新 Owner ID
        me = await self.user.get_me()
        await self.set_owner_id(me.id)
        logger.info(f"Userbot 已启动，Owner ID: {me.id}")
        
        return True

    async def logout(self):
        """
        退出登录：停止 Userbot 并清除 Session
        """
        if self.user:
            logger.info("正在停止 Userbot 并退出登录...")
            try:
                await self.user.stop()
            except Exception as e:
                logger.error(f"停止 Userbot 失败: {e}")
            self.user = None
        
        await self.set_session_string("")
        self._owner_id = 0
        await set_setting("owner_id", "0")
        logger.info("已成功退出登录并清除 Session 数据")

    async def start_all(self):
        if self.bot:
            logger.info("正在启动 Assistant Bot...")
            try:
                await self.bot.start()
            except Exception as e:
                if "database is locked" in str(e):
                    logger.warning(f"Bot 会话文件被锁定，尝试清理后重试: {e}")
                    import os as _os
                    session_path = self.bot.name + ".session"
                    for f in [session_path, session_path + "-journal", session_path + "-wal"]:
                        if _os.path.exists(f):
                            _os.remove(f)
                    logger.info("已清理 Bot 会话文件，重新启动...")
                    await self.bot.start()
                else:
                    raise
            # 同步机器人命令菜单
            await self.bot.sync_bot_commands()

        if self.user:
            logger.info("正在启动 Userbot...")
            await self.user.start()
            # 获取并更新 Owner ID
            me = await self.user.get_me()
            if self.owner_id != me.id:
                await self.set_owner_id(me.id)
            logger.info(f"Userbot 已启动，Owner ID: {me.id}")

    async def stop_all(self):
        if self.user:
            await self.user.stop()
        if self.bot:
            await self.bot.stop()

    async def restart(self):
        """
        重启脚本
        """
        import sys
        import os
        
        logger.info("程序正在重启...")
        
        # 1. 尝试优雅停止 Userbot (如果正在运行)
        if self.user:
            try:
                await self.user.stop()
            except Exception as e:
                logger.error(f"停止 Userbot 失败: {e}")
        
        # 2. 预留一点时间让日志输出
        import asyncio
        await asyncio.sleep(1)
        
        # 3. 重启进程
        # 注意：不要停止 self.bot，因为我们通常在 bot 的回调中执行此操作
        # os.execl 会在 Windows 上启动新进程并退出当前进程，操作系统会回收资源
        os.execl(sys.executable, sys.executable, *sys.argv)

    async def send_bot_message(self, text: str):
        """
        使用 Assistant Bot 向 Owner 发送消息
        """
        if not self.bot or not self.bot.is_connected:
            logger.warning("Bot 未启动，无法发送消息")
            return
            
        if not self.owner_id:
            logger.warning("Owner ID 未设置，无法发送消息")
            return

        try:
            await self.bot.send_message(self.owner_id, text)
        except Exception as e:
            logger.error(f"Bot 发送消息失败: {e}")

# 全局单例
manager = AppManager()
