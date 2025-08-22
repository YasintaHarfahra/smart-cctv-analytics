from sqlalchemy.orm import Session
from .database import CameraZoneModel

def get_camera_zone(db: Session, camera_id: str):
    return db.query(CameraZoneModel).filter(CameraZoneModel.camera_id == camera_id).first()

def get_all_camera_zones(db: Session):
    return db.query(CameraZoneModel).all()

def create_or_update_camera_zone(db: Session, camera_id: str, points: list):
    zone = get_camera_zone(db, camera_id)
    if zone:
        zone.points = points
        db.commit()
        db.refresh(zone)
    else:
        zone = CameraZoneModel(camera_id=camera_id, points=points)
        db.add(zone)
        db.commit()
        db.refresh(zone)
    return zone