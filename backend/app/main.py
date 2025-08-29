from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import httpx
import json
import os

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3001", # Port default Vite Anda
    # Tambahkan alamat frontend production Anda di sini jika perlu
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    # Be tolerant to upstream TLS/cert issues and redirects often present in CCTV origins
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=None, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }) as client:
        try:
            r = await client.get(url)
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
