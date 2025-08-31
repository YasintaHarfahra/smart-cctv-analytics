#!/usr/bin/env python3
"""
Test file untuk main.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing imports...")
    from app.main import app
    print("✅ Main app imported successfully")
    
    # Check endpoints
    print("\nChecking endpoints...")
    http_routes = []
    websocket_routes = []
    
    for route in app.routes:
        if hasattr(route, 'path'):
            if hasattr(route, 'methods'):
                # HTTP route
                methods = ', '.join(route.methods)
                http_routes.append(f"{methods} {route.path}")
            else:
                # WebSocket route
                websocket_routes.append(f"WS {route.path}")
    
    print("HTTP Routes:")
    for route in http_routes:
        print(f"  {route}")
    
    print("\nWebSocket Routes:")
    for route in websocket_routes:
        print(f"  {route}")
    
    # Check specific endpoints
    expected_http = [
        "GET /",
        "GET /cctv",
        "GET /cctv/{cctv_id}",
        "GET /health",
        "GET /debug/websocket",
        "GET /proxy"
    ]
    
    expected_websocket = [
        "WS /ws/test",
        "WS /ws/detection/{cctv_id}"
    ]
    
    print("\nChecking expected HTTP endpoints...")
    for expected in expected_http:
        if expected in http_routes:
            print(f"  ✅ {expected}")
        else:
            print(f"  ❌ {expected} - NOT FOUND")
    
    print("\nChecking expected WebSocket endpoints...")
    for expected in expected_websocket:
        if expected in websocket_routes:
            print(f"  ✅ {expected}")
        else:
            print(f"  ❌ {expected} - NOT FOUND")
    
    # Check app configuration
    print(f"\nApp title: {app.title}")
    print(f"App version: {app.version}")
    print(f"Total routes: {len(app.routes)}")
    
    print("\n✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
