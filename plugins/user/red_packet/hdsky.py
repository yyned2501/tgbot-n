"""
plugins/user/red_packet/hdsky.py
天空红包（拼手气红包）自动抢 — 按钮版

天空小秘（bot ID 8907007783）在群组发拼手气红包，
消息含「拼手气红包」关键字，内联键盘有「抢红包」按钮，
点击按钮抢红包。

可配置项（模块级常量）：
  - CLICK_DELAY: 点击前等待秒数（默认 0）
  - ALLOWED_GROUPS: 限定群组 ID 列表（空 = 所有群）
"""
import asyncio
import time
from core import tg, db, app
from scripts.filters import create_bot_filter
from scripts.notify import notify_owner


def _create_self_filter():
    """创建「自己的发言」过滤器（等价 filters.me，但显式可控）。"""
    async def is_self(_, __, m: tg.Message):
        return bool(m.from_user and m.from_user.is_self)

    return tg.filters.create(is_self)


self_filter = _create_self_filter()

# ─── 常量 ───────────────────────────────────────────────
BOT_ID = 8907007783              # 天空小秘 HDSKY（拼手气红包/转赠）
_CLICKED_TTL = 3600              # 去重 TTL（秒）
CLICK_DELAY = 0                  # 点击前等待秒数（可改为正数）
ALLOWED_GROUPS: list[int] = [-1001326208894]   # 限定群组（空=所有群），如 [-1001326208894]
INACTIVE_WAIT = 10               # 最近20条无发言时需等待的秒数（天空新规）

# ─── 去重缓存 ──────────────────────────────────────────
_clicked: dict[str, float] = {}  # "owner_id:chat_id:msg_id" → timestamp

# ─── 自身发言追踪（天空新规：最近20条无发言需等10秒）─────
_last_self_msg_id: dict[str, int] = {}  # "owner_id:chat_id" → msg_id


def _prune_clicked() -> None:
    """清理过期的去重记录。"""
    now = time.time()
    stale = [k for k, ts in _clicked.items() if now - ts > _CLICKED_TTL]
    for k in stale:
        _clicked.pop(k, None)


def _find_snatch_button(message: tg.Message) -> tuple[int, int] | None:
    """在消息内联键盘里找「抢红包」按钮，返回 (row, col) 或 None。"""
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return None
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
            text = getattr(btn, "text", "") or ""
            # 匹配「抢红包」「抢 红 包」「抢」「领取红包」等参与按钮文案
            if "抢红包" in text or "抢 红 包" in text or text.strip() in ("抢", "领取红包"):
                return (r, c)
    return None


def _is_lucky_packet(message: tg.Message) -> bool:
    """判断是否为拼手气红包消息。"""
    text = message.text or message.caption or ""
    # 关键特征：拼手气红包
    if "拼手气红包" in text:
        return True
    # 兜底：含「红包」且含份数/总银元/总金额
    if "红包" in text and ("份数" in text or "总银元" in text or "总金额" in text):
        return True
    return False


# ─── 自身发言追踪 Handler ────────────────────────────
@tg.Client.on_message(tg.filters.group & self_filter, group=-9)
async def track_self_message(client: tg.Client, message: tg.Message):
    """追踪自己在 ALLOWED_GROUPS 中最后一次发言的 msg_id，写入数据库防重启丢失。"""
    owner_id = getattr(client, "_owner_id", 0)
    app.logger.info(
        f"[天空红包] _track_self_message 触发 owner={owner_id} "
        f"chat={message.chat.id} msg={message.id}"
    )
    if not owner_id:
        app.logger.warning("[天空红包] _track_self_message 跳过：owner_id=0（Bot 账号）")
        return
    if ALLOWED_GROUPS and message.chat.id not in ALLOWED_GROUPS:
        app.logger.warning(
            f"[天空红包] _track_self_message 跳过：chat={message.chat.id} 不在 ALLOWED_GROUPS"
        )
        return
    chat_id = message.chat.id
    key = f"{owner_id}:{chat_id}"
    _last_self_msg_id[key] = message.id
    await db.set_setting(f"hdsky_last_msg:{chat_id}", str(message.id), owner_id=owner_id)
    app.logger.info(
        f"[天空红包] 记录自身发言 owner={owner_id} chat={chat_id} "
        f"msg_id={message.id}"
    )


# ─── Handler ──────────────────────────────────────────
@tg.Client.on_message(
    tg.filters.group
    & create_bot_filter(BOT_ID),
    group=-9,
)
async def snatch_hdsky_red_packet(client: tg.Client, message: tg.Message):
    """检测拼手气红包消息并点击「抢红包」按钮。"""
    # 仅 userbot 处理（Bot 账号没有 _owner_id）
    owner_id = getattr(client, "_owner_id", 0)
    if not owner_id:
        return

    # 群组过滤（空 = 所有群）
    if ALLOWED_GROUPS and message.chat.id not in ALLOWED_GROUPS:
        return

    if not _is_lucky_packet(message):
        return

    btn_pos = _find_snatch_button(message)
    if not btn_pos:
        app.logger.debug(f"[天空红包] 拼手气红包消息无「抢红包」按钮，跳过 msg={message.id}")
        return

    # 去重（按账号隔离）
    key = f"{owner_id}:{message.chat.id}:{message.id}"
    _prune_clicked()
    if key in _clicked:
        return
    _clicked[key] = time.time()

    # 活跃度检查（天空新规：最近20条无发言 → 等10秒）
    if ALLOWED_GROUPS:
        act_key = f"{owner_id}:{message.chat.id}"
        last_id = _last_self_msg_id.get(act_key)
        # 内存没有则从数据库恢复（重启后）
        if last_id is None:
            db_val = await db.get_setting(f"hdsky_last_msg:{message.chat.id}", owner_id=owner_id)
            if db_val:
                try:
                    last_id = int(db_val)
                    _last_self_msg_id[act_key] = last_id  # 回填内存
                except ValueError:
                    last_id = 0
            else:
                last_id = 0
        gap = message.id - last_id
        if gap >= 20:
            app.logger.info(
                f"[天空红包] msg_id 差={gap} >= 20，等待 {INACTIVE_WAIT}s 后抢包 "
                f"owner={owner_id} chat={message.chat.id} msg={message.id}"
            )
            await asyncio.sleep(INACTIVE_WAIT)
        else:
            app.logger.info(
                f"[天空红包] msg_id 差={gap} < 20，活跃中，立即抢包 "
                f"owner={owner_id} chat={message.chat.id} msg={message.id}"
            )

    # 可配置延迟
    if CLICK_DELAY > 0:
        await asyncio.sleep(CLICK_DELAY)

    row, col = btn_pos
    chat_title = getattr(message.chat, "title", "") if message.chat else ""
    msg_link = getattr(message, "link", "")

    try:
        result = await message.click(x=col, y=row, timeout=10)
        result_text = getattr(result, "message", None) or str(result)
        app.logger.info(f"[天空红包] 已点击抢红包 chat={message.chat.id} msg={message.id} 结果={result_text}")

        asyncio.create_task(
            notify_owner(
                "天空红包-已抢",
                icon="🧧",
                owner_id=owner_id,
                fields={
                    "🏠 所在群组": f"{chat_title}\n   群ID: {message.chat.id}",
                    "📩 抢包结果": result_text,
                    "🔗 消息链接": msg_link,
                },
            )
        )
    except Exception as e:
        app.logger.warning(f"[天空红包] 点击失败 chat={message.chat.id} msg={message.id}: {e}")
        asyncio.create_task(
            notify_owner(
                "天空红包-点击失败",
                icon="❌",
                owner_id=owner_id,
                fields={
                    "🏠 所在群组": f"{chat_title}\n   群ID: {message.chat.id}",
                    "⚠️ 错误信息": str(e),
                    "🔗 消息链接": msg_link,
                },
            )
        )
