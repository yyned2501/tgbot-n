import re
import asyncio
from decimal import Decimal
from pyrogram.types import InlineKeyboardMarkup
from core import tg, db, app
from scripts.filters import create_bot_filter, reply_to_me
from scripts.notify import notify_owner

# 配置常量 (朱雀站点信息)
TARGET_CHATS = [-1001833464786, -1002262543959]  # 监听的群组 ID
ZHUQUE_BOT_ID = 5697370563  # 朱雀 Bot ID
SITE_NAME = "zhuque"

@tg.Client.on_message(
    tg.filters.chat(TARGET_CHATS)
    & create_bot_filter(ZHUQUE_BOT_ID)
    & tg.filters.regex(
        r"内容: ([\s\S]*?)\n灵石: (\d+(?:\.\d+)?)/\d+(?:\.\d+)?\n剩余: .*?\n大善人: (.*)"
    )
)
async def grab_zhuque_redpocket(client: tg.Client, message: tg.Message):
    """
    监听朱雀红包并自动秒抢，记录获取的魔力值流水
    """
    owner_id = getattr(client, "_owner_id", 0)

    try:
        # 1. 匹配红包细节
        match = message.matches[0] if message.matches else None
        if not match:
            return

        redpocket_name = match.group(1)
        giver_user = match.group(3)

        # 2. 检查红包按钮并确保是 InlineKeyboardMarkup
        if not message.reply_markup or not isinstance(message.reply_markup, InlineKeyboardMarkup):
            return
        if not message.reply_markup.inline_keyboard:
            return
            
        callback_data = message.reply_markup.inline_keyboard[0][0].callback_data
        if not callback_data:
            return
        
        # 3. 循环发起抢夺请求 (秒抢逻辑)
        retry_times = 0
        max_retries = 200  # 限制最大重试次数以保护账号安全
        
        app.logger.info(f"⚡ 侦测到朱雀红包: {redpocket_name} (发件人: {giver_user})，owner_id={owner_id}，启动自动秒抢...")
        
        while retry_times < max_retries:
            # request_callback_answer 内部 retries=1，网络抖动易失败，在此加外层防护
            try:
                result_message = await client.request_callback_answer(
                    message.chat.id, message.id, callback_data
                )
            except Exception:
                # 网络/API 临时故障，继续下一次点击尝试，不中断抢红包流程
                retry_times += 1
                await asyncio.sleep(0.15)
                continue

            await asyncio.sleep(0.15)  # 重试延迟 150ms 保持较高连击速度且不易封禁
            
            # 解析点击结果
            msg_text = getattr(result_message, "message", None)
            if msg_text:
                match_result = re.search(r"已获得 (\d+) 灵石", msg_text)
                if match_result:
                    bonus_amount = Decimal(match_result.group(1))
                    app.logger.info(f"🎉 抢红包成功！获得 {bonus_amount} 灵石 | 尝试次数: {retry_times + 1}")

                    # 通知对应用户
                    asyncio.create_task(
                        notify_owner(
                            "朱雀红包-已抢",
                            icon="🟡",
                            owner_id=owner_id,
                            fields={
                                "🎁 红包内容": redpocket_name,
                                "👤 发包者": giver_user,
                                "💰 获得": f"{bonus_amount} 灵石",
                                "🔄 尝试次数": str(retry_times + 1),
                                "📎 消息链接": getattr(message, "link", ""),
                            },
                        )
                    )

                    # 4. 写入通用魔力值流水账单 (BonusLog)
                    async with db.async_session() as session:
                        async with session.begin():
                            record = db.BonusLog(
                                owner_id=owner_id,
                                website=SITE_NAME,
                                action_type="redpocket",
                                amount=bonus_amount,
                                tag=f"发包者: {giver_user} | 红包内容: {redpocket_name}",
                                message_id=message.id
                            )
                            session.add(record)
                    return
            retry_times += 1
            
    except Exception as e:
        app.logger.warning(f"⚠️ 抢朱雀红包失败（已达最大尝试次数 {max_retries}）: {e}")
        asyncio.create_task(
            notify_owner(
                "朱雀红包-未抢到",
                icon="❌",
                owner_id=owner_id,
                fields={
                    "🎁 红包内容": redpocket_name if 'redpocket_name' in locals() else "未知",
                    "🔄 尝试次数": f"{max_retries}（已达上限）",
                    "⚠️ 错误": str(e),
                },
            )
        )


@tg.Client.on_message(
    tg.filters.chat(TARGET_CHATS)
    & create_bot_filter(ZHUQUE_BOT_ID)
    & reply_to_me
    & tg.filters.regex(r"天上掉馅饼啦, \+(\d+\.\d+)")
)
async def log_zhuque_pie(client: tg.Client, message: tg.Message):
    """
    自动记录掉馅饼的魔力值变动
    """
    owner_id = getattr(client, "_owner_id", 0)

    try:
        match = message.matches[0] if message.matches else None
        if not match:
            return

        bonus_amount = Decimal(match.group(1))
        app.logger.info(f"🎁 被馅饼砸中！获得 {bonus_amount} 灵石，正在写入流水...")

        # 通知对应用户
        asyncio.create_task(
            notify_owner(
                "朱雀馅饼",
                icon="🎁",
                owner_id=owner_id,
                fields={
                    "💰 获得": f"{bonus_amount} 灵石",
                    "📎 消息链接": getattr(message, "link", ""),
                },
            )
        )

        # 写入通用魔力值流水账单 (BonusLog)
        async with db.async_session() as session:
            async with session.begin():
                record = db.BonusLog(
                    owner_id=owner_id,
                    website=SITE_NAME,
                    action_type="pie",
                    amount=bonus_amount,
                    tag="被朱雀系统馅饼砸中",
                    message_id=message.id
                )
                session.add(record)
                
    except Exception as e:
        app.logger.error(f"❌ 记录朱雀馅饼时发生异常: {e}")
