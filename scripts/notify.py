"""
scripts/notify.py
通用通知工具 — 通过 Bot 向 Owner 发送格式化通知。
其他插件可直接复用，避免各自实现 _send_notify。
"""
from core import app


async def notify_owner(
    title: str,
    *,
    icon: str = "📢",
    fields: dict[str, str] | None = None,
    text: str | None = None,
) -> None:
    """
    向 Owner 发送一条格式化通知。

    用法示例::

        from scripts.notify import notify_owner

        await notify_owner(
            "癫影积分红包-已抢",
            icon="🟡",
            fields={
                "🏠 所在群组": f"{chat_title}\\n   群ID: {chat_id}",
                "📩 抢包结果": result_text,
                "🔗 消息链接": msg_link,
            },
        )

    Args:
        title: 通知标题（不含图标）
        icon: 标题前缀图标，默认 📢
        fields: 标签 → 值 的映射，按插入顺序逐行渲染
        text: 追加在字段之后的自由文本块
    """
    try:
        parts = [f"{icon} {title}"]
        if fields:
            parts.append("")  # 空行分隔
            for label, value in fields.items():
                parts.append(f"{label}")
                parts.append(f"   {value}")
                parts.append("")
        if text:
            parts.append(text)
        message = "\n".join(parts).strip()
        await app.manager.send_bot_message(message)
    except Exception as e:
        app.logger.debug(f"[notify] 通知发送失败: {e}")
