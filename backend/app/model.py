import cv2
from ultralytics import YOLO

# Load YOLO model (bisa diganti dengan model custom)
model = YOLO("yolov8n.pt")  # kecil & cepat

def detect_objects(video_source):
    cap = cv2.VideoCapture(video_source)

    if not cap.isOpened():
        print("❌ Tidak bisa membuka sumber video:", video_source)
        return

    while True:
        success, frame = cap.read()
        if not success:
            cap.release()
            cap = cv2.VideoCapture(video_source)  # coba reconnect
            continue

        # Deteksi objek
        results = model(frame, stream=True)

        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])  # bounding box
                conf = float(box.conf[0])              # confidence
                cls = int(box.cls[0])                  # class id
                label = model.names[cls]

                detections.append({
                    "label": label,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2]
                })

                # Gambar kotak di frame
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"{label} {conf:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        yield frame, detections
