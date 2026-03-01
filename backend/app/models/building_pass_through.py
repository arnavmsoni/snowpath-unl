from sqlalchemy import Column, Integer, String, Boolean, Text
from app.models.base import Base

class BuildingPassThrough(Base):
    __tablename__ = "building_pass_through"

    id = Column(Integer, primary_key=True, index=True)
    building_osm_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    enabled = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
