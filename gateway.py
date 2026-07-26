#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ARC API GATEWAY — WITH SEARCH
Now you can search by song name and get downloadable URL
"""

import aiohttp
import asyncio
import os
import re
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

# ==================== CONFIGURATION ====================

ARC_API_KEY = os.environ.get("ARC_API_KEY", "YOUR_API_KEY_HERE")
ARC_API_BASE = "https://api.arcmusic.fun"

# ==================== APP ====================

app = FastAPI(title="Arc Gateway with Search")

# ==================== SEARCH FUNCTION ====================

async def search_youtube(query: str):
    """Search YouTube for a song and get video ID — NO API KEY NEEDED"""
    
    # Use Invidious — public, free, no API key
    search_url = f"https://invidious.io.lol/api/v1/search?q={query.replace(' ', '+')}&type=video&page=1"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=10) as r:
                if r.status != 200:
                    return None
                
                data = await r.json()
                if not data:
                    return None
                
                first = data[0]
                return {
                    "video_id": first.get("videoId"),
                    "title": first.get("title", "Unknown"),
                    "author": first.get("author", "Unknown"),
                    "duration": first.get("lengthSeconds", 0)
                }
    except Exception:
        return None

# ==================== GATEWAY ENDPOINTS ====================

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Gateway with Search"}

# 🔥 NEW: Search by song name
@app.get("/search")
async def search_song(
    q: str = Query(..., description="Song name to search (e.g., 'heat waves')"),
    isVideo: bool = Query(False, description="True for video, false for audio")
):
    """
    Search for a song by name and get downloadable URL
    Example: /search?q=heat+waves
    Returns: downloadable URL directly
    """
    
    # Step 1: Search for the song
    result = await search_youtube(q)
    if not result:
        raise HTTPException(404, f"Song '{q}' not found")
    
    video_id = result["video_id"]
    title = result["title"]
    author = result["author"]
    
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
                            "artist": author,
                            "video_id": video_id,
                            "download_url": downloadable_url,
                            "message": "Click the download_url to get your MP3!"
                        }
                
                elif status in ("failed", "error"):
                    raise HTTPException(500, "Download failed")
    
    raise HTTPException(408, "Download timed out")

# ==================== ORIGINAL ENDPOINTS (Unchanged) ====================

@app.get("/download")
async def download(
    query: str = Query(..., description="YouTube Video ID or URL"),
    isVideo: bool = Query(False, description="True for video, false for audio")
):
    """Original download endpoint — accepts video ID or URL"""
    
    # Extract video ID if full URL is provided
    video_id = query
    if "youtube.com" in query or "youtu.be" in query:
        patterns = [
            r"v=([A-Za-z0-9_-]{11})",
            r"youtu\.be/([A-Za-z0-9_-]{11})",
            r"shorts/([A-Za-z0-9_-]{11})"
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                video_id = match.group(1)
                break
    
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
    print(f"🔑 API Key: {ARC_API_KEY[:10]}...")
    print("📡 Endpoints:")
    print("   /search?q=heat+waves  ← Search by song name!")
    uvicorn.run(app, host="0.0.0.0", port=port)
