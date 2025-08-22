import cv2
import numpy as np
import tensorflow as tf
import time
import requests
import os
import collections
from datetime import datetime
from flask import Response, Flask
from imutils.video import VideoStream
import threading

# --- Konfigurasi ---
CCTV_STREAM_URL = os.getenv("CCTV_STREAM_URL", "0")
FASTAPI_ENDPOINT = os.getenv("FASTAPI_ENDPOINT", "http://backend:8000/analytics/")
MODEL_PATH = "app/models/yolov4-tiny.tflite"

CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

CONFIDENCE_THRESHOLD = 0.5
API_SEND_INTERVAL_SECONDS = 5

# --- Inisialisasi Model TensorFlow Lite ---
try:
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    print(f"TensorFlow Lite model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"ERROR: Could not load TFLite model from {MODEL_PATH}. Error: {e}")
    print("Please ensure the model file exists at the specified path and is valid.")
    exit(1)

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_shape = input_details[0]['shape']
input_height, input_width = input_shape[1], input_shape[2]

# --- Variabel Global untuk Streaming ---
outputFrame = None
lock = threading.Lock()

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)

# --- Fungsi untuk mengirim data ke FastAPI Backend ---
def send_to_fastapi(object_counts_per_frame):
    for obj_type, count in object_counts_per_frame.items():
        payload = {
            "object_type": obj_type,
            "count": count,
            "area_name": "KM Panorama Simpang"
        }
        try:
            response = requests.post(FASTAPI_ENDPOINT, json=payload, timeout=5)
            response.raise_for_status()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent '{obj_type}': {count} to FastAPI. Response: {response.json()}")
        except requests.exceptions.Timeout:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Request to FastAPI timed out for {obj_type}: {count}")
        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Failed to send data to FastAPI: {e}")

# --- Fungsi untuk Melakukan Deteksi Objek ---
def detect_thread():
    global outputFrame, lock

    if CCTV_STREAM_URL == "0":
        vs = VideoStream(src=0).start()
    else:
        vs = VideoStream(CCTV_STREAM_URL).start()

    time.sleep(2.0)

    last_api_send_time = time.time()

    while True:
        frame = vs.read()
        if frame is None:
            continue

        height, width, _ = frame.shape # <-- Variabel width dan height didefinisikan di sini
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(frame_rgb, (input_width, input_height))
        input_tensor = np.expand_dims(resized_frame, axis=0)
        input_tensor = input_tensor.astype(np.float32) / 255.0

        interpreter.set_tensor(input_details[0]['index'], input_tensor)
        interpreter.invoke()

        output_tensors = [interpreter.get_tensor(output_details[i]['index']) for i in range(len(output_details))]
        
        if len(output_tensors) == 4:
            boxes = output_tensors[0][0]
            classes = output_tensors[1][0]
            scores = output_tensors[2][0]
            num_detections = int(output_tensors[3][0])
        elif len(output_tensors) == 3:
            boxes, classes, scores = output_tensors[0][0], output_tensors[1][0], output_tensors[2][0]
            num_detections = len(scores)
        else:
            print("ERROR: Unsupported TFLite model output format. Expected 3 or 4 outputs.")
            continue
        
        object_counts_per_frame = collections.defaultdict(int)
        for i in range(num_detections):
            if scores[i] > CONFIDENCE_THRESHOLD:
                ymin, xmin, ymax, xmax = boxes[i]
                class_id = int(classes[i])
                class_name = CLASSES[class_id] if 0 <= class_id < len(CLASSES) else "unknown"

                object_counts_per_frame[class_name] += 1
                
                xmin_px, ymin_px = int(xmin * width), int(ymin * height)
                xmax_px, ymax_px = int(xmax * width), int(ymax * height)
                cv2.rectangle(frame, (xmin_px, ymin_px), (xmax_px, ymax_px), (0, 255, 0), 2)
                cv2.putText(frame, f"{class_name}: {scores[i]:.2f}", (xmin_px, ymin_px - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        current_time = time.time()
        if current_time - last_api_send_time >= API_SEND_INTERVAL_SECONDS:
            send_to_fastapi(object_counts_per_frame)
            last_api_send_time = current_time

        with lock:
            outputFrame = frame.copy()

# --- Fungsi untuk Streaming MJPEG ---
def generate():
    global outputFrame, lock

    while True:
        with lock:
            if outputFrame is None:
                continue

            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)

            if not flag:
                continue
        
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

# --- Endpoint Flask untuk Streaming ---
@app.route("/video_feed")
def video_feed():
    return Response(generate(), mimetype = "multipart/x-mixed-replace; boundary=frame")

# --- Main Thread untuk Menjalankan Flask Server dan Deteksi ---
if __name__ == "__main__":
    t = threading.Thread(target=detect_thread)
    t.daemon = True
    t.start()

    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)