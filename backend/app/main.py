from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import httpx
import json
import os
import logging
from urllib.parse import urljoin, quote, urlparse
import asyncio
import time
import sys
from typing import List, Dict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Try to import object detection module
try:
    from object_detection import detector
    logger.info("Object detection module imported successfully")
    DETECTOR_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import object detection module: {e}")
    DETECTOR_AVAILABLE = False
    # Create a mock detector
    class MockDetector:
        def stop(self):
            pass
        def get_statistics(self):
            return {"error": "Object detection not available"}
        def process_stream(self, url, websocket):
            return asyncio.sleep(1)
    
    detector = MockDetector()

app = FastAPI(title="Smart CCTV Analytics", version="1.0.0")
# Zones/virtual lines management endpoints
DB_AVAILABLE = True
try:
    from .database import get_db, CameraZoneModel, DetectionSessionModel, Base
    from .database import engine as _engine
    from sqlalchemy.orm import Session
    from fastapi import Depends
    from .schemas import CameraZoneCreate
    # Create tables if they don't exist
    try:
        Base.metadata.create_all(bind=_engine)
        logger.info("Database tables ensured (created if missing)")
    except Exception as _e:
        logger.warning(f"Failed to auto-create tables: {_e}")
except Exception as e:
    DB_AVAILABLE = False
    logger.warning(f"Database not available: {e}. Zone endpoints will be disabled.")


# Helper task: periodically persist live counts to the current session
async def _periodic_update_session_counts(session_id: int, camera_id: str):
    try:
        if not DB_AVAILABLE:
            return
        from .database import get_db
        from sqlalchemy import func
        while True:
            await asyncio.sleep(5)
            try:
                db = next(get_db())
                try:
                    row = db.query(DetectionSessionModel).filter(DetectionSessionModel.id == session_id).first()
                    if not row:
                        continue
                    counts = detector.camera_id_to_counts.get(camera_id, {}) or {}
                    row.counts = counts
                    # Update ended_at to the current database time to reflect last upload time
                    from sqlalchemy import func
                    row.ended_at = db.query(func.now()).scalar()
                    db.add(row)
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Periodic session update failed (id={session_id} cam={camera_id}): {e}")
    except asyncio.CancelledError:
        # Task cancelled when session ends
        pass
    except Exception as e:
        logger.warning(f"Periodic updater error: {e}")

@app.get("/zones/{camera_id}")
def get_zone(camera_id: str):
    if not DB_AVAILABLE:
        # Gracefully return an empty zone if DB isn't configured, to avoid frontend errors
        return {"camera_id": camera_id, "points": [], "is_active": False}
    from fastapi import Depends  # local import to avoid import at startup
    from sqlalchemy.orm import Session
    db: Session = next(get_db())
    try:
        zone = db.query(CameraZoneModel).filter(CameraZoneModel.camera_id == camera_id).first()
        if not zone:
            return {"camera_id": camera_id, "points": [], "is_active": False}
        return zone.to_dict()
    finally:
        db.close()

@app.post("/zones/{camera_id}")
def set_zone(camera_id: str, payload: dict):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured")
    from sqlalchemy.orm import Session
    db: Session = next(get_db())
    try:
        raw_points = payload.get("points", [])
        points = [{"x": float(p.get("x")), "y": float(p.get("y"))} for p in raw_points if p is not None]
        zone = db.query(CameraZoneModel).filter(CameraZoneModel.camera_id == camera_id).first()
        if zone:
            zone.points = points
            zone.is_active = True
        else:
            zone = CameraZoneModel(camera_id=camera_id, points=points, is_active=True)
            db.add(zone)
        db.commit()
        # Apply to detector immediately
        try:
            detector.set_virtual_line(camera_id, points)
        except Exception:
            pass
        return zone.to_dict()
    finally:
        db.close()

@app.delete("/zones/{camera_id}")
def clear_zone(camera_id: str):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured")
    from sqlalchemy.orm import Session
    db: Session = next(get_db())
    try:
        zone = db.query(CameraZoneModel).filter(CameraZoneModel.camera_id == camera_id).first()
        if zone:
            db.delete(zone)
            db.commit()
        try:
            detector.set_virtual_line(camera_id, [])
        except Exception:
            pass
        return {"camera_id": camera_id, "deleted": True}
    finally:
        db.close()

# Add a simple test route first
@app.get("/test-simple")
def test_simple():
    """Simple test endpoint"""
    return {"message": "Simple test working", "timestamp": time.time()}

origins = [
    "http://localhost",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CCTV_FILE = os.path.join(BASE_DIR, "cctv.json")

# Log startup information
logger.info(f"FastAPI app starting...")
logger.info(f"BASE_DIR: {BASE_DIR}")
logger.info(f"CCTV_FILE: {CCTV_FILE}")
logger.info(f"CCTV_FILE exists: {os.path.exists(CCTV_FILE)}")
logger.info(f"Detector available: {DETECTOR_AVAILABLE}")
logger.info(f"Python path: {sys.path[:3]}")


# Simple in-memory cache for CCTV data to avoid repeated disk I/O
_cctv_cache = {
    "data": None,
    "mtime": 0.0,
}

def _load_cctv_data_from_disk() -> dict:
    try:
        with open(CCTV_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse CCTV JSON: {je}")
            # Provide short preview to help debugging
            preview = text[:200].replace("\n", " ") if isinstance(text, str) else ""
            raise HTTPException(status_code=500, detail=f"Invalid CCTV JSON format: {je}. Preview: {preview}")

        # Accept either {"devices": [...]} or raw list [...]
        if isinstance(data, list):
            return {"devices": data}
        if not isinstance(data, dict):
            raise HTTPException(status_code=500, detail="Invalid CCTV config: not a JSON object")
        if "devices" not in data:
            # Try to infer: if there is a top-level key like "data" or similar
            for key in ("data", "items", "cameras"):
                if isinstance(data.get(key), list):
                    data = {"devices": data[key]}
                    break
        # Ensure devices exists as list
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            raise HTTPException(status_code=500, detail="Invalid CCTV config: 'devices' must be a list")
        return {"devices": devices}
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="CCTV configuration file not found")
    except Exception as e:
        logger.error(f"Unexpected error loading CCTV data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_cctv_data_cached() -> dict:
    try:
        mtime = os.path.getmtime(CCTV_FILE)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="CCTV configuration file not found")

    # Reload if cache is empty or file changed
    if not _cctv_cache["data"] or _cctv_cache["mtime"] != mtime:
        logger.info("Loading CCTV data into memory cache")
        _cctv_cache["data"] = _load_cctv_data_from_disk()
        _cctv_cache["mtime"] = mtime
    return _cctv_cache["data"]

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Smart CCTV Analytics API", "status": "running"}


@app.get("/cctv")
def get_cctv_list():
    try:
        data = get_cctv_data_cached()
        if not isinstance(data, dict):
            logger.error("Invalid CCTV config format (not dict)")
            return {"devices": []}
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            logger.error("Invalid CCTV config: 'devices' not list")
            devices = []
        return {"devices": devices}
    except HTTPException as e:
        logger.error(f"/cctv HTTPException: {e}")
        return {"devices": []}
    except Exception as e:
        logger.error(f"/cctv error: {e}")
        return {"devices": []}


@app.get("/cctv/{cctv_id}")
def get_cctv_detail(cctv_id: str):
    try:
        data = get_cctv_data_cached()
        devices = data.get("devices", []) if isinstance(data, dict) else []
        for c in devices:
            if c.get("id") == cctv_id:
                return c
        raise HTTPException(status_code=404, detail="CCTV not found")
    except HTTPException as e:
        logger.error(f"/cctv/{cctv_id} HTTPException: {e}")
        raise
    except Exception as e:
        logger.error(f"/cctv/{cctv_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "backend": "running",
        "websocket_support": True,
        "detector_available": DETECTOR_AVAILABLE
    }


# Debug endpoint untuk test WebSocket
@app.get("/debug/websocket")
def debug_websocket():
    """Debug endpoint untuk test WebSocket availability"""
    return {
        "message": "WebSocket endpoint available",
        "endpoints": [
            "/ws/detection/{cctv_id}",
            "/detection/stats",
            "/detection/stop"
        ],
        "cctv_file": CCTV_FILE,
        "cctv_file_exists": os.path.exists(CCTV_FILE),
        "detector_available": DETECTOR_AVAILABLE,
        "websocket_imports": {
            "fastapi": "FastAPI" in str(type(app)),
            "websocket": "WebSocket" in str(type(WebSocket)),
            "websocket_disconnect": "WebSocketDisconnect" in str(type(WebSocketDisconnect))
        }
    }


# Simple WebSocket test endpoint
@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Simple WebSocket test endpoint"""
    logger.info("=== WebSocket test connection attempt ===")
    
    try:
        await websocket.accept()
        logger.info("WebSocket test accepted successfully")
        
        # Send test message
        await websocket.send_text(json.dumps({
            "type": "test",
            "message": "WebSocket connection successful",
            "timestamp": time.time()
        }))
        logger.info("Test message sent successfully")
        
        # Keep connection alive for 10 seconds
        for i in range(10):
            await asyncio.sleep(1)
            try:
                await websocket.send_text(json.dumps({
                    "type": "heartbeat",
                    "count": i + 1,
                    "timestamp": time.time()
                }))
                logger.info(f"Heartbeat {i + 1} sent")
            except Exception as e:
                logger.error(f"Failed to send heartbeat {i + 1}: {e}")
                break
        
        logger.info("WebSocket test completed successfully")
        
    except WebSocketDisconnect as disconnect_error:
        logger.info(f"WebSocket test disconnected: {disconnect_error.code}")
    except Exception as e:
        logger.error(f"WebSocket test error: {e}")
    
    logger.info("=== WebSocket test handler completed ===")


# WebSocket endpoint untuk object detection
@app.websocket("/ws/detection/{cctv_id}")
async def websocket_detection(websocket: WebSocket, cctv_id: str):
    logger.info(f"=== WebSocket connection attempt for CCTV: {cctv_id} ===")
    
    try:
        # Accept connection
        await websocket.accept()
        logger.info(f"WebSocket accepted for CCTV: {cctv_id}")
        
        # Test connection dengan ping
        try:
            ping_message = json.dumps({
                "type": "ping",
                "message": "Connection established",
                "timestamp": time.time()
            })
            logger.info(f"Sending ping message: {ping_message}")
            
            await websocket.send_text(ping_message)
            logger.info(f"Ping sent successfully to CCTV: {cctv_id}")
            
        except Exception as ping_error:
            logger.error(f"Failed to send ping to CCTV {cctv_id}: {ping_error}")
            return
        
        # Ambil data CCTV
        try:
            logger.info(f"Reading CCTV file: {CCTV_FILE}")
            
            if not os.path.exists(CCTV_FILE):
                logger.error(f"CCTV file not found: {CCTV_FILE}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "CCTV configuration file not found"
                }))
                return
            
            with open(CCTV_FILE, "r") as f:
                data = json.load(f)
            
            devices = data.get("devices", [])
            logger.info(f"Found {len(devices)} devices in CCTV file")
            
            cctv = None
            for c in devices:
                if c.get("id") == cctv_id:
                    cctv = c
                    break
            
            if not cctv or not cctv.get("link"):
                logger.error(f"CCTV not found or no stream URL for ID: {cctv_id}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "CCTV not found or no stream URL"
                }))
                return
            
            logger.info(f"Found CCTV: {cctv.get('name', cctv_id)}")
            logger.info(f"Stream URL: {cctv.get('link')}")

            # Buat session detection di DB (Supabase)
            session_id = None
            periodic_task = None
            try:
                if DB_AVAILABLE:
                    from .database import get_db
                    db = next(get_db())
                    try:
                        session_row = DetectionSessionModel(
                            camera_id=cctv_id,
                            camera_name=cctv.get('name') or cctv_id,
                            counts={}
                        )
                        db.add(session_row)
                        db.commit()
                        db.refresh(session_row)
                        session_id = session_row.id
                        logger.info(f"Detection session started id={session_id} for camera {cctv_id}")
                        # Mulai periodic updater agar counts tersimpan selama sesi berjalan
                        periodic_task = asyncio.create_task(_periodic_update_session_counts(session_id, cctv_id))
                    finally:
                        db.close()
            except Exception as s_err:
                logger.warning(f"Failed to create detection session: {s_err}")
            
            # Resolve virtual line: prefer DB zone, fallback ke cctv.json line_coordinate
            line_points = []
            all_lines = []
            try:
                if DB_AVAILABLE:
                    # Lazy import and session usage
                    from .database import get_db, CameraZoneModel as _CZ
                    db = next(get_db())
                    try:
                        zone = db.query(_CZ).filter(_CZ.camera_id == cctv_id).first()
                        if zone and isinstance(zone.points, list):
                            # Ambil satu garis saja
                            if len(zone.points) >= 2 and isinstance(zone.points[0], dict):
                                line_points = zone.points[:2]
                            elif len(zone.points) > 0 and isinstance(zone.points[0], list):
                                for ln in zone.points:
                                    if isinstance(ln, list) and len(ln) >= 2 and isinstance(ln[0], dict):
                                        line_points = ln[:2]
                                        break
                        # Apply single line to detector jika ada
                        if line_points:
                            try:
                                detector.set_virtual_line(cctv_id, line_points)
                            except Exception:
                                pass
                    finally:
                        db.close()
            except Exception as e:
                logger.warning(f"Zone DB lookup failed for {cctv_id}: {e}")

            # Fallback to config file attribute if no DB zone
            if not line_points:
                try:
                    raw = cctv.get('line_coordinate')
                    if isinstance(raw, str) and raw.strip():
                        arr = json.loads(raw)
                        if isinstance(arr, list) and len(arr) > 0:
                            # Pilih kandidat terbaik: yang punya active:true, atau line_name mengandung 'count/hitung', jika tidak ada ambil pertama
                            def to_points(item):
                                return [
                                    {"x": float(item["startX"]), "y": float(item["startY"])},
                                    {"x": float(item["endX"]), "y": float(item["endY"])},
                                ]
                            # Build all valid lines
                            all_lines = [to_points(it) for it in arr if isinstance(it, dict) and all(k in it for k in ("startX","startY","endX","endY"))]
                            candidate = None
                            # 1) active:true
                            for it in arr:
                                if isinstance(it, dict) and all(k in it for k in ("startX","startY","endX","endY")) and it.get("active") is True:
                                    candidate = it
                                    break
                            # 2) line_name keyword
                            if candidate is None:
                                for it in arr:
                                    if not isinstance(it, dict):
                                        continue
                                    name = str(it.get("line_name", "")).lower()
                                    if any(key in name for key in ("count","hitung","main")) and all(k in it for k in ("startX","startY","endX","endY")):
                                        candidate = it
                                        break
                            # 3) first valid
                            if candidate is None:
                                for it in arr:
                                    if isinstance(it, dict) and all(k in it for k in ("startX","startY","endX","endY")):
                                        candidate = it
                                        break
                            if candidate is not None:
                                line_points = to_points(candidate)
                            # Terapkan hanya satu garis ke detector
                            if line_points:
                                try:
                                    detector.set_virtual_line(cctv_id, line_points)
                                except Exception:
                                    pass
                except Exception as e:
                    logger.warning(f"Failed to parse line_coordinate for {cctv_id}: {e}")

            # Kirim info CCTV termasuk line_points jika ada
            cctv_with_line = dict(cctv)
            if line_points:
                cctv_with_line["line_points"] = line_points
            # Jangan kirim all_lines agar hanya satu yang digambar di frontend
            cctv_info = json.dumps({
                "type": "cctv_info",
                "data": cctv_with_line
            })
            logger.info(f"Sending CCTV info: {cctv_info}")
            
            await websocket.send_text(cctv_info)
            logger.info(f"CCTV info sent for: {cctv_id}")
            
            # Mulai object detection dalam background task
            logger.info(f"Creating detection task for CCTV: {cctv_id}")
            
            if DETECTOR_AVAILABLE:
                detection_task = asyncio.create_task(
                    detector.process_stream(cctv["link"], websocket, camera_id=cctv_id)
                )
                logger.info(f"Detection task created for CCTV: {cctv_id}")
                
                # Tunggu task selesai atau WebSocket disconnect
                try:
                    logger.info(f"Waiting for detection task to complete...")
                    await detection_task
                    logger.info(f"Detection task completed for CCTV: {cctv_id}")
                except asyncio.CancelledError:
                    logger.info(f"Detection task cancelled for CCTV: {cctv_id}")
                except Exception as e:
                    logger.error(f"Detection task error for CCTV {cctv_id}: {e}")
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Detection error: {str(e)}"
                        }))
                    except Exception as send_error:
                        logger.error(f"Failed to send error message: {send_error}")
                finally:
                    # Tutup session dengan menyimpan hasil counts terakhir
                    try:
                        if DB_AVAILABLE and session_id is not None:
                            from .database import get_db
                            db = next(get_db())
                            try:
                                row = db.query(DetectionSessionModel).filter(DetectionSessionModel.id == session_id).first()
                                if row:
                                    # Ambil counts dari detector untuk kamera ini
                                    counts = detector.camera_id_to_counts.get(cctv_id, {}) or {}
                                    row.counts = counts
                                    # Set ended_at ke now() lewat db
                                    from sqlalchemy import func
                                    row.ended_at = db.query(func.now()).scalar()
                                    db.add(row)
                                    db.commit()
                                    logger.info(f"Detection session closed id={session_id} for camera {cctv_id}")
                            finally:
                                db.close()
                        # Hentikan periodic updater
                        if periodic_task:
                            periodic_task.cancel()
                    except Exception as close_err:
                        logger.warning(f"Failed to close detection session: {close_err}")
            else:
                logger.info(f"Using mock detector for CCTV: {cctv_id}")
                # Send mock detections with keep-alive
                while True:
                    try:
                        await asyncio.sleep(2)  # Send every 2 seconds
                        
                        # Send keep-alive ping
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "ping",
                                "message": "keep-alive",
                                "timestamp": time.time()
                            }))
                        except Exception as ping_error:
                            logger.error(f"Keep-alive ping failed: {ping_error}")
                            break
                        
                        # Send mock detection data
                        mock_data = {
                            "type": "detection_results",
                            "timestamp": time.time(),
                            "objects": [
                                {
                                    "label": "person",
                                    "confidence": 85.5,
                                    "bbox": [100, 100, 50, 150],
                                    "class_id": 0,
                                    "timestamp": time.time(),
                                    "color": "#FF0000"
                                }
                            ],
                            "counters": {"person": 1},
                            "total_objects": 1
                        }
                        await websocket.send_text(json.dumps(mock_data))
                        logger.info(f"Mock detection sent for CCTV: {cctv_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to send mock detection: {e}")
                        break
            
        except FileNotFoundError as file_error:
            logger.error(f"CCTV file not found: {file_error}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "CCTV configuration file not found"
            }))
        except json.JSONDecodeError as json_error:
            logger.error(f"Invalid CCTV file format: {json_error}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Invalid CCTV configuration format"
            }))
        except Exception as cctv_error:
            logger.error(f"Error reading CCTV data: {cctv_error}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Error reading CCTV data: {str(cctv_error)}"
            }))
        
    except WebSocketDisconnect as disconnect_error:
        logger.info(f"WebSocket disconnected for CCTV: {cctv_id}")
        logger.info(f"Disconnect code: {disconnect_error.code}")
        logger.info(f"Disconnect reason: {disconnect_error.reason}")
        detector.stop()
    except Exception as e:
        logger.error(f"WebSocket error for CCTV {cctv_id}: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass  # WebSocket mungkin sudah closed
        detector.stop()
    
    logger.info(f"=== WebSocket handler completed for CCTV: {cctv_id} ===")


# Endpoint untuk mendapatkan statistik detection
@app.get("/detection/stats")
def get_detection_stats():
    return detector.get_statistics()


# Endpoint untuk menghentikan detection
@app.post("/detection/stop")
def stop_detection():
    detector.stop()
    return {"message": "Detection stopped"}

# Debug endpoints
@app.post("/detection/debug/overlay")
def toggle_debug_overlay(enabled: bool = True):
    """Toggle debug overlay for visual verification"""
    detector.enable_debug_overlay(enabled)
    return {"message": f"Debug overlay {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/debug/logging")
def toggle_debug_logging(enabled: bool = True):
    """Toggle debug logging for coordinates and frame info"""
    detector.enable_debug_logging(enabled)
    return {"message": f"Debug logging {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/coordinates")
def use_original_coordinates(enabled: bool = True):
    """Use original video coordinates instead of resized frame coordinates"""
    detector.use_original_video_coordinates(enabled)
    return {"message": f"Using original video coordinates: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/resize")
def toggle_frame_resize(disabled: bool = True):
    """Disable/enable frame resize to use original video dimensions"""
    detector.disable_frame_resize(disabled)
    return {"message": f"Frame resize {'disabled' if disabled else 'enabled'}"}

@app.post("/detection/validation")
def toggle_coordinate_validation(enabled: bool = True):
    """Enable/disable coordinate validation"""
    detector.enable_coordinate_validation(enabled)
    return {"message": f"Coordinate validation {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/force-original")
def force_original_video_size(enabled: bool = True):
    """Force using original video size for all operations"""
    detector.force_original_video_size(enabled)
    return {"message": f"Force original video size: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/auto-fix")
def toggle_auto_fix_coordinates(enabled: bool = True):
    """Enable/disable automatic coordinate fixing"""
    detector.enable_auto_fix_coordinates(enabled)
    return {"message": f"Auto fix coordinates: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/smart-fix")
def toggle_smart_coordinate_fix(enabled: bool = True):
    """Enable/disable smart coordinate fixing"""
    detector.enable_smart_coordinate_fix(enabled)
    return {"message": f"Smart coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/adaptive-fix")
def toggle_adaptive_coordinate_fix(enabled: bool = True):
    """Enable/disable adaptive coordinate fixing"""
    detector.enable_adaptive_coordinate_fix(enabled)
    return {"message": f"Adaptive coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/intelligent-fix")
def toggle_intelligent_coordinate_fix(enabled: bool = True):
    """Enable/disable intelligent coordinate fixing"""
    detector.enable_intelligent_coordinate_fix(enabled)
    return {"message": f"Intelligent coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/ultimate-fix")
def toggle_ultimate_coordinate_fix(enabled: bool = True):
    """Enable/disable ultimate coordinate fixing"""
    detector.enable_ultimate_coordinate_fix(enabled)
    return {"message": f"Ultimate coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/mega-fix")
def toggle_mega_coordinate_fix(enabled: bool = True):
    """Enable/disable mega coordinate fixing"""
    detector.enable_mega_coordinate_fix(enabled)
    return {"message": f"Mega coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/super-fix")
def toggle_super_coordinate_fix(enabled: bool = True):
    """Enable/disable super coordinate fixing"""
    detector.enable_super_coordinate_fix(enabled)
    return {"message": f"Super coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/hyper-fix")
def toggle_hyper_coordinate_fix(enabled: bool = True):
    """Enable/disable hyper coordinate fixing"""
    detector.enable_hyper_coordinate_fix(enabled)
    return {"message": f"Hyper coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/ultra-fix")
def toggle_ultra_coordinate_fix(enabled: bool = True):
    """Enable/disable ultra coordinate fixing"""
    detector.enable_ultra_coordinate_fix(enabled)
    return {"message": f"Ultra coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/epic-fix")
def toggle_epic_coordinate_fix(enabled: bool = True):
    """Enable/disable epic coordinate fixing"""
    detector.enable_epic_coordinate_fix(enabled)
    return {"message": f"Epic coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/legendary-fix")
def toggle_legendary_coordinate_fix(enabled: bool = True):
    """Enable/disable legendary coordinate fixing"""
    detector.enable_legendary_coordinate_fix(enabled)
    return {"message": f"Legendary coordinate fix: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/force-no-resize")
def toggle_force_no_resize(enabled: bool = True):
    """Force no resize at all - use original video size"""
    detector.enable_force_no_resize(enabled)
    return {"message": f"Force no resize: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/raw-coordinates")
def toggle_raw_coordinates(enabled: bool = True):
    """Use raw coordinates without any scaling"""
    detector.enable_raw_coordinates(enabled)
    return {"message": f"Raw coordinates: {'enabled' if enabled else 'disabled'}"}

@app.post("/detection/config")
def update_detection_config(
    frame_skip: int = None,
    target_width: int = None,
    buffer_grab_count: int = None,
    smoothing_enabled: bool = None,
    smoothing_alpha: float = None,
    use_original_coordinates: bool = None,
    disable_resize: bool = None,
    coordinate_validation: bool = None,
    force_original_size: bool = None,
    auto_fix_coordinates: bool = None,
    smart_coordinate_fix: bool = None,
    adaptive_coordinate_fix: bool = None,
    intelligent_coordinate_fix: bool = None,
    ultimate_coordinate_fix: bool = None,
    mega_coordinate_fix: bool = None,
    super_coordinate_fix: bool = None,
    hyper_coordinate_fix: bool = None,
    ultra_coordinate_fix: bool = None,
    epic_coordinate_fix: bool = None,
    legendary_coordinate_fix: bool = None,
    force_no_resize: bool = None,
    use_raw_coordinates: bool = None,
    conf_threshold: float = None,
    iou_threshold: float = None,
    labels: str = None,
    model_path: str = None
):
    """Update detection configuration parameters"""
    if frame_skip is not None:
        detector.frame_skip = max(1, int(frame_skip))
    if target_width is not None:
        detector.target_width = int(target_width) if target_width > 0 else None
    if buffer_grab_count is not None:
        detector.buffer_grab_count = max(0, int(buffer_grab_count))
    if smoothing_enabled is not None:
        detector.smoothing_enabled = bool(smoothing_enabled)
    if smoothing_alpha is not None:
        detector.smoothing_alpha = max(0.0, min(1.0, float(smoothing_alpha)))
    if use_original_coordinates is not None:
        detector.use_original_coordinates = bool(use_original_coordinates)
    if disable_resize is not None:
        detector.disable_resize = bool(disable_resize)
    if coordinate_validation is not None:
        detector.coordinate_validation = bool(coordinate_validation)
    if force_original_size is not None:
        detector.force_original_size = bool(force_original_size)
    if auto_fix_coordinates is not None:
        detector.auto_fix_coordinates = bool(auto_fix_coordinates)
    if smart_coordinate_fix is not None:
        detector.smart_coordinate_fix = bool(smart_coordinate_fix)
    if adaptive_coordinate_fix is not None:
        detector.adaptive_coordinate_fix = bool(adaptive_coordinate_fix)
    if intelligent_coordinate_fix is not None:
        detector.intelligent_coordinate_fix = bool(intelligent_coordinate_fix)
    if ultimate_coordinate_fix is not None:
        detector.ultimate_coordinate_fix = bool(ultimate_coordinate_fix)
    if mega_coordinate_fix is not None:
        detector.mega_coordinate_fix = bool(mega_coordinate_fix)
    if super_coordinate_fix is not None:
        detector.super_coordinate_fix = bool(super_coordinate_fix)
    if hyper_coordinate_fix is not None:
        detector.hyper_coordinate_fix = bool(hyper_coordinate_fix)
    if ultra_coordinate_fix is not None:
        detector.ultra_coordinate_fix = bool(ultra_coordinate_fix)
    if epic_coordinate_fix is not None:
        detector.epic_coordinate_fix = bool(epic_coordinate_fix)
    if legendary_coordinate_fix is not None:
        detector.legendary_coordinate_fix = bool(legendary_coordinate_fix)
    if force_no_resize is not None:
        detector.force_no_resize = bool(force_no_resize)
    if use_raw_coordinates is not None:
        detector.use_raw_coordinates = bool(use_raw_coordinates)
    
    if conf_threshold is not None:
        detector.set_conf_threshold(conf_threshold)
    if iou_threshold is not None:
        detector.set_iou_threshold(iou_threshold)
    if labels is not None:
        try:
            arr = [s.strip() for s in labels.split(',') if s.strip()]
            detector.set_allowed_labels(arr)
        except Exception:
            pass
    if model_path:
        detector.load_model(model_path)

    return {
        "message": "Detection configuration updated",
        "config": {
            "frame_skip": detector.frame_skip,
            "target_width": detector.target_width,
            "buffer_grab_count": detector.buffer_grab_count,
            "smoothing_enabled": detector.smoothing_enabled,
            "smoothing_alpha": detector.smoothing_alpha,
            "use_original_coordinates": detector.use_original_coordinates,
            "disable_resize": detector.disable_resize,
            "coordinate_validation": detector.coordinate_validation,
            "force_original_size": detector.force_original_size,
            "auto_fix_coordinates": detector.auto_fix_coordinates,
            "smart_coordinate_fix": detector.smart_coordinate_fix,
            "adaptive_coordinate_fix": detector.adaptive_coordinate_fix,
            "intelligent_coordinate_fix": detector.intelligent_coordinate_fix,
            "ultimate_coordinate_fix": detector.ultimate_coordinate_fix,
            "mega_coordinate_fix": detector.mega_coordinate_fix,
            "super_coordinate_fix": detector.super_coordinate_fix,
            "hyper_coordinate_fix": detector.hyper_coordinate_fix,
            "ultra_coordinate_fix": detector.ultra_coordinate_fix,
            "epic_coordinate_fix": detector.epic_coordinate_fix,
            "legendary_coordinate_fix": detector.legendary_coordinate_fix,
            "force_no_resize": detector.force_no_resize,
            "use_raw_coordinates": detector.use_raw_coordinates,
            "conf_threshold": detector.conf_threshold,
            "iou_threshold": detector.iou_threshold,
            "allowed_labels": sorted(list(getattr(detector, 'allowed_labels', [])))
        }
    }


# 🔥 Proxy untuk streaming HLS (.m3u8 + .ts segments)
@app.get("/proxy")
async def proxy_stream(url: str):
    # Be tolerant to upstream TLS/cert issues and redirects often present in CCTV origins
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=None, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }) as client:
        try:
            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail="Failed to fetch stream")

            content_type = r.headers.get("content-type", "application/octet-stream")

            # Kalau file playlist (.m3u8) → rewrite semua URI agar lewat proxy
            if url.endswith(".m3u8"):
                try:
                    text = r.text
                    # Gunakan URL upstream yang diminta klien agar resolve relatif benar
                    base_url = str(url)

                    def rewrite_line(line: str) -> str:
                        line_stripped = line.strip()
                        if not line_stripped or line_stripped.startswith('#'):
                            # Rewrites for lines with URI attributes in tags (#EXT-X-KEY, #EXT-X-MAP)
                            if line_stripped.startswith('#EXT-X-KEY') or line_stripped.startswith('#EXT-X-MAP'):
                                # Find URI="..."
                                prefix = 'URI="'
                                if 'URI="' in line_stripped:
                                    start = line_stripped.index(prefix) + len(prefix)
                                    end = line_stripped.find('"', start)
                                    if end != -1:
                                        uri_value = line_stripped[start:end]
                                        # Koreksi jika origin keliru menjadi localhost:3001/api/
                                        parsed = urlparse(uri_value)
                                        candidate = uri_value
                                        if parsed.scheme in ("http", "https"):
                                            if parsed.netloc in ("localhost:3001", "127.0.0.1:3001") and parsed.path.startswith("/api/"):
                                                candidate = parsed.path.replace("/api/", "", 1)
                                        elif uri_value.startswith("/api/"):
                                            candidate = uri_value.replace("/api/", "", 1)

                                        absolute = urljoin(base_url, candidate)
                                        proxied = '/api/proxy?url=' + quote(absolute, safe='')
                                        return line_stripped[:start] + proxied + line_stripped[end:]
                            return line

                        # For URI lines (variants or segments)
                        candidate = line_stripped
                        parsed = urlparse(candidate)
                        if parsed.scheme in ("http", "https"):
                            if parsed.netloc in ("localhost:3001", "127.0.0.1:3001") and parsed.path.startswith("/api/"):
                                candidate = parsed.path.replace("/api/", "", 1)
                        elif candidate.startswith("/api/"):
                            candidate = candidate.replace("/api/", "", 1)

                        absolute = urljoin(base_url, candidate)
                        proxied = '/api/proxy?url=' + quote(absolute, safe='')
                        return proxied + ('\n' if line.endswith('\n') else '')

                    # Apply rewrite per line
                    rewritten_lines = []
                    for ln in text.splitlines(keepends=True):
                        rewritten_lines.append(rewrite_line(ln))
                    rewritten = ''.join(rewritten_lines)

                    return Response(
                        content=rewritten,
                        media_type="application/vnd.apple.mpegurl",
                        headers={
                            "Cache-Control": "no-cache, no-store, must-revalidate"
                        }
                    )
                except Exception as rewrite_error:
                    # Fallback: return original if rewrite fails
                    return Response(content=r.content, media_type="application/vnd.apple.mpegurl")

            # Kalau file segment video (.ts atau lainnya), stream langsung
            return StreamingResponse(r.aiter_bytes(), media_type=content_type)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
