from sqlalchemy import Column, Integer, Float, DateTime, String, Text
from sqlalchemy.sql import func
from app.models.base import Base

class UserReport(Base):
    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    segment_key = Column(String, nullable=True)
    rating = Column(Integer, nullable=True)
    report_type = Column(String, nullable=False)  # cleared, icy, blocked, door_access, door_locked
    note = Column(Text, nullable=True)
