from typing import Optional
from datetime import datetime

from sqlalchemy import Integer, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ZhuqueResult(Base):
    """
    Zhuque 压大小结果模型
    """
    __tablename__ = "zhuque_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    final_result: Mapped[Optional[int]] = mapped_column(Integer)  # 1 为大, 0 为小
    big_total: Mapped[Optional[int]] = mapped_column(BigInteger)  # 押大合计金额
    small_total: Mapped[Optional[int]] = mapped_column(BigInteger)  # 押小合计金额
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, unique=True
    )  # 游戏创建时间（唯一，防止多账号重复入库）
    settlement_time: Mapped[Optional[datetime]] = mapped_column(DateTime)  # 游戏结算时间
