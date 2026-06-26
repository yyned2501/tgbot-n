from typing import Optional

from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SystemSetting(Base):
    """
    通用系统设置模型

    owner_id=0 为全局设置，>0 为按账号隔离的设置。
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=0)
    value: Mapped[Optional[str]] = mapped_column(String(500))
