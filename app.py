import os, uuid, shutil, subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = Path(__file__).parent
WORK = Path(os.getenv("WORK_DIR", "./work")).resolve()
WORK.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024**3)))
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
REALESRGAN = os.getenv("REALESRGAN_BIN", "realesrgan-ncnn-vulkan")

app = FastAPI(title="VisionForge AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
def home():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "max_upload_bytes": MAX_BYTES, "photo_ai_binary": shutil.which(REALESRGAN) is not None,
            "ffmpeg": shutil.which(FFMPEG) is not None}

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60*60*8)
    if p.returncode:
        raise HTTPException(500, "المعالجة فشلات: " + p.stderr[-1400:])
    return p

async def save_limited(upload: UploadFile, path: Path):
    total = 0
    with path.open("wb") as out:
        while True:
            chunk = await upload.read(8 * 1024 * 1024)
            if not chunk: break
            total += len(chunk)
            if total > MAX_BYTES:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, "الملف أكبر من الحد المسموح (2GB).")
            out.write(chunk)
    if total == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "الملف فارغ.")
    return total

@app.post("/api/process")
async def process(file: UploadFile = File(...), kind: str = Form(...),
                  quality: str = Form("1080p"), mode: str = Form("enhance")):
    name = Path(file.filename or "upload").name
    ext = Path(name).suffix.lower()
    is_image = kind == "image"
    allowed = {".jpg",".jpeg",".png",".webp"} if is_image else {".mp4",".mov",".mkv",".webm",".m4v"}
    if ext not in allowed:
        raise HTTPException(415, "نوع الملف غير مدعوم.")
    job = uuid.uuid4().hex
    folder = WORK / job
    folder.mkdir(parents=True)
    src = folder / ("input" + ext)
    await save_limited(file, src)
    out = folder / ("enhanced" + (".png" if is_image else ".mp4"))
    try:
        if is_image:
            binary = shutil.which(REALESRGAN)
            if not binary:
                raise HTTPException(503, "تحسين الصور بالذكاء الاصطناعي يحتاج تثبيت Real-ESRGAN على السيرفر. ما غاديش نعطيك نتيجة مزيفة.")
            # Real-ESRGAN ncnn Vulkan writes into an output directory.
            outdir = folder / "aiout"
            outdir.mkdir()
            run([binary, "-i", str(src), "-o", str(outdir), "-n", "realesrgan-x4plus", "-s", "4"])
            produced = outdir / (src.stem + ".png")
            if not produced.exists():
                candidates = list(outdir.glob("*"))
                if not candidates: raise HTTPException(500, "نموذج AI ما خرج حتى صورة.")
                produced = candidates[0]
            shutil.copyfile(produced, out)
        else:
            dims = {"720p":"1280:720", "1080p":"1920:1080", "2k":"2560:1440",
                    "4k":"3840:2160", "8k":"7680:4320", "16k":"15360:8640"}
            if quality not in dims: raise HTTPException(400, "دقة غير معروفة.")
            # This is real FFmpeg transcoding/upscaling, not an AI restoration model.
            vf = f"scale={dims[quality]}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={dims[quality]}:(ow-iw)/2:(oh-ih)/2,unsharp=5:5:0.5:3:3:0.0"
            if mode == "denoise": vf = "hqdn3d=1.5:1.5:6:6," + vf
            run([FFMPEG, "-y", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
        return {"ok": True, "job_id": job, "filename": out.name, "download_url": f"/api/download/{job}",
                "note": "AI photo model used." if is_image else "FFmpeg upscale/transcode; not AI detail reconstruction."}
    except HTTPException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(500, f"خطأ أثناء المعالجة: {str(e)[:300]}")

@app.get("/api/download/{job_id}")
def download(job_id: str):
    if not job_id.isalnum() or len(job_id) != 32:
        raise HTTPException(400, "معرّف غير صالح.")
    folder = WORK / job_id
    files = list(folder.glob("enhanced.*")) if folder.exists() else []
    if not files: raise HTTPException(404, "الملف غير موجود أو تم حذفه.")
    return FileResponse(files[0], filename=files[0].name)
