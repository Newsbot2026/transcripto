from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI(title="Transcripto API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    url: str

class PaymentRequest(BaseModel):
    razorpay_payment_id: str
    plan: str

def detect_platform(url: str) -> str:
    url = url.lower()
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "instagram.com" in url:
        return "instagram"
    elif "twitter.com" in url or "x.com" in url:
        return "x"
    elif "facebook.com" in url:
        return "facebook"
    elif "linkedin.com" in url:
        return "linkedin"
    return "unknown"

def get_youtube_id(url: str) -> str:
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.post("/extract")
async def extract_transcript(req: ExtractRequest):
    url = req.url.strip()
    platform = detect_platform(url)
    if platform == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported platform URL")
    if platform != "youtube":
        raise HTTPException(status_code=400, detail="Currently only YouTube is supported on free tier")
    try:
        video_id = get_youtube_id(url)
        if not video_id:
            raise Exception("Could not extract YouTube video ID")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi", "auto"])
        lines = []
        for entry in transcript_list:
            start = int(entry["start"])
            mins = start // 60
            secs = start % 60
            lines.append(f"[{mins:02d}:{secs:02d}] {entry['text']}")
        transcript = "\n".join(lines)
        return {"success": True, "platform": platform, "transcript": transcript, "word_count": len(transcript.split())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payment/verify")
async def verify_payment(req: PaymentRequest):
    return {"success": True, "message": "Subscription activated", "plan": req.plan}

@app.get("/")
async def health():
    return {"status": "Transcripto backend is running!"}
