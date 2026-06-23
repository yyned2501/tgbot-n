import os
import asyncio
from core import tg, db, app

@tg.Client.bot_command("settings", "系统设置")
async def settings_handler(client: tg.Client, message: tg.Message):
    """
    显示系统设置菜单
    """
    # 60秒后自动删除指令消息
    asyncio.create_task(tg.delete_later(message))
    
    if message.from_user.id != app.manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    await send_settings_menu(message)

async def send_settings_menu(target: tg.Message, edit: bool = False):
    """
    发送或编辑设置菜单
    """
    prefix = app.manager.prefix
    
    kb = tg.Keyboards()
    kb.add_buttons([
        tg.Keyboards.button(f"⌨️ 指令前缀: {prefix}", callback_data="set_prefix"),
        tg.Keyboards.button("🔌 插件管理", callback_data="manage_plugins:"),
        tg.Keyboards.button("🔄 重启脚本", callback_data="restart_confirm"),
        tg.Keyboards.button("🚪 退出登录", callback_data="logout_confirm")
    ])
    kb.row().add_button("❌ 关闭菜单", callback_data="close_message")
    keyboard = kb.build()
    
    text = "⚙️ **系统设置**\n\n点击下方按钮切换功能开关或修改配置："
    
    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except Exception as e:
        app.logger.error(f"发送设置菜单失败: {e}")

@tg.Client.on_callback_query(tg.filters.regex(r"^logout_confirm$"))
async def logout_confirm_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    处理退出登录确认 (来自回调)
    """
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    await send_logout_confirm(callback_query.message, edit=True)

async def send_logout_confirm(target: tg.Message, edit: bool = True):
    """
    发送退出登录确认界面
    """
    keyboard = tg.Keyboards.confirm_cancel(
        confirm_data="logout_execute",
        cancel_data="back_to_settings",
        confirm_text="⚠️ 确认退出",
        cancel_text="取消"
    )
    
    text = (
        "⚠️ **确认退出登录？**\n\n"
        "退出后将执行以下操作：\n"
        "1. 停止当前运行的人形脚本 (Userbot)。\n"
        "2. 从数据库中清除 Session String。\n"
        "3. 清除 Owner 绑定信息。\n\n"
        "**此操作不可撤销，确定继续吗？**"
    )
    
    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.reply(text, reply_markup=keyboard)

@tg.Client.on_callback_query(tg.filters.regex(r"^logout_execute$"))
async def logout_execute_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    执行退出登录
    """
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    
    try:
        await callback_query.answer()
        await app.manager.logout()
        await callback_query.edit_message_text("✅ **已成功退出登录**\n\n所有 Session 数据已清除，人形脚本已停止。您可以发送 /login 重新登录。")
    except Exception as e:
        app.logger.error(f"退出登录失败: {e}")
        await callback_query.answer(f"❌ 退出失败: {e}", show_alert=True)

@tg.Client.on_callback_query(tg.filters.regex(r"^restart_confirm$"))
async def restart_confirm_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    处理重启确认 (来自回调)
    """
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    keyboard = tg.Keyboards.confirm_cancel(
        confirm_data="restart_execute",
        cancel_data="back_to_settings",
        confirm_text="🔄 确认重启",
        cancel_text="取消"
    )
    
    text = "🔄 **确认重启脚本？**\n\n重启期间脚本将暂时无法使用，大约需要几秒钟时间。"
    await callback_query.answer()
    await callback_query.edit_message_text(text, reply_markup=keyboard)

@tg.Client.on_callback_query(tg.filters.regex(r"^restart_execute$"))
async def restart_execute_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    执行重启
    """
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    
    await callback_query.answer()
    await callback_query.edit_message_text("🔄 **正在重启中，请稍候...**")
    
    # 延迟一小会儿确保消息已发送
    await asyncio.sleep(1)
    
    try:
        await app.manager.restart()
    except Exception as e:
        app.logger.error(f"重启失败: {e}")
        await callback_query.answer(f"❌ 重启失败: {e}", show_alert=True)

@tg.Client.on_callback_query(tg.filters.regex(r"^close_message$"))
async def close_message_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    统一处理关闭/删除消息
    """
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        # 如果无法删除（例如消息太旧），尝试清空内容
        try:
            await callback_query.edit_message_text("❌ 菜单已关闭")
        except Exception:
            pass

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

def get_directory_status(rel_path: str):
    """
    获取目录的状态
    返回: "✅" (全部开启), "🚫" (全部禁用), "🌗" (部分开启), 或 "" (无插件)
    """
    all_plugins = get_user_plugins()
    target_prefix = f"plugins.user.{rel_path}." if rel_path else "plugins.user."
    target_modules = [m for m in all_plugins if m.startswith(target_prefix)]
    
    if not target_modules:
        return ""
        
    enabled_count = sum(1 for m in target_modules if app.manager.is_module_enabled(m))
    
    if enabled_count == len(target_modules):
        return "✅"
    elif enabled_count == 0:
        return "🚫"
    else:
        return "🌗"

async def send_plugins_menu(target: tg.Message, rel_path: str = "", edit: bool = True):
    """
    显示插件管理菜单 (分层浏览)
    rel_path: 相对于 plugins/user 的路径，例如 "info" 或 ""
    """
    base_module = "plugins.user"
    current_module_prefix = f"{base_module}.{rel_path}" if rel_path else base_module
    
    # 获取目录内容
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
    
    # 列出子目录（每行最多2个）
    dir_buttons = []
    for d in dirs:
        new_rel_path = f"{rel_path}.{d}" if rel_path else d
        status_icon = get_directory_status(new_rel_path)
        display_icon = f" {status_icon}" if status_icon else ""
        dir_buttons.append(tg.Keyboards.button(f"📁 {d}{display_icon}", callback_data=f"manage_plugins:{new_rel_path}"))

    if dir_buttons:
        kb.add_buttons(dir_buttons, max_cols=2)
    
    # 列出文件（每行最多2个，留够空间显示状态）
    file_buttons = []
    for f in files:
        mod_name = f"{current_module_prefix}.{f}"
        status_icon = "✅" if app.manager.is_module_enabled(mod_name) else "🚫"
        file_buttons.append(tg.Keyboards.button(f"📄 {f}: {status_icon}", callback_data=f"toggle_mod:{mod_name}:{rel_path}"))

    if file_buttons:
        kb.add_buttons(file_buttons, max_cols=2)
    
    # 全部操作按钮 (仅在最末级目录，即没有子文件夹的目录显示)
    if files and not dirs:
        kb.row()
        kb.add_button("✅ 全部开启", callback_data=f"bulk_enable:{rel_path}")
        kb.add_button("🚫 全部禁用", callback_data=f"bulk_disable:{rel_path}")
    
    # 导航按钮
    kb.row()
    if rel_path:
        # 计算父目录
        parent_path = ".".join(rel_path.split(".")[:-1])
        kb.add_button("⬅️ 返回上级", callback_data=f"manage_plugins:{parent_path}")
    else:
        kb.add_button("⬅️ 返回主菜单", callback_data="back_to_settings")
    
    kb.add_button("❌ 关闭", callback_data="close_message")
    
    keyboard = kb.build()
    display_path = f"plugins/user/{rel_path.replace('.', '/')}" if rel_path else "plugins/user"
    text = f"🔌 **插件管理**\n当前路径: `{display_path}`\n\n点击文件夹进入，点击文件切换开关："
    
    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except Exception as e:
        app.logger.error(f"发送插件菜单失败: {e}")

@tg.Client.on_callback_query(tg.filters.regex(r"^manage_plugins:(.*)$"))
async def manage_plugins_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    
    rel_path = callback_query.matches[0].group(1)
    await callback_query.answer()
    await send_plugins_menu(callback_query.message, rel_path=rel_path)

@tg.Client.on_callback_query(tg.filters.regex(r"^back_to_settings$"))
async def back_to_settings_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    await callback_query.answer()
    await send_settings_menu(callback_query.message, edit=True)

@tg.Client.on_callback_query(tg.filters.regex(r"^toggle_mod:(.+):(.*)$"))
async def toggle_mod_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    
    module_name = callback_query.matches[0].group(1)
    rel_path = callback_query.matches[0].group(2)
    
    enabled = await app.manager.toggle_module(module_name)
    
    await callback_query.answer(f"已{'开启' if enabled else '禁用'}模块: {module_name}")
    await send_plugins_menu(callback_query.message, rel_path=rel_path, edit=True)

@tg.Client.on_callback_query(tg.filters.regex(r"^bulk_(enable|disable):(.*)$"))
async def bulk_toggle_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
    
    action = callback_query.matches[0].group(1)
    rel_path = callback_query.matches[0].group(2)
    
    # 获取该路径下的所有模块
    all_plugins = get_user_plugins()
    target_prefix = f"plugins.user.{rel_path}." if rel_path else "plugins.user."
    
    target_modules = [m for m in all_plugins if m.startswith(target_prefix) or m == target_prefix[:-1]]
    
    if not target_modules:
        await callback_query.answer("该目录下没有可管理的插件。")
        return
        
    if action == "enable":
        await app.manager.enable_all_in_path(target_modules)
        await callback_query.answer(f"已开启 {len(target_modules)} 个插件")
    else:
        await app.manager.disable_all_in_path(target_modules)
        await callback_query.answer(f"已禁用 {len(target_modules)} 个插件")
        
    await send_plugins_menu(callback_query.message, rel_path=rel_path, edit=True)

@tg.Client.on_callback_query(tg.filters.regex(r"^set_prefix$"))
async def set_prefix_callback_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    """
    处理修改前缀的回调
    """
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    await callback_query.answer()
    chat_id = callback_query.message.chat.id
    
    # 询问新前缀
    try:
        ask_prefix = await client.ask(chat_id, "请输入新的指令前缀 (例如 . 或 !):", timeout=60)
        if not ask_prefix or not ask_prefix.text:
            return
        
        new_prefix = ask_prefix.text.strip()
        if len(new_prefix) > 5:
            await callback_query.message.reply("❌ 前缀太长了。")
            return
            
        await app.manager.set_prefix(new_prefix)
        await callback_query.message.reply(f"✅ 指令前缀已修改为 `{new_prefix}`。\n⚠️ 注意：前缀修改需要重启程序后才能完全生效。")
        
        # 刷新菜单
        await send_settings_menu(callback_query.message)
        
    except Exception as e:
        await callback_query.message.reply(f"❌ 修改失败: {e}")
