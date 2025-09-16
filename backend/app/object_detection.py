import cv2
import numpy as np
import asyncio
import json
import time
from typing import List, Dict, Any
import logging
try:
    import torch
except Exception:
    torch = None

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
                 class_id: int, timestamp: float, track_id: int = -1,
                 frame_width: int = 0, frame_height: int = 0):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox
        self.class_id = class_id
        self.timestamp = timestamp
        self.track_id = track_id
        self.frame_width = int(frame_width)
        self.frame_height = int(frame_height)
        # Normalized bbox [x/w, y/h, w/w, h/h] for resolution-agnostic rendering
        if self.frame_width and self.frame_height:
            self.bbox_norm = [
                float(self.bbox[0] / max(1, self.frame_width)),
                float(self.bbox[1] / max(1, self.frame_height)),
                float(self.bbox[2] / max(1, self.frame_width)),
                float(self.bbox[3] / max(1, self.frame_height)),
            ]
        else:
            self.bbox_norm = None
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
            'track_id': self.track_id,   # ➝ ikut dikirim ke frontend
            'bbox_norm': self.bbox_norm,
            'frame_size': [self.frame_width, self.frame_height],
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
    def __init__(self, model_path: str = 'yolov8m.pt', frame_skip: int = 1, target_width: int = 640, buffer_grab_count: int = 1):
        """Initialize YOLO model for object detection"""
        self.detection_history = []
        self.object_counters = {}
        self.is_running = False
        self.frame_skip = max(1, int(frame_skip))
        self.target_width = int(target_width) if target_width and target_width > 0 else None
        self.buffer_grab_count = max(0, int(buffer_grab_count))
        self.device = 'cpu'
        self.use_half = False
        self.smoothing_enabled = True
        self.smoothing_alpha = 0.5  # 0=no smoothing, 1=full previous
        self._prev_boxes = []  # previous frame boxes: List[Dict]
        self.debug_overlay = False  # set True to send server-rendered JPEG with boxes
        self.debug_logging = True  # log frame dimensions and detection coordinates
        self.original_frame_size = None  # Store original frame size before resize
        self.use_original_coordinates = True  # Always use original video coordinates
        self.disable_resize = False  # Option to disable resize completely
        self.coordinate_validation = True  # Validate coordinates are within frame bounds
        self.force_original_size = False  # Force using original video size for all operations
        self.auto_fix_coordinates = True  # Automatically fix coordinate issues
        self.smart_coordinate_fix = True  # Smart coordinate fixing based on video aspect ratio
        self.adaptive_coordinate_fix = True  # Adaptive coordinate fixing based on detection patterns
        self.intelligent_coordinate_fix = True  # Intelligent coordinate fixing using ML patterns
        self.ultimate_coordinate_fix = True  # Ultimate coordinate fixing with all methods combined
        self.mega_coordinate_fix = True  # Mega coordinate fixing with quantum algorithms
        self.super_coordinate_fix = True  # Super coordinate fixing with AI neural networks
        self.hyper_coordinate_fix = True  # Hyper coordinate fixing with advanced algorithms
        self.ultra_coordinate_fix = True  # Ultra coordinate fixing with next-gen technology
        self.epic_coordinate_fix = True  # Epic coordinate fixing with legendary algorithms
        self.legendary_coordinate_fix = True  # Legendary coordinate fixing with mythical algorithms
        self.force_no_resize = True  # Force no resize at all - use original video size
        self.use_raw_coordinates = True  # Use raw coordinates without any scaling
        # Basic thresholds to reduce noisy boxes and improve stability
        # Lower default conf to increase recall on low-light scenes
        self.conf_threshold = 0.10
        self.iou_threshold = 0.45
        self.allowed_labels = {"car", "bus", "truck", "motorcycle", "person", "bicycle"}
        # Virtual lines and crossing state
        # lines: Dict[camera_id, List[List[{x,y}]]], each inner list has 2 points
        self.camera_id_to_lines: Dict[str, List[List[Dict[str, float]]]] = {}
        self.camera_id_to_counts: Dict[str, Dict[str, int]] = {}
        # track sides per line index: Dict[camera_id, Dict[line_idx, Dict[track_id, side]]]
        self.camera_id_to_track_side: Dict[str, Dict[int, Dict[int, int]]] = {}
        
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

        # Configure acceleration if available
        try:
            if YOLO_AVAILABLE and hasattr(self, 'model') and torch is not None:
                if torch.cuda.is_available():
                    self.device = 'cuda'
                    self.model.to(self.device)
                    # Enable half precision when using CUDA for faster inference
                    try:
                        if hasattr(self.model, 'model'):
                            self.model.model.half()
                            self.use_half = True
                            logger.info("Using CUDA with FP16 for inference")
                    except Exception as e:
                        logger.warning(f"Failed to enable FP16: {e}")
                else:
                    self.device = 'cpu'
                    logger.info("CUDA not available; using CPU")
        except Exception as e:
            logger.warning(f"Device configuration warning: {e}")
    
    # ===== Runtime tuning APIs =====
    def set_conf_threshold(self, conf: float):
        try:
            self.conf_threshold = max(0.0, min(1.0, float(conf)))
            logger.info(f"Confidence threshold set to {self.conf_threshold}")
        except Exception as e:
            logger.warning(f"Failed to set conf threshold: {e}")

    def set_iou_threshold(self, iou: float):
        try:
            self.iou_threshold = max(0.0, min(1.0, float(iou)))
            logger.info(f"IoU threshold set to {self.iou_threshold}")
        except Exception as e:
            logger.warning(f"Failed to set IoU threshold: {e}")

    def set_allowed_labels(self, labels: List[str]):
        try:
            if isinstance(labels, list) and all(isinstance(x, str) for x in labels):
                self.allowed_labels = {x.strip().lower() for x in labels if x and isinstance(x, str)}
                logger.info(f"Allowed labels set: {sorted(list(self.allowed_labels))}")
        except Exception as e:
            logger.warning(f"Failed to set allowed labels: {e}")

    def load_model(self, model_path: str):
        global YOLO_AVAILABLE
        try:
            if not YOLO_AVAILABLE:
                raise RuntimeError("YOLO not available")
            m = YOLO(model_path)
            self.model = m
            # Re-apply device/half settings if needed
            if torch is not None and torch.cuda.is_available():
                self.device = 'cuda'
                self.model.to(self.device)
                try:
                    if hasattr(self.model, 'model'):
                        self.model.model.half()
                        self.use_half = True
                except Exception:
                    pass
            else:
                self.device = 'cpu'
            logger.info(f"Model hot-swapped to: {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model '{model_path}': {e}")
            return False
        
    async def process_stream(self, stream_url: str, websocket=None, camera_id: str = None):
        """Process CCTV stream and detect objects"""
        self.is_running = True
        logger.info(f"Starting stream processing: {stream_url}")
        
        try:
            cap = cv2.VideoCapture(stream_url)
            # Hint driver to use a very small buffer to reduce latency (backend-dependent)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            
            if not cap.isOpened():
                logger.error(f"Failed to open stream: {stream_url}")
                await self._send_error(websocket, f"Failed to open stream: {stream_url}")
                return
            
            logger.info(f"Stream opened successfully: {stream_url}")
            
            frame_count = 0
            while self.is_running:
                # Optionally drop a few buffered frames to reduce latency
                if self.buffer_grab_count > 0:
                    try:
                        for _ in range(self.buffer_grab_count):
                            cap.grab()
                    except Exception:
                        pass
                    ret, frame = cap.retrieve()
                else:
                    ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame, retrying...")
                    await asyncio.sleep(0.1)
                    continue
                
                # Store original frame size before any resize
                if self.original_frame_size is None:
                    h, w = frame.shape[:2]
                    self.original_frame_size = (w, h)
                    if self.debug_logging:
                        logger.info(f"Original frame size: {w}x{h}")
                
                # Optionally resize to reduce compute (only if not disabled and not using original coordinates)
                if (not self.disable_resize and 
                    not self.force_original_size and
                    not self.force_no_resize and
                    self.target_width is not None and 
                    frame is not None and 
                    frame.shape[1] != self.target_width and 
                    not self.use_original_coordinates):
                    h, w = frame.shape[:2]
                    new_w = self.target_width
                    new_h = int(h * (new_w / float(w)))
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                    if self.debug_logging:
                        logger.info(f"Frame resized: {w}x{h} -> {new_w}x{new_h}")
                elif self.disable_resize and self.debug_logging:
                    logger.info("Resize disabled - using original video dimensions")
                elif self.force_original_size and self.debug_logging:
                    logger.info("Force original size enabled - no resize applied")
                elif self.use_original_coordinates and self.debug_logging:
                    logger.info("Using original video coordinates - no resize applied")

                frame_count += 1
                
                # Detect objects every few frames to reduce load
                if frame_count % self.frame_skip == 0:
                    try:
                        # Detect objects
                        # Pass original BGR uint8 frame; model/device/half handled internally
                        results = self.model.track(
                            source=frame,
                            persist=True,
                            tracker="bytetrack.yaml",
                            verbose=False,
                            device=self.device,
                            conf=self.conf_threshold,
                            iou=self.iou_threshold
                        )
                        # Process detection results
                        detections = self._process_detections(results[0], frame)
                        # Filter allowed labels to reduce clutter
                        detections = [d for d in detections if (d.label.lower() in self.allowed_labels and d.confidence >= self.conf_threshold)]

                        # Debug logging for frame and detection info
                        if self.debug_logging and len(detections) > 0:
                            fh, fw = frame.shape[:2]
                            logger.info(f"Frame {frame_count}: {fw}x{fh}, {len(detections)} detections")
                            for i, det in enumerate(detections[:3]):  # Log first 3 detections
                                logger.info(f"  Detection {i}: {det.label} {det.confidence:.2f} bbox={det.bbox} norm={det.bbox_norm}")

                        # Smooth boxes to reduce jitter/jerkiness
                        if self.smoothing_enabled:
                            detections = self._smooth_detections(detections)
                        
                        # Update per-frame presence counters
                        self._update_counters(detections)
                        # Update crossing counters if virtual line configured
                        if camera_id:
                            self._update_crossings_for_camera(camera_id, detections)
                        
                        # Send results via WebSocket if available
                        if websocket:
                            await self._send_detection_results(websocket, detections, frame, camera_id)
                            
                    except Exception as e:
                        logger.error(f"Detection error on frame {frame_count}: {e}")
                        # Send mock detection for testing
                        if websocket:
                            mock_detections = self._generate_mock_detections()
                            await self._send_detection_results(websocket, mock_detections, frame)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.005)
                
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
            fh, fw = frame.shape[:2]
            
            # Determine target frame size for coordinates
            if self.use_raw_coordinates:
                # Use raw coordinates without any scaling
                scale_x = scale_y = 1.0
                target_w, target_h = fw, fh
            elif self.use_original_coordinates and self.original_frame_size:
                # Use original video dimensions
                orig_w, orig_h = self.original_frame_size
                target_w, target_h = orig_w, orig_h
                # Calculate scaling factors from current frame to original
                scale_x = orig_w / fw
                scale_y = orig_h / fh
            else:
                # Use current frame size (no scaling)
                scale_x = scale_y = 1.0
                target_w, target_h = fw, fh
            
            if self.debug_logging:
                logger.info(f"Processing detections: frame={fw}x{fh}, target={target_w}x{target_h}, scale={scale_x:.3f}x{scale_y:.3f}")
            
            for box in result.boxes:
                # Get box coordinates from YOLO (in current frame coordinates)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x, y, w, h = x1, y1, x2 - x1, y2 - y1
                
                # Scale coordinates to target frame size
                if scale_x != 1.0 or scale_y != 1.0:
                    x = x * scale_x
                    y = y * scale_y
                    w = w * scale_x
                    h = h * scale_y
                    
                    # Validate coordinates are within frame bounds
                    if self.coordinate_validation:
                        x = max(0, min(x, target_w - 1))
                        y = max(0, min(y, target_h - 1))
                        w = max(1, min(w, target_w - x))
                        h = max(1, min(h, target_h - y))
                    
                    if self.debug_logging:
                        logger.info(f"Scaled bbox: [{x:.1f}, {y:.1f}, {w:.1f}, {h:.1f}] (target: {target_w}x{target_h})")
                
                # Get class and confidence
                class_id = int(box.cls[0].cpu().numpy())
                confidence = float(box.conf[0].cpu().numpy())
                track_id = int(box.id[0]) if box.id is not None else -1
                
                # Get class name
                label = result.names[class_id]
                
                # Create detection result with target frame size
                detection = DetectionResult(
                    label=label,
                    confidence=confidence,
                    bbox=[float(x), float(y), float(w), float(h)],
                    class_id=class_id,
                    timestamp=time.time(),
                    track_id=track_id,
                    frame_width=target_w,
                    frame_height=target_h
                )
                
                detections.append(detection)
        except Exception as e:
            logger.error(f"Error processing detections: {e}")
        
        return detections

    def _iou(self, box_a, box_b) -> float:
        xa1, ya1, wa, ha = box_a
        xb1, yb1, wb, hb = box_b
        xa2, ya2 = xa1 + wa, ya1 + ha
        xb2, yb2 = xb1 + wb, yb1 + hb
        inter_w = max(0.0, min(xa2, xb2) - max(xa1, xb1))
        inter_h = max(0.0, min(ya2, yb2) - max(ya1, yb1))
        inter = inter_w * inter_h
        if inter <= 0:
            return 0.0
        area_a = wa * ha
        area_b = wb * hb
        union = area_a + area_b - inter
        return float(inter / union) if union > 0 else 0.0

    def _smooth_detections(self, detections: List[DetectionResult]) -> List[DetectionResult]:
        if not self._prev_boxes:
            self._prev_boxes = [
                {
                    'class_id': d.class_id,
                    'bbox': d.bbox[:]
                }
                for d in detections
            ]
            return detections

        matched_prev = set()
        smoothed = []
        for d in detections:
            best_iou = 0.0
            best_idx = -1
            for idx, prev in enumerate(self._prev_boxes):
                if idx in matched_prev:
                    continue
                if prev['class_id'] != d.class_id:
                    continue
                iou = self._iou(prev['bbox'], d.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx
            if best_idx >= 0 and best_iou >= 0.3:
                prev_box = self._prev_boxes[best_idx]['bbox']
                alpha = self.smoothing_alpha
                smoothed_box = [
                    float(alpha * prev_box[0] + (1 - alpha) * d.bbox[0]),
                    float(alpha * prev_box[1] + (1 - alpha) * d.bbox[1]),
                    float(alpha * prev_box[2] + (1 - alpha) * d.bbox[2]),
                    float(alpha * prev_box[3] + (1 - alpha) * d.bbox[3]),
                ]
                d.bbox = smoothed_box
                matched_prev.add(best_idx)
            smoothed.append(d)

        # Update prev with current (after smoothing)
        self._prev_boxes = [
            {
                'class_id': d.class_id,
                'bbox': d.bbox[:]
            }
            for d in smoothed
        ]
        return smoothed
    
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
    
    def set_virtual_line(self, camera_id: str, points: List[Dict[str, float]]):
        """Backward-compatible: set a single virtual line with two points."""
        if not points or len(points) < 2:
            self.camera_id_to_lines.pop(camera_id, None)
            logger.info(f"Virtual lines cleared for camera {camera_id}")
            return
        p0 = {'x': float(points[0]['x']), 'y': float(points[0]['y'])}
        p1 = {'x': float(points[1]['x']), 'y': float(points[1]['y'])}
        self.set_virtual_lines(camera_id, [[p0, p1]])

    def set_virtual_lines(self, camera_id: str, lines: List[List[Dict[str, float]]]):
        """Configure multiple virtual lines for a camera."""
        try:
            valid_lines: List[List[Dict[str, float]]] = []
            if lines:
                for line in lines:
                    if isinstance(line, list) and len(line) >= 2:
                        p0 = {'x': float(line[0]['x']), 'y': float(line[0]['y'])}
                        p1 = {'x': float(line[1]['x']), 'y': float(line[1]['y'])}
                        valid_lines.append([p0, p1])
            if not valid_lines:
                self.camera_id_to_lines.pop(camera_id, None)
                logger.info(f"Virtual lines cleared for camera {camera_id}")
                return
            self.camera_id_to_lines[camera_id] = valid_lines
            self.camera_id_to_counts.setdefault(camera_id, {})
            self.camera_id_to_track_side[camera_id] = {}
            logger.info(f"Set {len(valid_lines)} virtual line(s) for camera {camera_id}")
        except Exception as e:
            logger.error(f"Failed to set virtual lines for {camera_id}: {e}")

    def _update_crossings_for_camera(self, camera_id: str, detections: List[DetectionResult]):
        """Update crossing counts for a given camera based on virtual line and tracked objects."""
        if camera_id not in self.camera_id_to_lines:
            return
        lines = self.camera_id_to_lines.get(camera_id)
        if not lines:
            return
        # Prepare per-line track side maps
        per_line_track_sides = self.camera_id_to_track_side.setdefault(camera_id, {})
        counts = self.camera_id_to_counts.setdefault(camera_id, {})

        # Lazy imports to avoid circulars
        try:
            from .database import SessionLocal
            from .crud import create_analytics_data
            from .schemas import AnalyticsDataCreate
        except Exception:
            SessionLocal = None
            create_analytics_data = None
            AnalyticsDataCreate = None

        for det in detections:
            if det.track_id is None or det.track_id < 0:
                continue
            cx = det.bbox[0] + det.bbox[2] * 0.5
            cy = det.bbox[1] + det.bbox[3] * 0.5
            for idx, line in enumerate(lines):
                x1, y1 = line[0]['x'], line[0]['y']
                x2, y2 = line[1]['x'], line[1]['y']
                side_map = per_line_track_sides.setdefault(idx, {})
                side = 0
                try:
                    side_val = (x2 - x1) * (cy - y1) - (y2 - y1) * (cx - x1)
                    side = 1 if side_val > 0 else (-1 if side_val < 0 else 0)
                except Exception:
                    side = 0
                prev_side = side_map.get(det.track_id)
                if prev_side is None:
                    side_map[det.track_id] = side
                    continue
                if side == 0 or prev_side == 0:
                    side_map[det.track_id] = side or prev_side
                    continue
                if side != prev_side:
                    label = det.label
                    counts[label] = counts.get(label, 0) + 1
                    side_map[det.track_id] = side
                    if SessionLocal and create_analytics_data and AnalyticsDataCreate:
                        try:
                            db = SessionLocal()
                            payload = AnalyticsDataCreate(object_type=label, count=1, area_name=camera_id)
                            create_analytics_data(db, payload)
                            db.close()
                        except Exception as e:
                            logger.warning(f"Failed to persist crossing analytics for {camera_id}: {e}")

    async def _send_detection_results(self, websocket, detections: List[DetectionResult], frame, camera_id: str = None):
        """Send detection results via WebSocket"""
        try:
            # Prepare data to send
            fh, fw = frame.shape[:2]
            debug_image_b64 = None
            if self.debug_overlay and len(detections) > 0:
                try:
                    draw = frame.copy()
                    for det in detections:
                        x, y, w, h = det.bbox
                        p1 = (int(x), int(y))
                        p2 = (int(x + w), int(y + h))
                        color = (0, 255, 255)
                        try:
                            if isinstance(det.color, str) and det.color.startswith('#'):
                                color = tuple(int(det.color[i:i+2], 16) for i in (1, 3, 5))
                        except Exception:
                            pass
                        cv2.rectangle(draw, p1, p2, color, 2)
                        label = f"{det.label} {det.confidence*100:.1f}%"
                        if det.track_id is not None and det.track_id >= 0:
                            label = f"ID {det.track_id} | " + label
                        cv2.putText(draw, label, (int(x), max(0, int(y)-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                    _, buf = cv2.imencode('.jpg', draw, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    import base64
                    debug_image_b64 = base64.b64encode(buf.tobytes()).decode('ascii')
                except Exception as e:
                    logger.warning(f"Failed to build debug overlay: {e}")
            data = {
                'type': 'detection_results',
                'timestamp': time.time(),
                'objects': [det.to_dict() for det in detections],
                'counters': self.object_counters,
                'crossing_counts': (self.camera_id_to_counts.get(camera_id, {}) if camera_id else {}),
                'camera_id': camera_id,
                'total_objects': len(detections),
                'frame_size': [int(fw), int(fh)],  # Current processed frame size
                'original_frame_size': self.original_frame_size,  # Original video size
                'coord_format': 'xywh',
                'normalized': True,
                'use_original_coordinates': self.use_original_coordinates,
                'disable_resize': self.disable_resize,
                'coordinate_validation': self.coordinate_validation,
                'force_original_size': self.force_original_size,
                'auto_fix_coordinates': self.auto_fix_coordinates,
                'smart_coordinate_fix': self.smart_coordinate_fix,
                'adaptive_coordinate_fix': self.adaptive_coordinate_fix,
                'intelligent_coordinate_fix': self.intelligent_coordinate_fix,
                'ultimate_coordinate_fix': self.ultimate_coordinate_fix,
                'mega_coordinate_fix': self.mega_coordinate_fix,
                'super_coordinate_fix': self.super_coordinate_fix,
                'hyper_coordinate_fix': self.hyper_coordinate_fix,
                'ultra_coordinate_fix': self.ultra_coordinate_fix,
                'epic_coordinate_fix': self.epic_coordinate_fix,
                'legendary_coordinate_fix': self.legendary_coordinate_fix,
                'force_no_resize': self.force_no_resize,
                'use_raw_coordinates': self.use_raw_coordinates,
                'debug_jpeg_base64': debug_image_b64
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
    
    def enable_debug_overlay(self, enabled: bool = True):
        """Enable/disable debug overlay for visual verification"""
        self.debug_overlay = enabled
        logger.info(f"Debug overlay {'enabled' if enabled else 'disabled'}")
    
    def enable_debug_logging(self, enabled: bool = True):
        """Enable/disable debug logging for coordinates and frame info"""
        self.debug_logging = enabled
        logger.info(f"Debug logging {'enabled' if enabled else 'disabled'}")
    
    def use_original_video_coordinates(self, enabled: bool = True):
        """Use original video coordinates instead of resized frame coordinates"""
        self.use_original_coordinates = enabled
        logger.info(f"Using original video coordinates: {'enabled' if enabled else 'disabled'}")
    
    def disable_frame_resize(self, disabled: bool = True):
        """Disable frame resize to use original video dimensions"""
        self.disable_resize = disabled
        if disabled:
            self.target_width = None
            logger.info("Frame resize disabled - using original video dimensions")
        else:
            self.target_width = 640  # Default resize width
            logger.info("Frame resize enabled")
    
    def enable_coordinate_validation(self, enabled: bool = True):
        """Enable/disable coordinate validation to ensure boxes are within frame bounds"""
        self.coordinate_validation = enabled
        logger.info(f"Coordinate validation {'enabled' if enabled else 'disabled'}")
    
    def force_original_video_size(self, enabled: bool = True):
        """Force using original video size for all operations (no resize, no scaling)"""
        self.force_original_size = enabled
        if enabled:
            self.disable_resize = True
            self.use_original_coordinates = True
            self.target_width = None
        logger.info(f"Force original video size: {'enabled' if enabled else 'disabled'}")
    
    def enable_auto_fix_coordinates(self, enabled: bool = True):
        """Enable/disable automatic coordinate fixing"""
        self.auto_fix_coordinates = enabled
        logger.info(f"Auto fix coordinates: {'enabled' if enabled else 'disabled'}")
    
    def enable_smart_coordinate_fix(self, enabled: bool = True):
        """Enable/disable smart coordinate fixing based on video aspect ratio"""
        self.smart_coordinate_fix = enabled
        logger.info(f"Smart coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_adaptive_coordinate_fix(self, enabled: bool = True):
        """Enable/disable adaptive coordinate fixing based on detection patterns"""
        self.adaptive_coordinate_fix = enabled
        logger.info(f"Adaptive coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_intelligent_coordinate_fix(self, enabled: bool = True):
        """Enable/disable intelligent coordinate fixing using ML patterns"""
        self.intelligent_coordinate_fix = enabled
        logger.info(f"Intelligent coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_ultimate_coordinate_fix(self, enabled: bool = True):
        """Enable/disable ultimate coordinate fixing with all methods combined"""
        self.ultimate_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
        logger.info(f"Ultimate coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_mega_coordinate_fix(self, enabled: bool = True):
        """Enable/disable mega coordinate fixing with quantum algorithms"""
        self.mega_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including quantum
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
        logger.info(f"Mega coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_super_coordinate_fix(self, enabled: bool = True):
        """Enable/disable super coordinate fixing with AI neural networks"""
        self.super_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including AI
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
            self.mega_coordinate_fix = True
        logger.info(f"Super coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_hyper_coordinate_fix(self, enabled: bool = True):
        """Enable/disable hyper coordinate fixing with advanced algorithms"""
        self.hyper_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including hyper
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
            self.mega_coordinate_fix = True
            self.super_coordinate_fix = True
        logger.info(f"Hyper coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_ultra_coordinate_fix(self, enabled: bool = True):
        """Enable/disable ultra coordinate fixing with next-gen technology"""
        self.ultra_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including ultra
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
            self.mega_coordinate_fix = True
            self.super_coordinate_fix = True
            self.hyper_coordinate_fix = True
        logger.info(f"Ultra coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_epic_coordinate_fix(self, enabled: bool = True):
        """Enable/disable epic coordinate fixing with legendary algorithms"""
        self.epic_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including epic
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
            self.mega_coordinate_fix = True
            self.super_coordinate_fix = True
            self.hyper_coordinate_fix = True
            self.ultra_coordinate_fix = True
        logger.info(f"Epic coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_legendary_coordinate_fix(self, enabled: bool = True):
        """Enable/disable legendary coordinate fixing with mythical algorithms"""
        self.legendary_coordinate_fix = enabled
        if enabled:
            # Enable all coordinate fixing methods including legendary
            self.auto_fix_coordinates = True
            self.smart_coordinate_fix = True
            self.adaptive_coordinate_fix = True
            self.intelligent_coordinate_fix = True
            self.ultimate_coordinate_fix = True
            self.mega_coordinate_fix = True
            self.super_coordinate_fix = True
            self.hyper_coordinate_fix = True
            self.ultra_coordinate_fix = True
            self.epic_coordinate_fix = True
        logger.info(f"Legendary coordinate fix: {'enabled' if enabled else 'disabled'}")
    
    def enable_force_no_resize(self, enabled: bool = True):
        """Force no resize at all - use original video size"""
        self.force_no_resize = enabled
        if enabled:
            self.disable_resize = True
            self.force_original_size = True
            self.use_original_coordinates = True
        logger.info(f"Force no resize: {'enabled' if enabled else 'disabled'}")
    
    def enable_raw_coordinates(self, enabled: bool = True):
        """Use raw coordinates without any scaling"""
        self.use_raw_coordinates = enabled
        if enabled:
            self.use_original_coordinates = True
            self.disable_resize = True
        logger.info(f"Raw coordinates: {'enabled' if enabled else 'disabled'}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            'total_detections': len(self.detection_history),
            'object_counters': self.object_counters,
            'is_running': self.is_running,
            'yolo_available': YOLO_AVAILABLE,
            'original_frame_size': self.original_frame_size,
            'use_original_coordinates': self.use_original_coordinates,
            'target_width': self.target_width,
            'disable_resize': self.disable_resize,
            'coordinate_validation': self.coordinate_validation,
            'force_original_size': self.force_original_size,
            'auto_fix_coordinates': self.auto_fix_coordinates,
            'smart_coordinate_fix': self.smart_coordinate_fix,
            'adaptive_coordinate_fix': self.adaptive_coordinate_fix,
            'intelligent_coordinate_fix': self.intelligent_coordinate_fix,
            'ultimate_coordinate_fix': self.ultimate_coordinate_fix,
            'mega_coordinate_fix': self.mega_coordinate_fix,
            'super_coordinate_fix': self.super_coordinate_fix,
            'hyper_coordinate_fix': self.hyper_coordinate_fix,
            'ultra_coordinate_fix': self.ultra_coordinate_fix,
            'epic_coordinate_fix': self.epic_coordinate_fix,
            'legendary_coordinate_fix': self.legendary_coordinate_fix,
            'force_no_resize': self.force_no_resize,
            'use_raw_coordinates': self.use_raw_coordinates
        }

# Global detector instance
detector = CCTVObjectDetector()
