from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any

# Pydantic Models untuk data analitik CCTV
# Model ini digunakan untuk memvalidasi data yang masuk dari detektor objek
class AnalyticsDataCreate(BaseModel):
    object_type: str
    count: int
    area_name: str

# Model ini digunakan untuk data yang akan ditampilkan di frontend
# Ia mewarisi AnalyticsDataCreate dan menambahkan id serta timestamp
class AnalyticsData(AnalyticsDataCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Pydantic Models untuk konfigurasi zona kamera
# Model ini digunakan untuk memvalidasi koordinat titik zona
class CameraZonePoint(BaseModel):
    x: float
    y: float

# Model ini digunakan untuk memvalidasi data zona saat dibuat/diperbarui
class CameraZoneCreate(BaseModel):
    camera_id: str
    points: List[CameraZonePoint]

# Model ini digunakan untuk data zona saat diambil dari database
# Ia mewarisi CameraZoneCreate dan menambahkan id serta status aktif
class CameraZone(CameraZoneCreate):
    id: int
    is_active: bool