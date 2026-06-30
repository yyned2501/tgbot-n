"""
系统设置插件 - 支持多账号管理

功能:
- /settings - 系统设置菜单 (所有绑定用户可访问，非管理员看到自己的)
- /admin - 管理员面板 (仅 Bot Owner)
- /accounts - 账号管理菜单 (Bot Owner 看到所有，普通用户看到自己的)
- 插件管理 (按账号隔离)
- 退出登录 (单个账号)
"""
import os
import asyncio
from core import tg, db, app
from core.logger import logger


# ==================== 设置主菜单 ====================

@tg.Client.bot_command("settings", "个人设置")
async def settings_handler(client: tg.Client, message: tg.Message):
    """
    显示个人设置菜单 (所有绑定用户可访问)
    """
    tg.delete_later(message)

    user_id = message.from_user.id

    # 检查是否已绑定账号
    account = app.account_manager.get_account(user_id)
    if not account:
        await message.reply("📭 **您还没有绑定账号**\n\n请发送 /login 开始绑定。")
        return

    await send_settings_menu(message, user_id=user_id)


@tg.Client.bot_command("admin", "管理员面板")
async def admin_handler(client: tg.Client, message: tg.Message):
    """
    显示管理员面板 (仅 Bot Owner)
    """
    tg.delete_later(message)

    if message.from_user.id != app.manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    await send_admin_menu(message)


async def send_settings_menu(target: tg.Message, user_id: int = 0, edit: bool = False):
    """
    发送或编辑个人设置菜单（所有用户统一布局）
    """
    if not user_id:
        user_id = target.chat.id if hasattr(target, 'chat') else 0

    # 获取该用户的前缀
    account = app.account_manager.get_account(user_id)
    if account:
        prefix = getattr(account, "_prefix", "") or app.manager.prefix
    else:
        prefix = app.manager.prefix

    kb = tg.Keyboards()
    kb.add_buttons([
        tg.Keyboards.button(f"⌨️ 指令前缀: {prefix}", callback_data=f"sp:{user_id}"),
        tg.Keyboards.button("🔌 插件管理", callback_data=f"upl:{user_id}"),
        tg.Keyboards.button("📋 我的账号", callback_data=f"mac:{user_id}"),
        tg.Keyboards.button("🔄 重启人形", callback_data=f"rs:{user_id}"),
    ])
    kb.row().add_button("❌ 关闭菜单", callback_data="close_message")
    keyboard = kb.build()

    text = "⚙️ **个人设置**\n\n管理您的账号和偏好设置："

    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except tg.errors.MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"发送设置菜单失败: {e}")


async def send_admin_menu(target: tg.Message, edit: bool = False):
    """
    发送管理员面板（仅 Bot Owner 可访问）
    """
    account_count = app.account_manager.account_count

    kb = tg.Keyboards()
    kb.add_buttons([
        tg.Keyboards.button(f"👥 账号管理 ({account_count})", callback_data="accounts_list"),
        tg.Keyboards.button("🔄 重启脚本", callback_data="restart_confirm"),
    ])
    kb.row().add_button("❌ 关闭菜单", callback_data="close_message")
    keyboard = kb.build()

    text = (
        "🛡️ **管理员面板**\n\n"
        f"当前在线账号数: **{account_count}**\n"
        "管理所有账号和全局设置："
    )

    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except tg.errors.MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"发送管理员面板失败: {e}")


# ==================== 账号管理 ====================

@tg.Client.bot_command("accounts", "管理绑定的账号")
async def accounts_handler(client: tg.Client, message: tg.Message, user_id: int = None):
    """
    显示账号列表
    - Bot Owner: 看到所有账号
    - 普通用户: 看到自己的账号

    参数:
        user_id: 可选，显式指定用户 ID（用于从回调进入时传入真实用户 ID）
    """
    tg.delete_later(message)

    # 优先使用传入的 user_id，否则从消息中获取
    # 注意：从回调进入时，message 是 Bot 发送的消息，from_user 是 Bot 自身
    if user_id is None:
        user_id = message.from_user.id
    is_owner = user_id == app.manager.owner_id

    # 获取账号信息
    owner_id_param = None if is_owner else user_id
    accounts_info = await app.account_manager.get_accounts_info(owner_id_param)

    if not accounts_info:
        if is_owner:
            text = "📭 **当前没有绑定的账号**\n\n其他用户可以通过 /login 绑定他们的账号。"
        else:
            text = "📭 **您还没有绑定账号**\n\n请发送 /login 开始绑定。"
        await message.reply(text)
        return

    # 构建账号列表消息
    lines = ["👥 **已绑定的账号**\n"]
    for i, info in enumerate(accounts_info, 1):
        status = "🟢 在线" if info["is_connected"] else "🔴 离线"
        lines.append(
            f"{i}. {status}\n"
            f"   🆔 `{info['owner_id']}`\n"
            f"   👤 {info['first_name']} (@{info['username']})\n"
        )

    # Bot Owner 可以看到管理按钮
    if is_owner and accounts_info:
        kb = tg.Keyboards()
        for info in accounts_info:
            kb.add_button(
                f"🔴 移除 {info['first_name']}",
                callback_data=f"remove_account:{info['owner_id']}",
            )
        kb.row().add_button("❌ 关闭", callback_data="close_message")
        keyboard = kb.build()
        await message.reply("\n".join(lines), reply_markup=keyboard)
    else:
        await message.reply("\n".join(lines))


@tg.Client.on_callback_query(tg.filters.regex(r"^accounts_list$"))
async def accounts_list_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """账号列表回调 (从管理员面板进入，原地编辑)"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()

    accounts_info = await app.account_manager.get_accounts_info()
    if not accounts_info:
        await callback_query.edit_message_text("📭 **当前没有绑定的账号**")
        return

    lines = ["👥 **已绑定的账号**\n"]
    for i, info in enumerate(accounts_info, 1):
        status = "🟢 在线" if info["is_connected"] else "🔴 离线"
        lines.append(
            f"{i}. {status}\n"
            f"   🆔 `{info['owner_id']}`\n"
            f"   👤 {info['first_name']} (@{info['username']})\n"
        )

    kb = tg.Keyboards()
    for info in accounts_info:
        kb.add_button(
            f"🔴 移除 {info['first_name']}",
            callback_data=f"remove_account:{info['owner_id']}",
        )
    kb.row().add_button("⬅️ 返回", callback_data="back_to_admin")
    kb.add_button("❌ 关闭", callback_data="close_message")

    await callback_query.edit_message_text("\n".join(lines), reply_markup=kb.build())


@tg.Client.on_callback_query(tg.filters.regex(r"^remove_account:(\d+)$"))
async def remove_account_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """移除指定账号"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    owner_id = int(callback_query.matches[0].group(1))
    await callback_query.answer()

    # 确认移除
    kb = tg.Keyboards.confirm_cancel(
        confirm_data=f"remove_account_confirm:{owner_id}",
        cancel_data="accounts_list",
        confirm_text="⚠️ 确认移除",
        cancel_text="取消",
    )
    await callback_query.edit_message_text(
        f"⚠️ **确认移除账号 `{owner_id}`？**\n\n"
        "移除后该账号将停止运行并从数据库中删除。\n"
        "该操作不可撤销。",
        reply_markup=kb,
    )


@tg.Client.on_callback_query(tg.filters.regex(r"^remove_account_confirm:(\d+)$"))
async def remove_account_confirm_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """执行移除账号"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    owner_id = int(callback_query.matches[0].group(1))
    await callback_query.answer()

    try:
        await app.account_manager.remove_account(owner_id)
        await callback_query.edit_message_text(
            f"✅ **已移除账号 `{owner_id}`**\n\n"
            "该账号已停止运行并从数据库中删除。"
        )
    except Exception as e:
        logger.error(f"移除账号 {owner_id} 失败: {e}")
        await callback_query.answer(f"❌ 移除失败: {e}", show_alert=True)


# ==================== 退出登录 (单账号) ====================

@tg.Client.bot_command("logout", "解绑当前账号")
async def logout_command_handler(client: tg.Client, message: tg.Message):
    """
    普通用户解绑自己的账号
    Bot Owner 可以通过 /accounts 管理所有账号
    """
    tg.delete_later(message)

    user_id = message.from_user.id

    # 检查是否有绑定
    account = app.account_manager.get_account(user_id)
    if not account:
        await message.reply("❌ 您还没有绑定账号。\n请发送 /login 开始绑定。")
        return

    # 确认解绑
    kb = tg.Keyboards.confirm_cancel(
        confirm_data=f"self_logout:{user_id}",
        cancel_data="close_message",
        confirm_text="⚠️ 确认解绑",
        cancel_text="取消",
    )
    await message.reply(
        "⚠️ **确认解绑您的账号？**\n\n"
        "解绑后该账号将停止运行并从数据库中删除。\n"
        "您可以随时通过 /login 重新绑定。",
        reply_markup=kb,
    )


@tg.Client.on_callback_query(tg.filters.regex(r"^self_logout:(\d+)$"))
async def self_logout_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """执行普通用户解绑"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限操作其他账号。", show_alert=True)
        return

    await callback_query.answer()
    try:
        await app.account_manager.remove_account(user_id)
        await callback_query.edit_message_text(
            "✅ **已成功解绑您的账号**\n\n"
            "您可以随时通过 /login 重新绑定。"
        )
    except Exception as e:
        logger.error(f"用户 {user_id} 解绑失败: {e}")
        await callback_query.answer(f"❌ 解绑失败: {e}", show_alert=True)


# ==================== 重启 ====================

@tg.Client.on_callback_query(tg.filters.regex(r"^restart_confirm$"))
async def restart_confirm_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """处理重启确认"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    keyboard = tg.Keyboards.confirm_cancel(
        confirm_data="restart_execute",
        cancel_data="back_to_admin",
        confirm_text="🔄 确认重启",
        cancel_text="取消",
    )

    text = "🔄 **确认重启脚本？**\n\n重启期间脚本将暂时无法使用，大约需要几秒钟时间。"
    await callback_query.answer()
    await callback_query.edit_message_text(text, reply_markup=keyboard)


@tg.Client.on_callback_query(tg.filters.regex(r"^restart_execute$"))
async def restart_execute_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """执行重启"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    await callback_query.edit_message_text("🔄 **正在重启中，请稍候...**")

    await asyncio.sleep(1)

    try:
        await app.manager.restart()
    except Exception as e:
        logger.error(f"重启失败: {e}")
        await callback_query.answer(f"❌ 重启失败: {e}", show_alert=True)


# ==================== 通用 ====================

@tg.Client.on_callback_query(tg.filters.regex(r"^close_message$"))
async def close_message_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """统一处理关闭/删除消息"""
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        try:
            await callback_query.edit_message_text("❌ 菜单已关闭")
        except Exception:
            pass


@tg.Client.on_callback_query(tg.filters.regex(r"^back_to_admin$"))
async def back_to_admin_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """返回管理员面板"""
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    await callback_query.answer()
    await send_admin_menu(callback_query.message, edit=True)


@tg.Client.on_callback_query(tg.filters.regex(r"^back_to_settings$"))
async def back_to_settings_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """返回个人设置主菜单"""
    user_id = callback_query.from_user.id
    await callback_query.answer()
    await send_settings_menu(callback_query.message, user_id=user_id, edit=True)


# ==================== 重启自己的 Userbot ====================

@tg.Client.on_callback_query(tg.filters.regex(r"^rs:(\d+)$"))
async def restart_self_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """确认重启自己的 Userbot"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    keyboard = tg.Keyboards.confirm_cancel(
        confirm_data=f"rse:{user_id}",
        cancel_data="back_to_settings",
        confirm_text="🔄 确认重启",
    )
    await callback_query.edit_message_text(
        "🔄 **确认重启您的人形？**\n\n重启期间您的人形将暂时离线，大约需要几秒钟。",
        reply_markup=keyboard,
    )


@tg.Client.on_callback_query(tg.filters.regex(r"^rse:(\d+)$"))
async def restart_self_execute_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """执行重启自己的 Userbot"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    await callback_query.edit_message_text("🔄 **正在重启您的 Userbot，请稍候...**")

    success = await app.account_manager.restart_account(user_id)
    if success:
        await callback_query.message.reply("✅ **您的 Userbot 已成功重启！**")
    else:
        await callback_query.message.reply("❌ **重启失败。** 请检查账号是否仍然有效。")


# ==================== 插件管理 ====================

def get_user_plugins():
    """
    递归获取 Userbot 插件模块列表
    """
    root_dir = "plugins/user"
    modules = []
    if not os.path.exists(root_dir):
        return modules

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                relative_path = os.path.relpath(os.path.join(root, file), root_dir)
                module_name = relative_path.replace(os.sep, ".").replace(".py", "")
                modules.append(f"plugins.user.{module_name}")
    return sorted(modules)



# ==================== 修改前缀 ====================

@tg.Client.on_callback_query(tg.filters.regex(r"^sp:(\d+)$"))
async def set_prefix_callback_handler(
    client: tg.Client, callback_query: tg.CallbackQuery
):
    """处理个人修改前缀的回调"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    msg = callback_query.message
    chat_id = msg.chat.id

    try:
        q_msg, reply = await client.ask(
            chat_id, "请输入新的指令前缀 (例如 . 或 !):", timeout=60
        )
        if not reply or not reply.text:
            await q_msg.delete()
            await callback_query.answer()
            return

        new_prefix = reply.text.strip()
        if len(new_prefix) > 5:
            await q_msg.delete()
            await callback_query.answer("❌ 前缀太长了。", show_alert=True)
            return

        await app.account_manager.save_prefix(user_id, new_prefix)
        account = app.account_manager.get_account(user_id)
        if account:
            account._prefix = new_prefix

        await q_msg.delete()
        await callback_query.answer(
            f"✅ 已改为 {new_prefix}",
            show_alert=True,
        )
        await send_settings_menu(msg, user_id=user_id, edit=True)

    except asyncio.TimeoutError:
        await callback_query.answer("⏰ 已超时", show_alert=True)
        await send_settings_menu(msg, user_id=user_id, edit=True)
    except Exception as e:
        logger.error(f"修改前缀失败: {e}")
        await callback_query.answer(f"❌ 修改失败: {e}", show_alert=True)


# ==================== 普通用户功能 ====================


@tg.Client.on_callback_query(tg.filters.regex(r"^mac:(\d+)$"))
async def my_account_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """普通用户查看自己的账号信息"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()

    # 获取该用户的账号信息
    accounts_info = await app.account_manager.get_accounts_info(user_id)
    if not accounts_info:
        await callback_query.edit_message_text(
            "📭 **您还没有绑定账号**\n\n请发送 /login 开始绑定。"
        )
        return

    info = accounts_info[0]
    status = "🟢 在线" if info["is_connected"] else "🔴 离线"
    text = (
        f"📋 **我的账号**\n\n"
        f"状态: {status}\n"
        f"🆔 `{info['owner_id']}`\n"
        f"👤 {info['first_name']} (@{info['username']})\n"
    )

    kb = tg.Keyboards()
    kb.add_button("🔗 解绑账号", callback_data=f"self_logout:{user_id}")
    kb.row().add_button("⬅️ 返回", callback_data="back_to_settings")
    kb.add_button("❌ 关闭", callback_data="close_message")

    await callback_query.edit_message_text(text, reply_markup=kb.build())


@tg.Client.on_callback_query(tg.filters.regex(r"^upl:(\d+)$"))
async def user_plugins_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """普通用户管理自己的插件"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    await send_user_plugins_menu(callback_query.message, user_id, edit=True)


async def send_user_plugins_menu(target: tg.Message, user_id: int, rel_path: str = "", edit: bool = True):
    """
    显示普通用户的插件管理菜单 (按用户隔离)
    """
    base_module = "plugins.user"
    current_module_prefix = (
        f"{base_module}.{rel_path}" if rel_path else base_module
    )

    base_dir = os.path.join("plugins", "user", rel_path.replace(".", os.sep))
    dirs = []
    files = []

    if os.path.exists(base_dir):
        for item in os.listdir(base_dir):
            full_path = os.path.join(base_dir, item)
            if os.path.isdir(full_path):
                if item != "__pycache__" and not item.startswith("."):
                    dirs.append(item)
            elif item.endswith(".py") and item != "__init__.py":
                files.append(item.replace(".py", ""))

    dirs.sort()
    files.sort()

    kb = tg.Keyboards()

    # 列出子目录
    dir_buttons = []
    for d in dirs:
        new_rel_path = f"{rel_path}.{d}" if rel_path else d
        status_icon = await get_user_directory_status(user_id, new_rel_path)
        display_icon = f" {status_icon}" if status_icon else ""
        dir_buttons.append(
            tg.Keyboards.button(
                f"📁 {d}{display_icon}",
                callback_data=f"ump:{user_id}:{new_rel_path}",
            )
        )

    if dir_buttons:
        kb.add_buttons(dir_buttons, max_cols=2)

    # 列出文件（只传文件名和 rel_path，由 handler 重建完整模块路径以节省 callback_data 长度）
    file_buttons = []
    for f in files:
        mod_name = f"{current_module_prefix}.{f}"
        enabled = await app.account_manager.is_module_enabled(user_id, mod_name)
        status_icon = "✅" if enabled else "🚫"
        file_buttons.append(
            tg.Keyboards.button(
                f"📄 {f}: {status_icon}",
                callback_data=f"utm:{user_id}:{rel_path}:{f}",
            )
        )

    if file_buttons:
        kb.add_buttons(file_buttons, max_cols=2)

    # 全部操作按钮
    if files and not dirs:
        kb.row()
        kb.add_button("✅ 全部开启", callback_data=f"ube:{user_id}:{rel_path}")
        kb.add_button("🚫 全部禁用", callback_data=f"ubd:{user_id}:{rel_path}")

    # 导航按钮
    kb.row()
    if rel_path:
        parent_path = ".".join(rel_path.split(".")[:-1])
        kb.add_button(
            "⬅️ 返回上级",
            callback_data=f"ump:{user_id}:{parent_path}"
        )
    else:
        kb.add_button("⬅️ 返回设置", callback_data="back_to_settings")

    kb.add_button("❌ 关闭", callback_data="close_message")

    keyboard = kb.build()
    display_path = (
        f"plugins/user/{rel_path.replace('.', '/')}" if rel_path else "plugins/user"
    )
    text = (
        f"🔌 **我的插件管理**\n当前路径: `{display_path}`\n\n"
        "点击文件夹进入，点击文件切换开关："
    )

    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except tg.errors.MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"发送用户插件菜单失败: {e}")


async def get_user_directory_status(user_id: int, rel_path: str):
    """
    获取指定用户的目录插件状态
    返回: "✅" (全部开启), "🚫" (全部禁用), "🌗" (部分开启), 或 "" (无插件)
    """
    all_plugins = get_user_plugins()
    target_prefix = f"plugins.user.{rel_path}." if rel_path else "plugins.user."
    target_modules = [m for m in all_plugins if m.startswith(target_prefix)]

    if not target_modules:
        return ""

    enabled_count = 0
    for m in target_modules:
        if await app.account_manager.is_module_enabled(user_id, m):
            enabled_count += 1

    if enabled_count == len(target_modules):
        return "✅"
    elif enabled_count == 0:
        return "🚫"
    else:
        return "🌗"


@tg.Client.on_callback_query(tg.filters.regex(r"^ump:(\d+):(.*)$"))
async def user_manage_plugins_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """普通用户浏览插件目录"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    rel_path = callback_query.matches[0].group(2)
    await callback_query.answer()
    await send_user_plugins_menu(callback_query.message, user_id, rel_path=rel_path)


@tg.Client.on_callback_query(tg.filters.regex(r"^utm:(\d+):(.*):(.+)$"))
async def user_toggle_mod_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """普通用户切换自己的模块"""
    user_id = int(callback_query.matches[0].group(1))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    rel_path = callback_query.matches[0].group(2)
    file_name = callback_query.matches[0].group(3)
    # 重建完整模块路径
    module_name = f"plugins.user.{rel_path}.{file_name}" if rel_path else f"plugins.user.{file_name}"

    enabled = await app.account_manager.toggle_module(user_id, module_name)
    await callback_query.answer(
        f"已{'开启' if enabled else '禁用'}模块，立即生效"
    )

    await send_user_plugins_menu(callback_query.message, user_id, rel_path=rel_path, edit=True)


@tg.Client.on_callback_query(tg.filters.regex(r"^ub([ed]):(\d+):(.*)$"))
async def user_bulk_toggle_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """普通用户批量切换自己的模块"""
    action_code = callback_query.matches[0].group(1)
    action = "enable" if action_code == "e" else "disable"
    user_id = int(callback_query.matches[0].group(2))
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    rel_path = callback_query.matches[0].group(3)

    all_plugins = get_user_plugins()
    target_prefix = (
        f"plugins.user.{rel_path}." if rel_path else "plugins.user."
    )

    target_modules = [
        m
        for m in all_plugins
        if m.startswith(target_prefix) or m == target_prefix[:-1]
    ]

    if not target_modules:
        await callback_query.answer("该目录下没有可管理的插件。")
        return

    if action == "enable":
        await app.account_manager.enable_all_in_path(user_id, target_modules)
        await callback_query.answer(f"已开启 {len(target_modules)} 个插件，立即生效")
    else:
        await app.account_manager.disable_all_in_path(user_id, target_modules)
        await callback_query.answer(f"已禁用 {len(target_modules)} 个插件，立即生效")

    await send_user_plugins_menu(callback_query.message, user_id, rel_path=rel_path, edit=True)
