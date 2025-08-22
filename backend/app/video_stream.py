import cv2
from app.model import detect_objects

# Ganti URL dengan stream CCTV kamu
# Contoh: "rtsp://username:password@ip:554/Streaming/Channels/101"
CCTV_URL = "https://restreamer.kotabogor.go.id/memfs/1dd9dac0-e6db-40b6-ae39-59717fdeeeb7.m3u8"  

cap = cv2.VideoCapture(CCTV_URL)

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break

        # Deteksi objek di frame
        frame, detections = detect_objects(frame)

        # Encode jadi JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        # Streaming ke browser
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
