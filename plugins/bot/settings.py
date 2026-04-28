import os
from core import tg, db, app

@tg.Client.bot_command("settings", "系统设置")
async def settings_handler(client: tg.Client, message: tg.Message):
    """
    显示系统设置菜单
    """
    if message.from_user.id != app.manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    await send_settings_menu(message)

async def send_settings_menu(target: tg.Message, edit: bool = False):
    """
    发送或编辑设置菜单
    """
    prefix = app.manager.prefix
    
    keyboard = tg.InlineKeyboardMarkup([
        [
            tg.InlineKeyboardButton(
                f"指令前缀: {prefix}",
                callback_data="set_prefix"
            )
        ],
        [
            tg.InlineKeyboardButton(
                "🔌 插件管理",
                callback_data="manage_plugins:"
            )
        ]
    ])
    
    text = "⚙️ **系统设置**\n\n点击下方按钮切换功能开关或修改配置："
    
    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.reply(text, reply_markup=keyboard)
    except Exception as e:
        app.logger.error(f"发送设置菜单失败: {e}")

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
    返回: "✅" (全部开启), "❌" (全部禁用), "🌗" (部分开启), 或 "" (无插件)
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
        return "❌"
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
    
    buttons = []
    
    # 列出子目录
    for d in dirs:
        new_rel_path = f"{rel_path}.{d}" if rel_path else d
        status_icon = get_directory_status(new_rel_path)
        display_icon = f" {status_icon}" if status_icon else ""
        buttons.append([
            tg.InlineKeyboardButton(
                f"📁 {d}/{display_icon}",
                callback_data=f"manage_plugins:{new_rel_path}"
            )
        ])
    
    # 列出文件
    for f in files:
        mod_name = f"{current_module_prefix}.{f}"
        status_icon = "✅" if app.manager.is_module_enabled(mod_name) else "❌"
        buttons.append([
            tg.InlineKeyboardButton(
                f"📄 {f}: {status_icon}",
                callback_data=f"toggle_mod:{mod_name}:{rel_path}"
            )
        ])
    
    # 导航按钮
    nav_buttons = []
    if rel_path:
        # 计算父目录
        parent_path = ".".join(rel_path.split(".")[:-1])
        nav_buttons.append(tg.InlineKeyboardButton("⬅️ 返回上级", callback_data=f"manage_plugins:{parent_path}"))
    else:
        nav_buttons.append(tg.InlineKeyboardButton("⬅️ 返回主菜单", callback_data="back_to_settings"))
    
    # 全部操作按钮 (仅在最末级目录，即没有子文件夹的目录显示)
    if files and not dirs:
        bulk_buttons = [
            tg.InlineKeyboardButton("✅ 全部开启", callback_data=f"bulk_enable:{rel_path}"),
            tg.InlineKeyboardButton("❌ 全部禁用", callback_data=f"bulk_disable:{rel_path}")
        ]
        buttons.append(bulk_buttons)
    
    buttons.append(nav_buttons)
    
    keyboard = tg.InlineKeyboardMarkup(buttons)
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
    await send_plugins_menu(callback_query.message, rel_path=rel_path)

@tg.Client.on_callback_query(tg.filters.regex(r"^back_to_settings$"))
async def back_to_settings_handler(client: tg.Client, callback_query: tg.CallbackQuery):
    if callback_query.from_user.id != app.manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return
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
