from sqlalchemy import Column, Integer, DateTime, BigInteger
from .base import Base

class ZhuqueResult(Base):
    """
    Zhuque 压大小结果模型
    """

    __tablename__ = "zhuque_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    final_result = Column(Integer)  # 1 为大, 0 为小
    big_total = Column(BigInteger)  # 押大合计金额
    small_total = Column(BigInteger)  # 押小合计金额
    created_at = Column(DateTime)  # 游戏创建时间
    settlement_time = Column(DateTime)  # 游戏结算时间
