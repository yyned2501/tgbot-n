"""
多账号管理器 (UserAccountManager)

负责管理多个 Userbot 账号的生命周期：
- 从数据库加载/保存账号
- 启动/停止单个账号
- 批量启动/停止所有账号
- 提供账号信息查询接口
"""
import os
import json
import asyncio
import importlib
from typing import Dict, List, Optional, Set
from .client import Client
from . import config
from .logger import logger
from .database import get_setting, set_setting, delete_setting, async_session
from .models import UserAccount
from sqlalchemy import select


class UserAccountManager:
    """
    多账号管理器
    维护 owner_id -> Client 的映射关系
    """

    def __init__(self):
        # owner_id -> Client 实例
        self._accounts: Dict[int, Client] = {}
        # 全局禁用模块列表 (对所有账号生效)
        self._disabled_modules: Set[str] = set()
        # 全局指令前缀
        self._prefix: str = "."

    @property
    def accounts(self) -> Dict[int, Client]:
        """获取所有账号映射 (owner_id -> Client)"""
        return self._accounts

    @property
    def account_count(self) -> int:
        """当前在线账号数量"""
        return len(self._accounts)

    @property
    def disabled_modules(self) -> Set[str]:
        return self._disabled_modules

    @property
    def prefix(self) -> str:
        return self._prefix

    # ==================== 数据库操作 ====================

    async def load_all_accounts_from_db(self) -> List[UserAccount]:
        """
        从数据库加载所有启用的账号记录
        返回 UserAccount 对象列表
        """
        async with async_session() as session:
            result = await session.execute(
                select(UserAccount).where(UserAccount.is_active == True)
            )
            return list(result.scalars().all())

    async def get_account_record(self, owner_id: int) -> Optional[UserAccount]:
        """根据 owner_id 获取数据库中的账号记录"""
        async with async_session() as session:
            result = await session.execute(
                select(UserAccount).where(UserAccount.owner_id == owner_id)
            )
            return result.scalar_one_or_none()

    async def save_account_record(self, account: UserAccount):
        """保存或更新账号记录到数据库"""
        async with async_session() as session:
            async with session.begin():
                session.add(account)

    async def delete_account_record(self, owner_id: int):
        """从数据库删除账号记录"""
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserAccount).where(UserAccount.owner_id == owner_id)
                )
                account = result.scalar_one_or_none()
                if account:
                    await session.delete(account)

    # ==================== 模块开关 (按账号隔离) ====================

    async def load_disabled_modules(self, owner_id: int) -> Set[str]:
        """加载指定账号的禁用模块列表"""
        key = f"disabled_modules:{owner_id}"
        raw = await get_setting(key, "[]")
        try:
            return set(json.loads(raw))
        except Exception:
            return set()

    async def save_disabled_modules(self, owner_id: int, modules: Set[str]):
        """保存指定账号的禁用模块列表"""
        key = f"disabled_modules:{owner_id}"
        await set_setting(key, json.dumps(list(modules)))

    async def toggle_module(self, owner_id: int, module_name: str) -> bool:
        """
        切换指定账号的模块启用状态
        返回: True 表示已启用, False 表示已禁用
        """
        disabled = await self.load_disabled_modules(owner_id)
        if module_name in disabled:
            disabled.remove(module_name)
            enabled = True
        else:
            disabled.add(module_name)
            enabled = False
        await self.save_disabled_modules(owner_id, disabled)
        logger.info(f"[{owner_id}] 模块 {module_name} 已{'启用' if enabled else '禁用'}")
        return enabled

    async def is_module_enabled(self, owner_id: int, module_name: str) -> bool:
        """检查指定账号的模块是否启用"""
        disabled = await self.load_disabled_modules(owner_id)
        return module_name not in disabled

    async def enable_all_in_path(self, owner_id: int, modules: List[str]):
        """批量启用指定账号的模块"""
        disabled = await self.load_disabled_modules(owner_id)
        for mod in modules:
            if mod in disabled:
                disabled.remove(mod)
        await self.save_disabled_modules(owner_id, disabled)
        logger.info(f"[{owner_id}] 已批量启用 {len(modules)} 个模块")

    async def disable_all_in_path(self, owner_id: int, modules: List[str]):
        """批量禁用指定账号的模块"""
        disabled = await self.load_disabled_modules(owner_id)
        for mod in modules:
            disabled.add(mod)
        await self.save_disabled_modules(owner_id, disabled)
        logger.info(f"[{owner_id}] 已批量禁用 {len(modules)} 个模块")

    # ==================== 指令前缀 (按账号隔离) ====================

    async def load_prefix(self, owner_id: int) -> str:
        """加载指定账号的指令前缀，未设置时回退到全局前缀"""
        key = f"prefix:{owner_id}"
        raw = await get_setting(key, "")
        if raw:
            return raw
        # 回退到全局前缀
        from . import app
        return app.manager.prefix

    async def save_prefix(self, owner_id: int, prefix: str):
        """保存指定账号的指令前缀"""
        key = f"prefix:{owner_id}"
        await set_setting(key, prefix)
        logger.info(f"[{owner_id}] 指令前缀已更新为: {prefix}")

    # ==================== 账号生命周期管理 ====================

    def _get_user_plugin_modules(self) -> List[str]:
        """
        获取所有 User 插件模块列表
        """
        modules = []
        root_dir = "plugins/user"
        if os.path.exists(root_dir):
            for root, _, files in os.walk(root_dir):
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":
                        relative_path = os.path.relpath(
                            os.path.join(root, file), root_dir
                        )
                        module_name = relative_path.replace(os.sep, ".").replace(
                            ".py", ""
                        )
                        modules.append(f"user.{module_name}")

        # 同时加载 plugins/ 根目录下的插件
        if os.path.exists("plugins"):
            for f in os.listdir("plugins"):
                if f.endswith(".py") and f != "__init__.py":
                    modules.append(f.replace(".py", ""))
        return modules

    def _init_single_userbot(
        self, owner_id: int, session_string: str, phone: str
    ) -> Client:
        """
        初始化单个 Userbot Client 实例
        使用 phone 作为 Client 名称，便于区分
        """
        user_plugin_modules = self._get_user_plugin_modules()

        # 使用 phone 作为 Client 名称（如果 phone 是 "migrated" 则用 owner_id）
        client_name = phone if phone and phone != "migrated" else f"user_{owner_id}"

        logger.info(
            f"[{owner_id}] 初始化 Userbot (name={client_name}), "
            f"加载插件: {user_plugin_modules}"
        )

        client = Client(
            client_name,
            owner_id=owner_id,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=session_string,
            plugins=dict(root="plugins", include=user_plugin_modules)
            if user_plugin_modules
            else None,
        )
        return client

    async def start_account(
        self, owner_id: int, session_string: str, phone: str
    ) -> bool:
        """
        启动指定账号的 Userbot
        返回是否成功
        """
        if owner_id in self._accounts:
            logger.info(f"[{owner_id}] 账号已在运行，跳过")
            return True

        try:
            client = self._init_single_userbot(owner_id, session_string, phone)
            logger.info(f"[{owner_id}] 正在启动 Userbot...")
            await client.start()

            # 验证身份：确保登录的账号与 owner_id 一致
            me = await client.get_me()
            if me.id != owner_id:
                logger.error(
                    f"[{owner_id}] 身份验证失败！登录的账号 ID ({me.id}) "
                    f"与绑定的 owner_id ({owner_id}) 不匹配，立即登出"
                )
                await client.stop()
                return False

            self._accounts[owner_id] = client

            # 加载该用户的前缀并缓存到 Client 实例
            prefix = await self.load_prefix(owner_id)
            client._prefix = prefix

            logger.info(f"[{owner_id}] Userbot 已启动 (phone={phone}, username={me.username or 'N/A'}, prefix='{prefix}')")

            # 通知该用户自己的 Userbot 已启动
            from . import app
            try:
                await app.manager.send_bot_message(
                    f"🚀 **您的 Userbot 已启动就绪！**\n\n"
                    f"👤 账号: `{owner_id}`\n"
                    f"⌨️ 指令前缀: `{prefix}`",
                    target_id=owner_id,
                )
            except Exception:
                pass

            return True

        except Exception as e:
            logger.error(f"[{owner_id}] 启动 Userbot 失败: {e}")
            return False

    async def stop_account(self, owner_id: int):
        """停止指定账号的 Userbot"""
        client = self._accounts.pop(owner_id, None)
        if client:
            try:
                await client.stop()
                logger.info(f"[{owner_id}] Userbot 已停止")
            except Exception as e:
                logger.error(f"[{owner_id}] 停止 Userbot 失败: {e}")

    async def start_all(self):
        """
        从数据库加载所有启用的账号并启动
        """
        records = await self.load_all_accounts_from_db()
        if not records:
            logger.info("数据库中没有启用的 Userbot 账号")
            return

        logger.info(f"正在启动 {len(records)} 个 Userbot 账号...")
        success_count = 0
        for record in records:
            ok = await self.start_account(
                record.owner_id, record.session_string, record.phone
            )
            if ok:
                success_count += 1

        logger.info(f"Userbot 账号启动完成: 成功 {success_count}/{len(records)}")

    async def stop_all(self):
        """停止所有正在运行的 Userbot"""
        owner_ids = list(self._accounts.keys())
        for owner_id in owner_ids:
            await self.stop_account(owner_id)
        logger.info("所有 Userbot 账号已停止")

    async def add_account(
        self, owner_id: int, session_string: str, phone: str
    ) -> bool:
        """
        添加新账号并保存到数据库
        1. 保存到数据库
        2. 启动 Userbot
        3. 返回是否成功
        """
        # 先检查是否已存在
        existing = await self.get_account_record(owner_id)
        if existing:
            logger.warning(f"[{owner_id}] 账号已存在，更新 session_string")
            existing.session_string = session_string
            existing.phone = phone
            existing.is_active = True
            await self.save_account_record(existing)
        else:
            account = UserAccount(
                owner_id=owner_id,
                phone=phone,
                session_string=session_string,
                is_active=True,
                is_connected=False,
            )
            await self.save_account_record(account)

        # 启动 Userbot
        return await self.start_account(owner_id, session_string, phone)

    async def remove_account(self, owner_id: int):
        """
        移除账号：停止运行并从数据库删除
        """
        await self.stop_account(owner_id)
        await self.delete_account_record(owner_id)
        logger.info(f"[{owner_id}] 账号已从数据库删除")

    async def restart_account(self, owner_id: int) -> bool:
        """
        重启指定账号的 Userbot
        从数据库取回 session_string / phone，先停后启
        """
        record = await self.get_account_record(owner_id)
        if not record:
            logger.error(f"[{owner_id}] 无法重启：数据库中无此账号记录")
            return False

        logger.info(f"[{owner_id}] 正在重启 Userbot...")
        await self.stop_account(owner_id)
        await asyncio.sleep(1)

        success = await self.start_account(
            owner_id, record.session_string, record.phone
        )
        if success:
            logger.info(f"[{owner_id}] Userbot 已重启")
        else:
            logger.error(f"[{owner_id}] Userbot 重启失败")
        return success

    # ==================== 查询接口 ====================

    def get_account(self, owner_id: int) -> Optional[Client]:
        """获取指定 owner_id 的 Client 实例"""
        return self._accounts.get(owner_id)

    def get_all_accounts(self) -> Dict[int, Client]:
        """获取所有运行中的 Client 实例"""
        return dict(self._accounts)

    async def get_accounts_info(self, owner_id: Optional[int] = None) -> List[dict]:
        """
        获取账号信息列表

        参数:
            owner_id: 如果提供，只返回该用户的账号信息
                      如果为 None (Bot Owner)，返回所有账号信息
        """
        if owner_id is not None:
            # 普通用户：只返回自己的账号
            client = self._accounts.get(owner_id)
            if client:
                me = await client.get_me()
                # Userbot 的 get_me() 返回的 User 对象没有 phone 属性
                phone = getattr(me, "phone", None) or "N/A"
                return [
                    {
                        "owner_id": owner_id,
                        "phone": phone,
                        "username": me.username or "N/A",
                        "first_name": me.first_name or "",
                        # 账号在 _accounts 中即视为在线（已成功启动）
                        "is_connected": True,
                    }
                ]
            return []
        else:
            # Bot Owner：返回所有账号
            info_list = []
            for oid, client in self._accounts.items():
                try:
                    me = await client.get_me()
                    # Userbot 的 get_me() 返回的 User 对象没有 phone 属性
                    phone = getattr(me, "phone", None) or "N/A"
                    info_list.append(
                        {
                            "owner_id": oid,
                            "phone": phone,
                            "username": me.username or "N/A",
                            "first_name": me.first_name or "",
                            # 账号在 _accounts 中即视为在线（已成功启动）
                            # 不依赖 client.is_connected，因为 Pyrogram 底层连接可能短暂断开但会自动重连
                            "is_connected": True,
                        }
                    )
                except Exception:
                    # get_me 失败但账号仍在 _accounts 中，说明只是临时网络问题
                    info_list.append(
                        {
                            "owner_id": oid,
                            "phone": "N/A",
                            "username": "N/A",
                            "first_name": "在线",
                            "is_connected": True,
                        }
                    )
            return info_list


# 全局单例
account_manager = UserAccountManager()
