from core import Message, filters, Filter

async def reply_to_me_filter(_, __, m: Message):
    """
    过滤器：检查消息是否回复了“我”的消息
    """
    return bool(
        m.reply_to_message
        and m.reply_to_message.from_user
        and m.reply_to_message.from_user.is_self
    )

# 过滤器对象
reply_to_me = filters.create(reply_to_me_filter)

def create_bot_filter(bot_id: int):
    """
    工厂函数：创建一个匹配特定 Bot ID 的过滤器
    """
    async def bot_filter(_, __, m: Message):
        return bool(m.from_user and m.from_user.is_bot and m.from_user.id == bot_id)

    return filters.create(bot_filter)
