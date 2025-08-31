#!/usr/bin/env python3
"""
Script untuk download model YOLO secara otomatis
"""

import os
import sys
from pathlib import Path

def download_yolo_model():
    """Download YOLO model jika belum ada"""
    try:
        from ultralytics import YOLO
        
        model_path = "yolov8n.pt"
        
        if not os.path.exists(model_path):
            print("Downloading YOLO model...")
            model = YOLO('yolov8n.pt')  # Ini akan download model secara otomatis
            print(f"Model downloaded successfully to {model_path}")
        else:
            print(f"YOLO model already exists at {model_path}")
            
        return True
        
    except Exception as e:
        print(f"Error downloading YOLO model: {e}")
        return False

if __name__ == "__main__":
    success = download_yolo_model()
    sys.exit(0 if success else 1)
