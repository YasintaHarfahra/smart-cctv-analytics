from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, Response
import httpx
import json
import os

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CCTV_FILE = os.path.join(BASE_DIR, "cctv.json")


@app.get("/cctv")
def get_cctv_list():
    with open(CCTV_FILE, "r") as f:
        data = json.load(f)
    return data


@app.get("/cctv/{cctv_id}")
def get_cctv_detail(cctv_id: str):
    with open(CCTV_FILE, "r") as f:
        data = json.load(f)
    devices = data.get("devices", [])
    for c in devices:
        if c.get("id") == cctv_id:
            return c
    raise HTTPException(status_code=404, detail="CCTV not found")


# 🔥 Proxy untuk streaming HLS (.m3u8 + .ts segments)
@app.get("/proxy")
async def proxy_stream(url: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=None)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail="Failed to fetch stream")

            content_type = r.headers.get("content-type", "application/octet-stream")

            # Kalau file playlist (.m3u8)
            if url.endswith(".m3u8"):
                return Response(content=r.content, media_type="application/vnd.apple.mpegurl")

            # Kalau file segment video (.ts atau lainnya), stream langsung
            return StreamingResponse(r.aiter_bytes(), media_type=content_type)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
