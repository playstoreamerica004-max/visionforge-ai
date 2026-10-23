# VisionForge AI — video & photo enhancer starter

A phone-friendly web app with:
- local camera recording in the browser (where supported)
- file upload UI for videos/images
- backend upload limit configured for 2 GiB
- real image AI upscaling via Real-ESRGAN command-line binary (if installed)
- video processing via FFmpeg scaling/denoise/sharpen; optional frame-by-frame AI hook is deliberately not enabled by default

## Important limitations
- 16K output means resizing pixels, not recovering true missing detail. The app does not promise "100% real" recovered details.
- A 2 GB upload requires a host/proxy that allows it, enough disk, and long request timeouts. Free static hosting cannot process this. Many free demo hosts have compute/storage quotas.
- Video mode in this starter uses FFmpeg filters (real transcoding, not generative AI). Photo mode uses Real-ESRGAN AI only if its binary and model files are installed; otherwise it reports a clear error.
- For production, add authentication, per-user quotas, background jobs, object storage, cleanup, rate limiting and HTTPS.

## Run locally (Android-only authoring is possible, but server should run on a computer/cloud)
1. Install Python 3.11+, FFmpeg, and (for AI photos) Real-ESRGAN ncnn Vulkan binary.
2. `pip install -r requirements.txt`
3. `uvicorn app:app --host 0.0.0.0 --port 7860`
4. Open `http://SERVER:7860` in a browser. Camera requires HTTPS or localhost.

Environment:
- `MAX_UPLOAD_BYTES`: defaults to 2 GiB
- `WORK_DIR`: defaults to `./work`
- `REALESRGAN_BIN`: path to `realesrgan-ncnn-vulkan` executable (optional)
- `FFMPEG_BIN`: defaults to `ffmpeg`

## Deploy
Use a Docker-capable host with persistent disk and configurable body-size/request timeouts. Set the reverse proxy body limit to at least 2g and timeout to several hours. Do not assume a free tier accepts 2 GB uploads or provides a GPU.
