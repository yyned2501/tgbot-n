import re
from datetime import datetime
from core import Client, filters, Message, Base, async_session, logger, get_setting, ZhuqueResult
from scripts.filters import create_bot_filter

GROUPID = -1002262543959
BOTID = 5697370563

@Client.on_message(
    filters.chat(GROUPID)
    & create_bot_filter(BOTID)
    & filters.regex(r"已结算: 结果为 (\d+) (.)")
)
async def zhuque_handler(client: Client, message: Message):
    """
    监听并记录 Zhuque 压大小结果
    触发逻辑：监听结算通知消息，并从其回复的消息中获取投注详情
    """
    # 检查开关设置
    if await get_setting("zhuque_record", "false") == "false":
        return

    try:
        # 1. 从正则匹配结果中获取最终结果 (大/小)
        # message.matches[0] 是 regex 过滤器的匹配结果
        match = message.matches[0]
        final_result = 1 if match.group(2) == "大" else 0

        # 2. 获取包含投注详情的消息 (被回复的消息)
        if not message.reply_to_message:
            # 如果没有回复消息，尝试从当前消息解析（兼容旧逻辑）
            detail_text = message.text
        else:
            detail_text = message.reply_to_message.text or ""

        if not detail_text:
            return

        # 3. 解析押大合计
        big_total = 0
        big_section = re.search(
            r"押大:\n(.*?)(?=\n押小:|\n\n|$)", detail_text, re.DOTALL
        )
        if big_section:
            amounts = re.findall(r": ([\d,]+)", big_section.group(1))
            big_total = sum(int(a.replace(",", "")) for a in amounts)

        # 4. 解析押小合计
        small_total = 0
        small_section = re.search(r"押小:\n(.*)", detail_text, re.DOTALL)
        if small_section:
            amounts = re.findall(r": ([\d,]+)", small_section.group(1))
            small_total = sum(int(a.replace(",", "")) for a in amounts)

        # 5. 解析时间
        created_at_match = re.search(r"创建时间: ([\d\- :]+)", detail_text)
        settlement_time_match = re.search(r"结算时间: ([\d\- :]+)", detail_text)

        created_at = (
            datetime.strptime(created_at_match.group(1), "%Y-%m-%d %H:%M:%S")
            if created_at_match
            else datetime.now()
        )
        settlement_time = (
            datetime.strptime(settlement_time_match.group(1), "%Y-%m-%d %H:%M:%S")
            if settlement_time_match
            else datetime.now()
        )

        # 6. 保存到数据库
        async with async_session() as session:
            async with session.begin():
                new_record = ZhuqueResult(
                    final_result=final_result,
                    big_total=big_total,
                    small_total=small_total,
                    created_at=created_at,
                    settlement_time=settlement_time,
                )
                session.add(new_record)

        logger.info(
            f"✅ Zhuque 结果已记录: {'大' if final_result == 1 else '小'} | 大总计: {big_total:,} | 小总计: {small_total:,}"
        )

    except Exception as e:
        logger.error(f"❌ 解析或记录 Zhuque 结果时发生错误: {e}")
