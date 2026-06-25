"""
应用管理器 (AppManager)

负责管理 Assistant Bot 和全局配置。
Userbot 账号的生命周期管理已委托给 UserAccountManager。
"""
import os
import importlib
import json
import inspect
from typing import Dict, List, Optional, Set
from .client import Client
from . import config
from .logger import logger
from .database import get_setting, set_setting
from .account_manager import account_manager


class AppManager:
    """
    应用管理器

    职责:
    - 管理 Assistant Bot 实例
    - 管理全局配置 (prefix, owner_id)
    - 加载/卸载插件
    - 提供向后兼容的接口 (委托给 account_manager)
    """

    def __init__(self):
        self.bot: Optional[Client] = None
        self._owner_id: int = 0
        self._prefix: str = "."
        # 兼容旧版引用: self.user -> account_manager 的第一个账号
        self._legacy_user: Optional[Client] = None

    @property
    def user(self) -> Optional[Client]:
        """
        兼容旧版属性：返回第一个可用的 Userbot Client
        如果只有一个账号，直接返回；如果有多个，返回第一个
        """
        if self._legacy_user and self._legacy_user.is_connected:
            return self._legacy_user
        accounts = account_manager.get_all_accounts()
        if accounts:
            first = list(accounts.values())[0]
            self._legacy_user = first
            return first
        return None

    @user.setter
    def user(self, value: Optional[Client]):
        self._legacy_user = value

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @owner_id.setter
    def owner_id(self, value: int):
        self._owner_id = value

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def session_string(self) -> str:
        """
        兼容旧版属性：返回第一个账号的 session_string
        """
        accounts = account_manager.get_all_accounts()
        if accounts:
            first_oid = list(accounts.keys())[0]
            record = None
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # 异步上下文中无法直接 await，返回空
                    return ""
            except RuntimeError:
                pass
        return ""

    @property
    def disabled_modules(self) -> Set[str]:
        """
        兼容旧版属性：返回空集
        新版使用 account_manager 按账号隔离
        """
        return set()

    # ==================== 配置加载 ====================

    async def load_settings(self):
        """
        从数据库加载动态配置
        """
        self._owner_id = int(await get_setting("owner_id", "0"))
        self._prefix = await get_setting("prefix", ".")

        # 同步更新 core.app.PREFIX 变量
        import core
        core.app.PREFIX = self._prefix

        logger.info(
            f"配置已加载: Owner={self._owner_id}, "
            f"Prefix='{self._prefix}'"
        )

    async def set_owner_id(self, owner_id: int):
        self._owner_id = owner_id
        await set_setting("owner_id", str(owner_id))
        logger.info(f"Owner ID 已更新为: {owner_id}")

    async def set_prefix(self, prefix: str):
        self._prefix = prefix
        await set_setting("prefix", prefix)
        logger.info(f"指令前缀已更新为: {prefix}")
        # 同步更新 core 模块中的 app.PREFIX 变量
        import core
        core.app.PREFIX = prefix

    # ==================== 模块管理 (委托给 account_manager) ====================

    async def toggle_module(self, module_name: str) -> bool:
        """
        切换模块启用状态 (兼容旧版，使用 owner_id)
        如果只有一个账号，操作该账号的模块
        """
        accounts = account_manager.get_all_accounts()
        if not accounts:
            logger.warning("没有运行的 Userbot 账号，无法切换模块")
            return False
        # 对第一个账号操作
        first_oid = list(accounts.keys())[0]
        return await account_manager.toggle_module(first_oid, module_name)

    def is_module_enabled(self, module_name: str) -> bool:
        """
        检查模块是否启用 (同步方法，兼容旧版)
        注意：新版建议使用 account_manager.is_module_enabled(owner_id, module_name)
        """
        # 由于是同步方法，无法 await，直接返回 True
        # 实际过滤逻辑在 add_handler 中处理
        return True

    async def enable_all_in_path(self, modules: List[str]):
        """批量启用模块 (兼容旧版，对第一个账号操作)"""
        accounts = account_manager.get_all_accounts()
        if accounts:
            first_oid = list(accounts.keys())[0]
            await account_manager.enable_all_in_path(first_oid, modules)

    async def disable_all_in_path(self, modules: List[str]):
        """批量禁用模块 (兼容旧版，对第一个账号操作)"""
        accounts = account_manager.get_all_accounts()
        if accounts:
            first_oid = list(accounts.keys())[0]
            await account_manager.disable_all_in_path(first_oid, modules)

    # ==================== 插件加载 ====================

    def _load_plugin_modules(self, root_dir: str, prefix: str = ""):
        """
        手动导入插件模块以触发装饰器
        """
        modules = self._get_plugin_modules(root_dir, prefix=prefix)
        for module in modules:
            try:
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
                    relative_path = os.path.relpath(
                        os.path.join(root, file), root_dir
                    )
                    module_name = relative_path.replace(os.sep, ".").replace(
                        ".py", ""
                    )
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
                module = importlib.import_module(full_mod_name)

                doc = module.__doc__.strip() if module.__doc__ else ""

                if not doc:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            callable(attr)
                            and not attr_name.startswith("_")
                            and attr.__doc__
                            and inspect.getmodule(attr) == module
                        ):
                            doc = attr.__doc__.strip()
                            break

                if not doc:
                    doc = "无说明"

                cmd_name = mod_name.split(".")[-1]

                info_list.append(
                    {
                        "module": full_mod_name,
                        "name": cmd_name,
                        "description": doc.split("\n")[0],
                        "enabled": True,  # 兼容旧版
                    }
                )
            except Exception as e:
                logger.error(f"获取插件信息失败 {full_mod_name}: {e}")
        return info_list

    # ==================== Client 初始化 ====================

    def init_apps(self):
        """
        初始化 Client 实例

        注意：Userbot 的初始化现在由 account_manager 在 start_all 中完成
        此方法只初始化 Assistant Bot
        """
        # 初始化 Assistant Bot
        if config.BOT_TOKEN:
            bot_plugin_modules = self._get_plugin_modules(
                "plugins/bot", prefix="bot"
            )
            logger.info(f"初始化 Bot，加载插件: {bot_plugin_modules}")
            self.bot = Client(
                "my_assistant_bot",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                bot_token=config.BOT_TOKEN,
                plugins=dict(root="plugins", include=bot_plugin_modules)
                if bot_plugin_modules
                else None,
            )

    def _init_userbot(self, session_string: str):
        """
        内部方法：兼容旧版动态启动
        实际委托给 account_manager
        """
        # 此方法保留用于兼容，但实际不再使用
        logger.warning("_init_userbot 已弃用，请使用 account_manager.start_account()")
        pass

    # ==================== 启动/停止 ====================

    async def start_userbot(self, session_string: str):
        """
        动态启动 Userbot (兼容旧版)
        实际委托给 account_manager
        """
        # 从 session_string 启动，但不知道 owner_id
        # 此方法保留用于兼容旧版 login 流程
        logger.warning(
            "start_userbot(session_string) 已弃用，"
            "请使用 account_manager.add_account(owner_id, session_string, phone)"
        )
        return False

    async def logout(self):
        """
        退出登录：停止所有 Userbot 并清除 Session (兼容旧版)
        """
        await account_manager.stop_all()
        self._owner_id = 0
        await set_setting("owner_id", "0")
        logger.info("已退出登录并清除 Owner 数据")

    async def start_all(self):
        """
        启动所有服务：
        1. 启动 Assistant Bot
        2. 启动所有 Userbot 账号
        """
        # 1. 启动 Bot
        if self.bot:
            logger.info("正在启动 Assistant Bot...")
            try:
                await self.bot.start()
            except Exception as e:
                if "database is locked" in str(e):
                    logger.warning(
                        f"Bot 会话文件被锁定，尝试清理后重试: {e}"
                    )
                    session_path = self.bot.name + ".session"
                    for f in [
                        session_path,
                        session_path + "-journal",
                        session_path + "-wal",
                    ]:
                        if os.path.exists(f):
                            os.remove(f)
                    logger.info("已清理 Bot 会话文件，重新启动...")
                    await self.bot.start()
                else:
                    raise
            # 同步机器人命令菜单
            await self.bot.sync_bot_commands()

        # 2. 启动所有 Userbot 账号
        await account_manager.start_all()

    async def stop_all(self):
        """停止所有服务"""
        # 停止所有 Userbot
        await account_manager.stop_all()
        # 停止 Bot
        if self.bot:
            await self.bot.stop()

    async def restart(self):
        """
        重启脚本
        """
        import sys

        logger.info("程序正在重启...")

        # 1. 停止所有 Userbot
        await account_manager.stop_all()

        # 2. 预留一点时间让日志输出
        import asyncio
        await asyncio.sleep(1)

        # 3. 重启进程
        os.execl(sys.executable, sys.executable, *sys.argv)

    # ==================== 消息发送 ====================

    async def send_bot_message(self, text: str, target_id: int = 0):
        """
        使用 Assistant Bot 向指定用户发送消息

        Args:
            text: 消息文本
            target_id: 目标用户 ID，为 0 时发送给 Bot Owner（向后兼容）
        """
        if not self.bot or not self.bot.is_connected:
            logger.warning("Bot 未启动，无法发送消息")
            return

        recipient = target_id if target_id else self.owner_id
        if not recipient:
            logger.warning("Owner ID 未设置且未指定 target_id，无法发送消息")
            return

        logger.info(f"[send_bot_message] target_id={target_id} -> recipient={recipient}")
        try:
            await self.bot.send_message(recipient, text)
        except Exception as e:
            logger.error(f"Bot 发送消息给 {recipient} 失败: {e}")


# 全局单例
manager = AppManager()
