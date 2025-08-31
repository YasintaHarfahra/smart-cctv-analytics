#!/usr/bin/env python3
"""
Simple FastAPI test server
"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Test Server", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/test")
async def test():
    return {"test": "working"}

if __name__ == "__main__":
    print("Starting simple test server...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="debug")
