# Smart CCTV Analytics - Object Detection

## Fitur Object Detection

Sistem ini telah diintegrasikan dengan fitur object detection menggunakan YOLO (You Only Look Once) untuk mendeteksi objek secara real-time dari stream CCTV.

## Komponen yang Ditambahkan

### Backend
- **`object_detection.py`** - Module utama untuk object detection
- **WebSocket endpoints** - Real-time communication dengan frontend
- **YOLO integration** - Model AI untuk deteksi objek
- **OpenCV** - Video processing dan frame analysis

### Frontend
- **Detection Canvas** - Menampilkan bounding box dan label objek
- **Real-time Statistics** - Counter objek yang terdeteksi
- **WebSocket Connection** - Status koneksi detection
- **Control Buttons** - Start/Stop detection

## Cara Penggunaan

### 1. Start Backend
```bash
cd backend
pip install -r requirements.txt
python download_model.py  # Download YOLO model
uvicorn app.main:app --reload
```

### 2. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Akses Object Detection
1. Buka CCTV list
2. Pilih CCTV yang ingin dianalisis
3. Klik tombol **"Start Detection"**
4. Sistem akan mulai mendeteksi objek secara real-time

## Fitur Detection

### Real-time Object Detection
- Deteksi objek menggunakan YOLO v8
- Bounding box dengan warna berbeda untuk setiap class
- Confidence score untuk setiap deteksi
- Update real-time via WebSocket

### Object Counting
- Counter untuk setiap jenis objek
- Statistik real-time
- History deteksi

### Visual Display
- Side-by-side view: Video original + Detection overlay
- Canvas dengan bounding box dan label
- Color-coded objects
- Live detection info

## Model YOLO

### Default Classes
YOLO v8 dapat mendeteksi 80+ classes termasuk:
- **Kendaraan**: car, truck, bus, motorcycle, bicycle
- **Orang**: person
- **Hewan**: dog, cat, horse, cow, sheep
- **Objek**: chair, table, bottle, cup, book

### Custom Model
Untuk menggunakan model custom:
1. Place model file di folder `backend/`
2. Update `model_path` di `object_detection.py`
3. Restart backend

## Performance

### Optimizations
- Frame rate: ~30 FPS (configurable)
- GPU acceleration (jika tersedia)
- Efficient memory management
- WebSocket untuk real-time updates

### Resource Usage
- CPU: Moderate (dapat dioptimasi dengan GPU)
- Memory: ~500MB untuk model YOLO
- Network: Minimal (hanya WebSocket data)

## Troubleshooting

### Common Issues

#### 1. Model Download Failed
```bash
# Manual download
cd backend
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

#### 2. OpenCV Error
```bash
# Install system dependencies
sudo apt-get install libgl1-mesa-glx libglib2.0-0
```

#### 3. WebSocket Connection Failed
- Pastikan backend berjalan di port 8000
- Check firewall settings
- Verify CORS configuration

#### 4. Detection Not Working
- Check CCTV stream URL
- Verify WebSocket connection status
- Check backend logs untuk error

### Debug Mode
```python
# Di backend/app/object_detection.py
logging.basicConfig(level=logging.DEBUG)
```

## API Endpoints

### WebSocket
- `ws://localhost:8000/ws/detection/{cctv_id}` - Real-time detection

### REST API
- `GET /detection/stats` - Get detection statistics
- `POST /detection/stop` - Stop detection process

## Configuration

### Detection Settings
```python
# Di backend/app/object_detection.py
class CCTVObjectDetector:
    def __init__(self, model_path='yolov8n.pt'):
        # Customize model path
        self.model = YOLO(model_path)
    
    async def process_stream(self, stream_url, websocket=None):
        # Adjust frame rate
        await asyncio.sleep(0.033)  # 30 FPS
```

### Frontend Settings
```javascript
// Di frontend/src/views/cctvdetail.vue
const canvasWidth = ref(640)   // Canvas width
const canvasHeight = ref(360)  // Canvas height
```

## Future Enhancements

### Planned Features
- **Object Tracking** - Follow objects across frames
- **Alert System** - Notifications for specific objects
- **Recording** - Save frames with detections
- **Analytics Dashboard** - Historical data analysis
- **Multi-stream Support** - Process multiple CCTV simultaneously

### Custom Detection
- **Line Crossing Detection** - Count objects crossing virtual lines
- **Zone Detection** - Monitor specific areas
- **Behavior Analysis** - Unusual activity detection
- **License Plate Recognition** - Vehicle identification

## Support

Untuk bantuan teknis atau feature request, silakan buat issue di repository atau hubungi tim development.
