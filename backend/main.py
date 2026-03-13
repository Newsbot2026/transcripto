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
    time_pattern = re.compile(r"(\d+):(\d+):(\d+\.\d+) --> ")
    current_time = None
    for line in lines:
        line = line.strip()
        tm = time_pattern.match(line)
        if tm:
            h, m, s = int(tm.group(1)), int(tm.group(2)), float(tm.group(3))
            current_time = int(h*3600 + m*60 + s)
        elif line and not line.startswith("WEBVTT") and not line.startswith("NOTE") and "-->" not in line and not line.isdigit() and current_time is not None:
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean:
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

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sub")
            subprocess.run([
                "yt-dlp",
                "--write-auto-sub", "--write-sub",
                "--sub-langs", "en.*,hi",
                "--skip-download",
                "--convert-subs", "vtt",
                "-o", out,
                f"https://www.youtube.com/watch?v={video_id}"
            ], capture_output=True, text=True, timeout=60)

            for f in os.listdir(tmpdir):
                if f.endswith(".vtt"):
                    with open(os.path.join(tmpdir, f), "r", encoding="utf-8") as file:
                        transcript = parse_vtt(file.read())
                    if transcript:
                        return {"success": True, "transcript": transcript}

        return JSONResponse({"error": "No subtitles found for this video. Try a video with captions enabled."}, status_code=404)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/payment/verify")
async def payment(request: Request):
    return {"success": True}

@app.get("/")
async def health():
    return {"status": "running"}
