from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Text, func
from .base import Base


class UserAccount(Base):
    """
    用户账号模型
    存储多个人形账号的登录信息和状态
    """
    __tablename__ = "user_accounts"

    owner_id = Column(BigInteger, primary_key=True, comment="用户的 Telegram User ID（主键）")
    phone = Column(String(20), unique=True, nullable=False, comment="手机号，用户可读标识")
    session_string = Column(Text, nullable=False, comment="Pyrogram Session String")
    is_active = Column(Boolean, default=True, comment="是否启用（启动时自动连接）")
    is_connected = Column(Boolean, default=False, comment="当前是否在线")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
