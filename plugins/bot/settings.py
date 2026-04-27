from core import Client, filters, Message, CallbackQuery, manager, get_setting, set_setting
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.bot_command("settings", "系统设置")
async def settings_handler(client: Client, message: Message):
    """
    显示系统设置菜单
    """
    if message.from_user.id != manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    await send_settings_menu(message)

async def send_settings_menu(target: Message, edit: bool = False):
    """
    发送或编辑设置菜单
    """
    zhuque_record = await get_setting("zhuque_record", "false")
    zhuque_icon = "✅" if zhuque_record == "true" else "❌"
    
    prefix = manager.prefix
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"Zhuque 记录: {zhuque_icon}",
                callback_data="toggle_zhuque_record"
            )
        ],
        [
            InlineKeyboardButton(
                f"指令前缀: {prefix}",
                callback_data="set_prefix"
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
        from core import logger
        logger.error(f"发送设置菜单失败: {e}")

@Client.on_callback_query(filters.regex(r"^toggle_zhuque_record$"))
async def toggle_zhuque_record_handler(client: Client, callback_query: CallbackQuery):
    """
    处理切换 Zhuque 记录开关的回调
    """
    if callback_query.from_user.id != manager.owner_id:
        await callback_query.answer("❌ 您没有权限。", show_alert=True)
        return

    current = await get_setting("zhuque_record", "false")
    new_value = "false" if current == "true" else "true"
    await set_setting("zhuque_record", new_value)
    
    await callback_query.answer(f"已{'开启' if new_value == 'true' else '关闭'} Zhuque 记录")
    await send_settings_menu(callback_query.message, edit=True)

@Client.on_callback_query(filters.regex(r"^set_prefix$"))
async def set_prefix_callback_handler(client: Client, callback_query: CallbackQuery):
    """
    处理修改前缀的回调
    """
    if callback_query.from_user.id != manager.owner_id:
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
            
        await manager.set_prefix(new_prefix)
        await callback_query.message.reply(f"✅ 指令前缀已修改为 `{new_prefix}`。\n⚠️ 注意：前缀修改需要重启程序后才能完全生效。")
        
        # 刷新菜单
        await send_settings_menu(callback_query.message)
        
    except Exception as e:
        await callback_query.message.reply(f"❌ 修改失败: {e}")
