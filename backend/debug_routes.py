#!/usr/bin/env python3
"""
Debug script untuk check routes
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing app...")
    from app.main import app
    
    print(f"\nApp title: {app.title}")
    print(f"App version: {app.version}")
    print(f"Total routes: {len(app.routes)}")
    
    print("\nAll routes:")
    for i, route in enumerate(app.routes):
        print(f"{i+1}. {type(route).__name__}: {route.path}")
        if hasattr(route, 'methods'):
            print(f"   Methods: {route.methods}")
        if hasattr(route, 'endpoint'):
            print(f"   Endpoint: {route.endpoint}")
        print()
    
    # Check specific routes
    print("\nChecking specific routes...")
    route_paths = [route.path for route in app.routes]
    
    test_routes = ["/", "/test-simple", "/health", "/cctv"]
    for route in test_routes:
        if route in route_paths:
            print(f"✅ {route} - FOUND")
        else:
            print(f"❌ {route} - NOT FOUND")
    
    print("\nRoute paths:")
    for path in route_paths:
        print(f"  {path}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
