from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_youtube_id(url):
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

@app.post("/extract")
async def extract(request: Request):
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        video_id = get_youtube_id(url)
        if not video_id:
            return JSONResponse({"error": "Invalid YouTube URL"}, status_code=400)
        fetched = YouTubeTranscriptApi().fetch(video_id)
        lines = []
        for snippet in fetched:
            s = int(snippet.start)
            lines.append(f"[{s//60:02d}:{s%60:02d}] {snippet.text}")
        return {"success": True, "transcript": "\n".join(lines)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/payment/verify")
async def payment(request: Request):
    return {"success": True}

@app.get("/")
async def health():
    return {"status": "running"}
