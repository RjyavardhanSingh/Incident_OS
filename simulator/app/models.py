from sqlalchemy import BigInteger, Column, Integer, String

from app.db import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"schema": "demo"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="pending")


class InventoryItem(Base):
    __tablename__ = "inventory"
    __table_args__ = {"schema": "demo"}

    sku = Column(String(64), primary_key=True)
    stock = Column(Integer, nullable=False, default=100)
