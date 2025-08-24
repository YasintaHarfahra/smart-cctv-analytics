import os
import cv2
import threading
import time
from fastapi import FastAPI, Response, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Tambahan import untuk error yang muncul
from typing import List
from sqlalchemy.orm import Session

from . import crud
from .schemas import AnalyticsData, AnalyticsDataCreate
from .database import get_db

# --- Inisialisasi Aplikasi FastAPI ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]  # Add this line
)

# --- Variabel Global untuk Streaming ---
CCTV_STREAM_URL = "https://mam.jogjaprov.go.id:1937/cctv-bantul/TPRParangtritis.stream/chunklist_w307863718.m3u8"

outputFrame = None
lock = threading.Lock()
video_stream = None

# --- Fungsi untuk Membuka dan Membaca Stream Video ---
def video_stream_reader():
    global outputFrame, lock, video_stream

    vs = cv2.VideoCapture(CCTV_STREAM_URL, cv2.CAP_FFMPEG)

    if not vs.isOpened():
        print(f"❌ Error: Gagal membuka stream video dari {CCTV_STREAM_URL}")
        return

    while True:
        success, frame = vs.read()
        if not success:
            print("❌ Error: Gagal membaca frame dari stream.")
            break

        with lock:
            outputFrame = frame.copy()

    vs.release()

# --- Fungsi untuk Menyajikan Frame sebagai Streaming MJPEG ---
def generate():
    global outputFrame, lock

    while True:
        with lock:
            if outputFrame is None:
                continue

            ret, buffer = cv2.imencode(".jpg", outputFrame)
            if not ret:
                continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

# --- Endpoint FastAPI untuk Streaming ---
@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# --- Endpoint Health Check ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

# --- Endpoint utama (root) ---
@app.get("/")
def root():
    return {
        "message": "CCTV Streaming API",
        "routes": {
            "/video_feed": "Streaming MJPEG",
            "/health": "Health check"
        },
        "video_source": CCTV_STREAM_URL
    }

# Endpoint untuk menerima data analitik deteksi objek
@app.post("/analytics/", response_model=AnalyticsData)
def create_analytics_data(data: AnalyticsDataCreate, db: Session = Depends(get_db)):
    return crud.create_analytics_data(db=db, data=data)

# Endpoint untuk mengambil data analitik deteksi objek
@app.get("/analytics/", response_model=List[AnalyticsData])
def read_analytics_data(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    data = crud.get_analytics_data(db, skip=skip, limit=limit)
    return data

# --- Jalankan Thread Video Stream ---
@app.on_event("startup")
async def startup_event():
    global video_stream
    video_stream = threading.Thread(target=video_stream_reader)
    video_stream.daemon = True
    video_stream.start()
