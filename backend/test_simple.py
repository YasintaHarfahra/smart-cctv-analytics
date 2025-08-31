#!/usr/bin/env python3
"""
Simple test file untuk FastAPI tanpa object detection
"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Test API", version="1.0.0")

@app.get("/")
def root():
    return {"message": "Test API is working"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/test")
def test():
    return {"message": "Test endpoint working"}

if __name__ == "__main__":
    print("Starting simple test server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
