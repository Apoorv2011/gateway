#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import asyncio
import aiohttp
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# 🔥 SAME as your bot — py_yt
from py_yt import VideosSearch

# ==================== CONFIGURATION ====================

ARC_API_KEY = os.environ.get("ARC_API_KEY", "YOUR_API_KEY_HERE")
ARC_API_BASE = "https://api.arcmusic.fun"

app = FastAPI(title="Arc Gateway with py_yt Search")

# ==================== SEARCH (EXACTLY LIKE YOUR BOT) ====================

async def search_youtube(query: str):
    """EXACT same search logic as your bot"""
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
        }
    return None

# ==================== SEARCH + DOWNLOAD ====================

@app.get("/search")
async def search_and_download(
    q: str = Query(..., description="Song name"),
    isVideo: bool = Query(False)
):
    # Step 1: Search (same as your bot!)
    result = await search_youtube(q)
    if not result:
        raise HTTPException(404, f"Song '{q}' not found")
    
    video_id = result["video_id"]
    title = result["title"]
    channel = result["channel"]
    
    # Step 2: Download via Arc API
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
                raise HTTPException(r.status, await r.text())
            
            data = await r.json()
            job_id = data.get("job_id")
            
            if not job_id:
                raise HTTPException(500, "No job_id")
    
    # Step 3: Poll
    async with aiohttp.ClientSession() as session:
        for _ in range(30):
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
                    public_url = job.get("result", {}).get("public_url", "")
                    if public_url:
                        if ".m4a" in public_url:
                            public_url = public_url.replace(".m4a", ".mp3")
                        
                        return {
                            "success": True,
                            "song": title,
                            "artist": channel,
                            "video_id": video_id,
                            "download_url": f"{ARC_API_BASE}{public_url}"
                        }
                
                elif status in ("failed", "error"):
                    raise HTTPException(500, "Download failed")
    
    raise HTTPException(408, "Download timed out")

# ==================== OTHER ENDPOINTS ====================

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Gateway"}

@app.get("/download")
async def download(
    query: str = Query(...),
    isVideo: bool = Query(False)
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
        ) as r:
            if r.status != 200:
                raise HTTPException(r.status, await r.text())
            return await r.json()

@app.get("/status")
async def status(job_id: str = Query(...)):
    async with aiohttp.ClientSession() as session:
        params = {"job_id": job_id, "api_key": ARC_API_KEY}
        async with session.get(
            f"{ARC_API_BASE}/youtube/jobStatus",
            params=params,
            timeout=30
        ) as r:
            if r.status != 200:
                raise HTTPException(r.status, await r.text())
            return await r.json()

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
    uvicorn.run(app, host="0.0.0.0", port=port)
