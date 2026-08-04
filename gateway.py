#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# Configuration
ARC_API_KEY = os.environ.get("ARC_API_KEY", "YOUR_API_KEY_HERE")
ARC_API_BASE = "https://arcmusic.fun"

app = FastAPI(title="Arc Path Gateway")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Path Gateway Active"}

# ==================== NEW SLASH SEARCH ENDPOINT ====================

@app.get("/search/{q}")
async def search_and_download(q: str):
    """
    Accepts the YouTube video ID directly in the URL path: /search/VIDEO_ID
    Automatically processes it as an audio download.
    """
    video_id = q  # The path parameter {q} is your direct YouTube video ID
    
    # Step 1: Start Download via Arc API
    async with aiohttp.ClientSession() as session:
        params = {
            "query": video_id,
            "isVideo": "false",
            "api_key": ARC_API_KEY
        }
        
        try:
            async with session.get(
                f"{ARC_API_BASE}/youtube/v2/download",
                params=params,
                timeout=30
            ) as r:
                if r.status != 200:
                    raise HTTPException(r.status, f"Arc Init Error: {await r.text()}")
                
                data = await r.json()
                job_id = data.get("job_id")
                
                if not job_id:
                    raise HTTPException(500, "Arc API failed to return a job_id")
        except asyncio.TimeoutError:
            raise HTTPException(504, "Arc API initialization request timed out")
    
    # Step 2: Poll Job Status until done
    async with aiohttp.ClientSession() as session:
        for _ in range(45):  # Poll up to 90 seconds
            await asyncio.sleep(2)
            
            try:
                status_params = {"job_id": job_id, "api_key": ARC_API_KEY}
                async with session.get(
                    f"{ARC_API_BASE}/youtube/jobStatus",
                    params=status_params,
                    timeout=10
                ) as r:
                    if r.status != 200:
                        continue
                    
                    status_data = await r.json()
                    job = status_data.get("job", {})
                    status = job.get("status") or status_data.get("status")
                    
                    if status == "done":
                        public_url = job.get("result", {}).get("public_url", "")
                        if public_url:
                            if ".m4a" in public_url:
                                public_url = public_url.replace(".m4a", ".mp3")
                            
                            return {
                                "success": True,
                                "video_id": video_id,
                                "download_url": f"{ARC_API_BASE}{public_url}"
                            }
                    
                    elif status in ("failed", "error"):
                        raise HTTPException(500, "Download task failed on processing backend")
            except asyncio.TimeoutError:
                continue
                
    raise HTTPException(408, "Download task timed out")

# ==================== MAINTENANCE ENDPOINTS ====================

@app.get("/media/{file_path:path}")
async def get_media(file_path: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ARC_API_BASE}/media/{file_path}") as r:
            if r.status != 200:
                raise HTTPException(r.status, "Media not found")
            return StreamingResponse(
                r.content,
                media_type=r.headers.get("content-type", "audio/mpeg")
            )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("gateway:app", host="0.0.0.0", port=port, reload=False)
