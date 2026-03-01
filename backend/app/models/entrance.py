from sqlalchemy import Column, Integer, String, Float, Boolean
from app.models.base import Base

class Entrance(Base):
    __tablename__ = "entrances"

    id = Column(Integer, primary_key=True, index=True)
    building_osm_id = Column(String, nullable=True)
    name = Column(String, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)
    is_accessible = Column(Boolean, default=True, nullable=False)
