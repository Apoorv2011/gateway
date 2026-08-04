#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import aiohttp
from fastapi import FastAPI, Query, HTTPException
import uvicorn

# Configuration
ARC_API_KEY = os.environ.get("ARC_API_KEY")
if not ARC_API_KEY:
    print("WARNING: ARC_API_KEY environment variable is missing!")

ARC_API_BASE = "https://api.arcmusic.fun"

app = FastAPI(title="Arc Download Gateway")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Arc Download Gateway Active"}

@app.get("/get-download")
async def get_download_url(
    video_id: str = Query(..., description="The YouTube Video ID only (e.g., gJLVTKhTnog)"),
    isVideo: bool = Query(False, description="True for video, False for audio")
):
    """
    Accepts a direct YouTube video ID, initiates background processing on Arc API,
    polls until complete, and gives back the final absolute downloadable URL.
    """
    # Step 1: Initialize Download Job
    async with aiohttp.ClientSession() as session:
        params = {
            "query": video_id,
            "isVideo": str(isVideo).lower(),
            "api_key": ARC_API_KEY
        }
        
        try:
            async with session.get(
                f"{ARC_API_BASE}/youtube/v2/download",
                params=params,
                timeout=20
            ) as r:
                if r.status != 200:
                    error_msg = await r.text()
                    raise HTTPException(r.status, f"Arc API Error: {error_msg}")
                
                data = await r.json()
                job_id = data.get("job_id")
                
                if not job_id:
                    raise HTTPException(500, "Arc API failed to return a job_id")
        except asyncio.TimeoutError:
            raise HTTPException(504, "Arc API initialization request timed out")

    # Step 2: Poll status endpoint for completion
    async with aiohttp.ClientSession() as session:
        # Loop 45 times with 2-second sleep intervals (90 seconds maximum wait time)
        for _ in range(45):
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
                    
                    # Read status structure matching Arc documentation
                    job = status_data.get("job", {})
                    status = job.get("status") or status_data.get("status")
                    
                    if status == "done":
                        public_url = job.get("result", {}).get("public_url", "")
                        if not public_url:
                            raise HTTPException(500, "Job completed but no download path was provided")
                        
                        # Match extensions cleanly
                        if not isVideo and ".m4a" in public_url:
                            public_url = public_url.replace(".m4a", ".mp3")
                            
                        return {
                            "success": True,
                            "video_id": video_id,
                            "job_id": job_id,
                            "download_url": f"{ARC_API_BASE}{public_url}"
                        }
                    
                    elif status in ("failed", "error"):
                        raise HTTPException(500, "Arc API media download processing failed")
                        
            except asyncio.TimeoutError:
                continue # Skip flaky timeouts and keep polling until the 90s mark
                
    raise HTTPException(408, "The download task timed out on the processing backend")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("gateway:app", host="0.0.0.0", port=port, reload=False)
