from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    base_shelf_life_days = Column(Integer, nullable=False)
    optimal_temp_c = Column(Float, nullable=False)

    batches = relationship("Batch", back_populates="product")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    production_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    current_status = Column(String(50), nullable=False)

    product = relationship("Product", back_populates="batches")
    telemetry = relationship("Telemetry", back_populates="batch")


class Telemetry(Base):
    __tablename__ = "telemetry"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    temperature_c = Column(Float)
    humidity = Column(Float)
    spoilage_risk_score = Column(Float)

    batch = relationship("Batch", back_populates="telemetry")
