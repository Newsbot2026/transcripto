from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess, os, tempfile, re

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

def parse_vtt(content):
    lines = content.split("\n")
    result = []
    seen = set()
    time_pattern = re.compile(r"(\d+):(\d+):(\d+\.\d+)\s-->")
    current_time = None
    for line in lines:
        line = line.strip()
        tm = time_pattern.match(line)
        if tm:
            h, m, s = int(tm.group(1)), int(tm.group(2)), float(tm.group(3))
            current_time = int(h*3600 + m*60 + s)
        elif line and not line.startswith("WEBVTT") and not line.startswith("NOTE") and "-->" not in line and not line.isdigit() and current_time is not None:
            clean = re.sub(r"<[^>]+>", "", line).strip()
            clean = re.sub(r"&amp;", "&", clean)
            clean = re.sub(r"&nbsp;", " ", clean)
            if clean and clean not in seen:
                seen.add(clean)
                result.append(f"[{current_time//60:02d}:{current_time%60:02d}] {clean}")
                current_time = None
    return "\n".join(result)

@app.post("/extract")
async def extract(request: Request):
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        video_id = get_youtube_id(url)
        if not video_id:
            return JSONResponse({"error": "Invalid YouTube URL"}, status_code=400)

        full_url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sub")

            # Try 1: Auto-generated subtitles — ALL languages
            result = subprocess.run([
                "yt-dlp",
                "--write-auto-sub",
                "--sub-langs", "all",
                "--skip-download",
                "--convert-subs", "vtt",
                "-o", out,
                full_url
            ], capture_output=True, text=True, timeout=60)

            # Try 2: Manual subtitles if auto failed
            if not any(f.endswith(".vtt") for f in os.listdir(tmpdir)):
                subprocess.run([
                    "yt-dlp",
                    "--write-sub",
                    "--sub-langs", "all",
                    "--skip-download",
                    "--convert-subs", "vtt",
                    "-o", out,
                    full_url
                ], capture_output=True, text=True, timeout=60)

            # Parse any .vtt file found — prefer English/Hindi
            vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]

            # Sort: prefer en, hi, then others
            def sort_key(f):
                if ".en." in f or f.endswith(".en.vtt"): return 0
                if ".hi." in f or f.endswith(".hi.vtt"): return 1
                return 2
            vtt_files.sort(key=sort_key)

            for fname in vtt_files:
                with open(os.path.join(tmpdir, fname), "r", encoding="utf-8") as file:
                    transcript = parse_vtt(file.read())
                if transcript and len(transcript.strip()) > 50:
                    return {"success": True, "transcript": transcript}

        return JSONResponse({
            "error": "No captions found for this video. This video may not have subtitles enabled by the creator. Try a different video."
        }, status_code=404)

    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Request timed out. Please try again."}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/payment/verify")
async def payment(request: Request):
    return {"success": True}

@app.get("/")
async def health():
    return {"status": "running"}
