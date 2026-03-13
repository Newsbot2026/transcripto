"""
Transcripto Backend - FastAPI
Supports: YouTube, Instagram, X/Twitter, Facebook, LinkedIn
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
import os
import subprocess
import tempfile
import whisper
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Transcripto API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper model loaded!")

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
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def transcribe_with_whisper(url: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")
        result = subprocess.run([
            "yt-dlp", "--extract-audio", "--audio-format", "mp3",
            "--audio-quality", "0", "-o", audio_path, "--no-playlist", url,
        ], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise Exception(f"yt-dlp failed: {result.stderr[:300]}")
        if not os.path.exists(audio_path):
            raise Exception("Audio file not downloaded")
        result = whisper_model.transcribe(audio_path)
        segments = result.get("segments", [])
        if segments:
            lines = []
            for seg in segments:
                start = int(seg["start"])
                mins = start // 60
                secs = start % 60
                lines.append(f"[{mins:02d}:{secs:02d}] {seg['text'].strip()}")
            return "\n".join(lines)
        return result["text"].strip()

@app.post("/extract")
async def extract_transcript(req: ExtractRequest):
    url = req.url.strip()
    platform = detect_platform(url)
    if platform == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported platform URL")
    try:
        if platform == "youtube":
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
        else:
            transcript = transcribe_with_whisper(url)
        return {"success": True, "platform": platform, "transcript": transcript, "word_count": len(transcript.split())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payment/verify")
async def verify_payment(req: PaymentRequest):
    print(f"Payment received: {req.razorpay_payment_id}, Plan: {req.plan}")
    return {"success": True, "message": "Subscription activated", "plan": req.plan, "payment_id": req.razorpay_payment_id}

@app.get("/")
async def health():
    return {"status": "Transcripto backend is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
