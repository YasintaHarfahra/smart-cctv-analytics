import cv2
import numpy as np
import tensorflow as tf
import requests
import time

# 🔹 RTSP / m3u8 stream (Bogor)
VIDEO_URL = "https://restreamer.kotabogor.go.id/memfs/1dd9dac0-e6db-40b6-ae39-59717fdeeeb7.m3u8"

# 🔹 Load TFLite model
MODEL_PATH = "models/custom/detect.tflite"
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# 🔹 API backend (sesuaikan dengan app.py backend-mu)
BACKEND_API = "http://localhost:5000/api/detections"

# Fungsi untuk melakukan preprocessing gambar
def preprocess(frame):
    h, w = input_details[0]['shape'][1:3]  # biasanya [1, 300, 300, 3] / [1, 320, 320, 3]
    resized = cv2.resize(frame, (w, h))
    normalized = resized / 255.0
    input_data = np.expand_dims(normalized.astype(np.float32), axis=0)
    return input_data

# Loop membaca video
cap = cv2.VideoCapture(VIDEO_URL)

if not cap.isOpened():
    print("❌ Gagal membuka stream:", VIDEO_URL)
    exit()

print("✅ Stream terbuka, mulai deteksi...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️ Gagal membaca frame, retry...")
        time.sleep(1)
        continue

    # Preprocess
    input_data = preprocess(frame)

    # Inference
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    # Ambil hasil deteksi
    boxes = interpreter.get_tensor(output_details[0]['index'])[0]  # [N,4]
    classes = interpreter.get_tensor(output_details[1]['index'])[0]  # [N]
    scores = interpreter.get_tensor(output_details[2]['index'])[0]  # [N]

    h, w, _ = frame.shape
    detections = []
    count_objects = 0

    for i in range(len(scores)):
        if scores[i] > 0.5:  # threshold 50%
            ymin, xmin, ymax, xmax = boxes[i]
            xmin, xmax = int(xmin * w), int(xmax * w)
            ymin, ymax = int(ymin * h), int(ymax * h)

            label = int(classes[i])
            conf = float(scores[i])

            detections.append({
                "label": label,
                "confidence": round(conf, 2),
                "box": [xmin, ymin, xmax, ymax]
            })
            count_objects += 1

            # Gambarkan bounding box di frame
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{label} {conf:.2f}", (xmin, ymin - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Kirim hasil ke backend API (supaya frontend bisa baca)
    try:
        payload = {
            "timestamp": time.time(),
            "count": count_objects,
            "detections": detections
        }
        requests.post(BACKEND_API, json=payload, timeout=1)
    except Exception as e:
        print("⚠️ Gagal kirim data ke backend:", e)

    # Tampilkan jendela preview (opsional, boleh dimatikan di server)
    cv2.imshow("Deteksi CCTV", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
