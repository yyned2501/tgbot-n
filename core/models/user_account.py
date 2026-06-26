from datetime import datetime

from sqlalchemy import String, BigInteger, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserAccount(Base):
    """
    用户账号模型
    存储多个人形账号的登录信息和状态
    """
    __tablename__ = "user_accounts"

    owner_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="用户的 Telegram User ID（主键）"
    )
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="手机号，用户可读标识"
    )
    session_string: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Pyrogram Session String"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用（启动时自动连接）"
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="当前是否在线"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
