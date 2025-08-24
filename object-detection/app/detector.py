import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter
import time
import requests
import os
import collections
from datetime import datetime
from flask import Response, Flask
from imutils.video import VideoStream
import threading

# --- Konfigurasi ---
CCTV_STREAM_URL = os.getenv("CCTV_STREAM_URL", "https://mam.jogjaprov.go.id:1937/cctv-bantul/TPRParangtritis.stream/chunklist_w307863718.m3u8")
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
    interpreter = Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    print(f"TensorFlow Lite model loaded successfully from {MODEL_PATH}")

    # Debug model information
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"Model input details: {len(input_details)} inputs")
    for i, detail in enumerate(input_details):
        print(f"  Input {i}: {detail['name']} - Shape: {detail['shape']}")

    print(f"Model output details: {len(output_details)} outputs")
    for i, detail in enumerate(output_details):
        print(f"  Output {i}: {detail['name']} - Shape: {detail['shape']}")

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
        except ValueError: # Handle non-JSON responses
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent '{obj_type}': {count} to FastAPI. (Non-JSON response)")

# --- Fungsi untuk Melakukan Deteksi Objek ---
def detect_thread():
    global outputFrame, lock

    if CCTV_STREAM_URL == "0":
        print("INFO: Attempting to open default webcam (index 0)...")
        vs = VideoStream(src=0).start()
    else:
        print(f"INFO: Attempting to open video stream from: {CCTV_STREAM_URL}")
        vs = VideoStream(CCTV_STREAM_URL).start()

    time.sleep(2.0)
    print("INFO: Video stream opened and ready for processing.")

    last_api_send_time = time.time()

    while True:
        frame = vs.read()
        if frame is None:
            print("WARNING: Failed to grab frame. Skipping...")
            time.sleep(0.1) # Brief pause before retrying
            continue

        height, width, _ = frame.shape
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(frame_rgb, (input_width, input_height))
        input_tensor = np.expand_dims(resized_frame, axis=0)
        input_tensor = input_tensor.astype(np.float32) / 255.0

        interpreter.set_tensor(input_details[0]['index'], input_tensor)
        interpreter.invoke()

        # --- Adapted for your model's specific output structure ---
        # Output 0: shape=[1, 2535, 4] -> boxes [ymin, xmin, ymax, xmax]
        # Output 1: shape=[1, 2535, 1] -> likely class IDs or confidence scores
        boxes = interpreter.get_tensor(output_details[0]['index'])[0]
        classes_or_scores = interpreter.get_tensor(output_details[1]['index'])[0]

        object_counts_per_frame = collections.defaultdict(int)

        # Interpret the second output based on its structure
        if classes_or_scores.shape[1] == 1:
            # Assume it contains confidence scores for a single class (e.g., 'person')
            scores = classes_or_scores.flatten() # Shape becomes [2535]

            for i in range(len(scores)):
                if scores[i] > CONFIDENCE_THRESHOLD:
                    # Extract bounding box coordinates
                    ymin, xmin, ymax, xmax = boxes[i]

                    # Assign a default class name (adjust if needed)
                    class_name = "person" # Or determine from your model's specifics

                    object_counts_per_frame[class_name] += 1

                    # Draw bounding box and label on the frame
                    xmin_px, ymin_px = int(xmin * width), int(ymin * height)
                    xmax_px, ymax_px = int(xmax * width), int(ymax * height)
                    cv2.rectangle(frame, (xmin_px, ymin_px), (xmax_px, ymax_px), (0, 255, 0), 2)
                    cv2.putText(frame, f"{class_name}: {scores[i]:.2f}", (xmin_px, ymin_px - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            # If it's not [2535, 1], it might be class IDs. Handle accordingly.
            # This is a simplified fallback; you might need to adjust based on your model.
            print(f"Unexpected structure for output 1: {classes_or_scores.shape}")
            # You could add logic here to handle other structures if needed.

        # Kirim data ke FastAPI secara periodik
        current_time = time.time()
        if current_time - last_api_send_time >= API_SEND_INTERVAL_SECONDS and object_counts_per_frame:
            send_to_fastapi(object_counts_per_frame)
            last_api_send_time = current_time

        # Perbarui frame global untuk streaming
        with lock:
            outputFrame = frame.copy()

# --- Fungsi untuk Streaming MJPEG ---
def generate():
    global outputFrame, lock

    while True:
        with lock:
            if outputFrame is None:
                # Small delay to prevent busy-waiting
                time.sleep(0.01)
                continue

            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)

            if not flag:
                time.sleep(0.01)
                continue

        # Yield the frame in MJPEG format
        yield(b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' +
              bytearray(encodedImage) +
              b'\r\n')

# --- Endpoint Flask untuk Streaming ---
@app.route("/video_feed")
def video_feed():
    return Response(generate(), mimetype = "multipart/x-mixed-replace; boundary=frame")

# --- Main Thread untuk Menjalankan Flask Server dan Deteksi ---
if __name__ == "__main__":
    # Start the detection thread
    t = threading.Thread(target=detect_thread)
    t.daemon = True # Dies when main thread dies
    t.start()
    print("INFO: Detection thread started.")

    # Start the Flask web server
    print("INFO: Starting Flask server on http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
