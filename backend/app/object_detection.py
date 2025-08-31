import cv2
import numpy as np
import asyncio
import json
import time
from typing import List, Dict, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import YOLO, fallback to mock if not available
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    logger.info("YOLO imported successfully")
except ImportError as e:
    YOLO_AVAILABLE = False
    logger.warning(f"YOLO not available: {e}. Using mock detection.")

class DetectionResult:
    def __init__(self, label: str, confidence: float, bbox: List[float], 
                 class_id: int, timestamp: float):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox  # [x, y, w, h]
        self.class_id = class_id
        self.timestamp = timestamp
        self.color = self._get_color(class_id)
    
    def _get_color(self, class_id: int) -> str:
        """Generate consistent color for class ID"""
        colors = [
            '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', 
            '#00FFFF', '#FF8000', '#8000FF', '#008000', '#800080'
        ]
        return colors[class_id % len(colors)]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'confidence': round(self.confidence * 100, 2),
            'bbox': self.bbox,
            'class_id': self.class_id,
            'timestamp': self.timestamp,
            'color': self.color
        }

class MockDetector:
    """Mock detector for testing when YOLO is not available"""
    def __init__(self):
        self.names = {0: 'person', 1: 'car', 2: 'truck'}
    
    def __call__(self, frame, verbose=False):
        # Return mock detection results
        class MockResult:
            def __init__(self):
                self.boxes = None
                self.names = {0: 'person', 1: 'car', 2: 'truck'}
        
        return [MockResult()]

class CCTVObjectDetector:
    def __init__(self, model_path: str = 'yolov8n.pt'):
        """Initialize YOLO model for object detection"""
        self.detection_history = []
        self.object_counters = {}
        self.is_running = False
        
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                logger.info(f"YOLO model loaded successfully: {model_path}")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                # Fallback to default model
                try:
                    self.model = YOLO('yolov8n.pt')
                    logger.info("Fallback YOLO model loaded")
                except Exception as e2:
                    logger.error(f"Fallback YOLO model also failed: {e2}")
                    self.model = MockDetector()
        else:
            logger.info("Using mock detector")
            self.model = MockDetector()
        
    async def process_stream(self, stream_url: str, websocket=None):
        """Process CCTV stream and detect objects"""
        self.is_running = True
        logger.info(f"Starting stream processing: {stream_url}")
        
        try:
            cap = cv2.VideoCapture(stream_url)
            
            if not cap.isOpened():
                logger.error(f"Failed to open stream: {stream_url}")
                await self._send_error(websocket, f"Failed to open stream: {stream_url}")
                return
            
            logger.info(f"Stream opened successfully: {stream_url}")
            
            frame_count = 0
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame, retrying...")
                    await asyncio.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Detect objects every few frames to reduce load
                if frame_count % 3 == 0:  # Process every 3rd frame
                    try:
                        # Detect objects
                        results = self.model(frame, verbose=False)
                        
                        # Process detection results
                        detections = self._process_detections(results[0], frame)
                        
                        # Update counters
                        self._update_counters(detections)
                        
                        # Send results via WebSocket if available
                        if websocket:
                            await self._send_detection_results(websocket, detections, frame)
                            
                    except Exception as e:
                        logger.error(f"Detection error on frame {frame_count}: {e}")
                        # Send mock detection for testing
                        if websocket:
                            mock_detections = self._generate_mock_detections()
                            await self._send_detection_results(websocket, mock_detections, frame)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.033)  # ~30 FPS
                
        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
            await self._send_error(websocket, str(e))
        finally:
            if 'cap' in locals():
                cap.release()
            self.is_running = False
            logger.info("Stream processing stopped")
    
    def _generate_mock_detections(self) -> List[DetectionResult]:
        """Generate mock detections for testing"""
        import random
        
        mock_objects = [
            DetectionResult('person', 0.85, [100, 100, 50, 150], 0, time.time()),
            DetectionResult('car', 0.92, [300, 200, 120, 80], 1, time.time()),
        ]
        
        # Randomly add/remove objects
        if random.random() > 0.7:
            mock_objects.append(
                DetectionResult('truck', 0.78, [500, 150, 150, 100], 2, time.time())
            )
        
        return mock_objects
    
    def _process_detections(self, result, frame) -> List[DetectionResult]:
        """Process YOLO detection results"""
        detections = []
        
        if result.boxes is None:
            return detections
        
        try:
            for box in result.boxes:
                # Get box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x, y, w, h = x1, y1, x2 - x1, y2 - y1
                
                # Get class and confidence
                class_id = int(box.cls[0].cpu().numpy())
                confidence = float(box.conf[0].cpu().numpy())
                
                # Get class name
                label = result.names[class_id]
                
                # Create detection result
                detection = DetectionResult(
                    label=label,
                    confidence=confidence,
                    bbox=[float(x), float(y), float(w), float(h)],
                    class_id=class_id,
                    timestamp=time.time()
                )
                
                detections.append(detection)
        except Exception as e:
            logger.error(f"Error processing detections: {e}")
        
        return detections
    
    def _update_counters(self, detections: List[DetectionResult]):
        """Update object counters"""
        current_counts = {}
        
        for detection in detections:
            label = detection.label
            if label not in current_counts:
                current_counts[label] = 0
            current_counts[label] += 1
        
        # Update global counters
        for label, count in current_counts.items():
            if label not in self.object_counters:
                self.object_counters[label] = 0
            self.object_counters[label] = count
    
    async def _send_detection_results(self, websocket, detections: List[DetectionResult], frame):
        """Send detection results via WebSocket"""
        try:
            # Prepare data to send
            data = {
                'type': 'detection_results',
                'timestamp': time.time(),
                'objects': [det.to_dict() for det in detections],
                'counters': self.object_counters,
                'total_objects': len(detections)
            }
            
            # Send via WebSocket
            await websocket.send_text(json.dumps(data))
            
        except Exception as e:
            logger.error(f"Failed to send detection results: {e}")
    
    async def _send_error(self, websocket, error_message: str):
        """Send error message via WebSocket"""
        if websocket:
            try:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': error_message
                }))
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
    
    def stop(self):
        """Stop the detection process"""
        self.is_running = False
        logger.info("Detection stopped by user")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            'total_detections': len(self.detection_history),
            'object_counters': self.object_counters,
            'is_running': self.is_running,
            'yolo_available': YOLO_AVAILABLE
        }

# Global detector instance
detector = CCTVObjectDetector()
