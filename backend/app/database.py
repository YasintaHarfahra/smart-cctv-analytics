import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, text, Boolean
from sqlalchemy.dialects.postgresql import JSONB # Impor JSONB
from datetime import datetime

# Ambil variabel lingkungan dari Docker Compose
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set for backend service.")
    
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AnalyticsDataModel(Base):
    __tablename__ = "analytics_data" # HARUS SAMA dengan nama tabel di Supabase

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=text('now()')) # Gunakan text('now()') untuk Supabase
    object_type = Column(String)
    count = Column(Integer)
    area_name = Column(String)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "object_type": self.object_type,
            "count": self.count,
            "area_name": self.area_name
        }

# Tambahkan model SQLAlchemy baru untuk tabel camera_zones
class CameraZoneModel(Base):
    __tablename__ = "camera_zones"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True, unique=True)
    points = Column(JSONB)
    is_active = Column(Boolean, default=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "points": self.points,
            "is_active": self.is_active
        }