#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ARC API GATEWAY — WITH py_yt SEARCH
Same as your bot: search → download → return URL
"""

import os
import re
import asyncio
import aiohttp
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# 🔥 Same search library as your bot
from py_yt import VideosSearch

# ==================== CONFIGURATION ====================

ARC_API_KEY = os.environ.get("ARC_API_KEY", "YOUR_API_KEY_HERE")
ARC_API_BASE = "https://api.arcmusic.fun"

# ==================== APP ====================

app = FastAPI(title="Arc Gateway")

# ==================== SEARCH FUNCTION (SAME AS YOUR BOT) ====================

async def search_youtube(query: str):
    """Same search logic as your bot — uses py_yt"""
    try:
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
    except Exception as e:
        print(f"Search error: {e}")
        return None
    
    if results and results.get("result"):
        data = results["result"][0]
        return {
            "video_id": data.get("id"),
            "title": data.get("title", "Unknown"),
            "channel": data.get("channel", {}).get("name", "Unknown"),
            "duration": data.get("duration", "Unknown")
        }
    return None

# ==================== SEARCH + DOWNLOAD ENDPOINT ====================

@app.get("/search")
async def search_and_download(
    q: str = Query(..., description="Song name (e.g., 'heat waves')"),
    isVideo: bool = Query(False, description="True for video, false for audio")
):
    """
    Search for a song by name → returns downloadable URL
    Example: /search?q=heat+waves
    """
    
    # Step 1: Search using py_yt (same as your bot!)
    result = await search_youtube(q)
    if not result:
        raise HTTPException(404, f"Song '{q}' not found")
    
    video_id = result["video_id"]
    title = result["title"]
    channel = result["channel"]
    
    # Step 2: Start download via Arc API
    async with aiohttp.ClientSession() as session:
        params = {
            "query": video_id,
            "isVideo": str(isVideo).lower(),
            "api_key": ARC_API_KEY
        }
        
        async with session.get(
            f"{ARC_API_BASE}/youtube/v2/download",
            params=params,
            timeout=30
        ) as r:
            if r.status != 200:
                error = await r.text()
                raise HTTPException(r.status, error)
            
            data = await r.json()
            job_id = data.get("job_id")
            
            if not job_id:
                raise HTTPException(500, "No job_id returned")
    
    # Step 3: Poll for completion
    async with aiohttp.ClientSession() as session:
        for i in range(30):
            await asyncio.sleep(2)
            
            async with session.get(
                f"{ARC_API_BASE}/youtube/jobStatus",
                params={"job_id": job_id, "api_key": ARC_API_KEY},
                timeout=10
            ) as r:
                if r.status != 200:
                    continue
                
                status_data = await r.json()
                job = status_data.get("job", {})
                status = job.get("status") or status_data.get("status")
                
                if status == "done":
                    result_data = job.get("result", {})
                    public_url = result_data.get("public_url", "")
                    
                    if public_url:
                        # Convert M4A to MP3
                        if ".m4a" in public_url:
                            public_url = public_url.replace(".m4a", ".mp3")
                        
                        downloadable_url = f"{ARC_API_BASE}{public_url}"
                        
                        return {
                            "success": True,
                            "song": title,
                            "artist": channel,
                            "video_id": video_id,
                            "download_url": downloadable_url
                        }
                
                elif status in ("failed", "error"):
                    raise HTTPException(500, "Download failed")
    
    raise HTTPException(408, "Download timed out")

# ==================== ORIGINAL ENDPOINTS (Same as Arc API) ====================

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Gateway is running"}

@app.get("/download")
async def download(
    query: str = Query(..., description="YouTube Video ID"),
    isVideo: bool = Query(False, description="True for video, false for audio")
):
    """Direct download by video ID — same as Arc API"""
    
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
        ) as r:
            if r.status != 200:
                error = await r.text()
                raise HTTPException(r.status, error)
            return await r.json()

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
        ) as r:
            if r.status != 200:
                error = await r.text()
                raise HTTPException(r.status, error)
            return await r.json()

@app.get("/media/{file_path:path}")
async def get_media(file_path: str):
    async with aiohttp.ClientSession() as session:
        media_url = f"{ARC_API_BASE}/media/{file_path}"
        async with session.get(media_url) as r:
            if r.status != 200:
                raise HTTPException(r.status, "Media not found")
            return StreamingResponse(
                r.content,
                media_type=r.headers.get("content-type", "audio/mpeg")
            )

# ==================== START ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("🚀 Arc Gateway with Search running")
    uvicorn.run(app, host="0.0.0.0", port=port)
