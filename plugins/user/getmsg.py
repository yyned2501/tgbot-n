import os
from datetime import datetime
from pathlib import Path
from core import Client, filters, Message, PREFIX, manager, logger

@Client.on_message(filters.command("getmsg", PREFIX) & filters.me)
async def get_message(client: Client, message: Message):
    """
    获取消息信息并由 Bot 发送给 Owner
    """
    if not message.reply_to_message:
        await message.edit("❌ 请回复一条消息以获取其信息。")
        return

    if not manager.bot:
        await message.edit("❌ Assistant Bot 未启动，无法发送消息。")
        return

    # 使用 logs 目录存放临时文件
    temp_dir = Path("logs/temp_msgs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 构建文件名
    reply = message.reply_to_message
    if reply.text:
        # 提取前6个字符并处理非法文件名字符
        safe_text = "".join(c for c in reply.text[:6] if c.isalnum() or c in "._- ")
        file_name = f"{safe_text}_{current_time}.txt"
    elif reply.caption:
        safe_text = "".join(c for c in reply.caption[:6] if c.isalnum() or c in "._- ")
        file_name = f"{safe_text}_{current_time}.txt"
    else:
        file_name = f"{current_time}.txt"
    
    file_path = temp_dir / file_name
    
    try:
        # 写入消息内容的字符串表示
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(reply))
        
        # 使用 Bot 发送文档给 Owner
        if manager.owner_id:
            await manager.bot.send_document(
                chat_id=manager.owner_id,
                document=str(file_path),
                caption=f"📋 消息详情\n来自: `{reply.chat.id}`\n消息 ID: `{reply.id}`"
            )
            await message.delete()
            logger.info(f"已获取消息 {reply.id} 并通过 Bot 发送")
        else:
            await message.edit("❌ Owner ID 未设置，无法发送。")
            
    except Exception as e:
        logger.error(f"获取消息失败: {e}")
        await message.edit(f"❌ 获取消息失败: {e}")
    finally:
        # 删除临时文件
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"删除临时文件失败: {e}")
