from sqlalchemy.orm import Session
from .database import AnalyticsDataModel
from .schemas import AnalyticsDataCreate 

def create_analytics_data(db: Session, data: AnalyticsDataCreate):
    db_data = AnalyticsDataModel(
        object_type=data.object_type,
        count=data.count,
        area_name=data.area_name
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data

def get_analytics_data(db: Session, skip: int = 0, limit: int = 100):
    # Urutkan berdasarkan timestamp terbaru
    return db.query(AnalyticsDataModel).offset(skip).limit(limit).all()