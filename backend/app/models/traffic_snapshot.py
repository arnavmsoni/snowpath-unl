from sqlalchemy import Column, Integer, Float, DateTime, String
from app.models.base import Base

class TrafficSnapshot(Base):
    __tablename__ = "traffic_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)  # "synthetic"
    captured_at = Column(DateTime, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    intensity = Column(Float, nullable=False)  # 0..1