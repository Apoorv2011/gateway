#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiohttp
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import os

ARC_API_KEY = os.environ.get("ARC_API_KEY", "YOUR_API_KEY_HERE")
ARC_API_BASE = "https://api.arcmusic.fun"

app = FastAPI(title="Arc Gateway")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Gateway is running"}

@app.get("/download")
async def download(
    query: str = Query(..., description="YouTube Video ID"),
    isVideo: bool = Query(False, description="True for video, false for audio")
):
    async with aiohttp.ClientSession() as session:
        params = {
            "query": query,
            "isVideo": str(isVideo).lower(),
            "api_key": ARC_API_KEY
        }
        async with session.get(
            f"{ARC_API_BASE}/youtube/v2/download",
            params=params,
            timeout=30
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise HTTPException(response.status, error)
            return await response.json()

@app.get("/status")
async def status(
    job_id: str = Query(..., description="Job ID from download")
):
    async with aiohttp.ClientSession() as session:
        params = {
            "job_id": job_id,
            "api_key": ARC_API_KEY
        }
        async with session.get(
            f"{ARC_API_BASE}/youtube/jobStatus",
            params=params,
            timeout=30
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise HTTPException(response.status, error)
            return await response.json()

@app.get("/media/{file_path:path}")
async def get_media(file_path: str):
    async with aiohttp.ClientSession() as session:
        media_url = f"{ARC_API_BASE}/media/{file_path}"
        async with session.get(media_url) as response:
            if response.status != 200:
                raise HTTPException(response.status, "Media not found")
            return StreamingResponse(
                response.content,
                media_type=response.headers.get("content-type", "audio/mpeg")
            )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("🚀 Arc Gateway running")
    print(f"🔑 API Key: {ARC_API_KEY[:10]}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
