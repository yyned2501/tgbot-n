from typing import Optional
from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, Integer, Numeric, DateTime, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BonusLog(Base):
    """
    通用 PT 站点魔力值变动流水模型 (魔力日志)
    """
    __tablename__ = "bonus_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    website: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 站点名称，如 "zhuque", "ptvicomo", "redleaves"

    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 行为类型，如 "redpocket" (抢红包), "pie" (馅饼), "transfer_in" (转账收入) 等

    amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False
    )  # 魔力值变动数额（正数为增加，负数为消耗）

    tag: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # 附加备注信息

    message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )  # 关联的 Telegram 消息 ID

    owner_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="所属账号的 Telegram User ID"
    )
