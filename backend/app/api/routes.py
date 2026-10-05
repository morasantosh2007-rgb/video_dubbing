import os
import re
import uuid
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.models.schemas import (
    DubbingJobResponse,
    JobProgressResponse,
    JobSettings,
    JobStatus,
    LanguageOption,
    SpeechSegment,
    VoiceOption,
    YoutubeJobRequest,
)
from app.services.pipeline import DubbingPipeline
from app.services.tts_service import TTSService
from app.services.subtitle_service import SubtitleService
from app.services.youtube_service import YouTubeService
from app.storage.job_store import job_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.API_PREFIX)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or malformed paths."""
    base = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return clean or "uploaded_video.mp4"

@router.get("/health")
def health_check():
    """Health check endpoint confirming service status and environment."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "asr_provider": settings.ASR_PROVIDER,
        "translation_provider": settings.TRANSLATION_PROVIDER,
        "tts_provider": settings.TTS_PROVIDER,
    }

@router.get("/languages", response_model=List[LanguageOption])
def list_languages():
    """List supported source and target languages."""
    return [
        LanguageOption(code="hi", name="Hindi", native_name="हिन्दी"),
        LanguageOption(code="te", name="Telugu", native_name="తెలుగు"),
        LanguageOption(code="en", name="English", native_name="English"),
        LanguageOption(code="ta", name="Tamil", native_name="தமிழ்"),
        LanguageOption(code="kn", name="Kannada", native_name="ಕನ್ನಡ"),
    ]

@router.get("/voices", response_model=List[VoiceOption])
def list_voices(language: str = "te"):
    """List available TTS voices for dubbing."""
    return TTSService.get_available_voices(language)

@router.post("/jobs", response_model=DubbingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_dubbing_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_language: str = Form("hi"),
    target_language: str = Form("te"),
    voice_id: str = Form("te-IN-MohanNeural"),
    speaking_rate: float = Form(1.0),
    preserve_background: bool = Form(True),
    ducking_db: float = Form(-12.0)
):
    """
    Upload a Hindi video and initiate the background AI dubbing pipeline.
    """
    # Validate extension
    clean_name = sanitize_filename(file.filename)
    ext = Path(clean_name).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    job_id = uuid.uuid4().hex[:12]
    saved_filename = f"{job_id}_{clean_name}"
    saved_path = settings.UPLOAD_DIR / saved_filename

    # Save uploaded file in chunks
    total_bytes = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    try:
        with open(saved_path, "wb") as f_out:
            while chunk := await file.read(1024 * 1024):  # 1MB chunk
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Video exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
                    )
                f_out.write(chunk)
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink()
        raise e

    job_settings = JobSettings(
        source_language=source_language,
        target_language=target_language,
        voice_id=voice_id,
        speaking_rate=speaking_rate,
        preserve_background=preserve_background,
        ducking_db=ducking_db
    )

    job = job_store.create_job(
        job_id=job_id,
        original_filename=clean_name,
        original_video_path=saved_path,
        job_settings=job_settings
    )

    # Dispatch asynchronous background task
    background_tasks.add_task(DubbingPipeline.execute_job, job_id)

    return job

@router.post("/jobs/youtube", response_model=DubbingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_youtube_dubbing_job(
    request: YoutubeJobRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit a YouTube URL (Hindi video or Shorts) for automated extraction and Telugu dubbing.
    """
    clean_url = request.url.strip()
    if not YouTubeService.is_valid_youtube_url(clean_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube link. Please provide a valid youtube.com or youtu.be URL."
        )

    # Inspect video metadata (fast, flat extraction)
    try:
        info = YouTubeService.get_video_info(clean_url, max_duration=900)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error inspecting YouTube video for {clean_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to access YouTube video: {str(e)}"
        )

    video_title = info.get("title", "youtube_video")
    clean_title = sanitize_filename(f"{video_title}.mp4")
    if not clean_title.lower().endswith(".mp4"):
        clean_title += ".mp4"

    job_id = uuid.uuid4().hex[:12]
    saved_path = settings.UPLOAD_DIR / f"{job_id}_{clean_title}"

    job_settings = JobSettings(
        source_language=request.source_language,
        target_language=request.target_language,
        voice_id=request.voice_id,
        speaking_rate=request.speaking_rate,
        preserve_background=request.preserve_background,
        ducking_db=request.ducking_db
    )

    job = job_store.create_job(
        job_id=job_id,
        original_filename=clean_title,
        original_video_path=saved_path,
        job_settings=job_settings
    )

    # Mark as downloading
    job_store.update_status(
        job_id,
        JobStatus.DOWNLOADING,
        5,
        f"Connecting to YouTube to download '{video_title[:50]}'..."
    )

    # Dispatch asynchronous background task with youtube_url
    background_tasks.add_task(DubbingPipeline.execute_job, job_id, clean_url)

    updated_job = job_store.get_job(job_id)
    return updated_job or job

@router.get("/jobs", response_model=List[DubbingJobResponse])
def get_jobs(limit: int = 20):
    """List recent dubbing jobs."""
    return job_store.list_jobs(limit=limit)

@router.get("/jobs/{job_id}", response_model=DubbingJobResponse)
def get_job(job_id: str):
    """Retrieve complete status and metadata for a specific job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job

@router.get("/jobs/{job_id}/progress", response_model=JobProgressResponse)
def get_job_progress(job_id: str):
    """Lightweight polling endpoint for real-time progress updates."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobProgressResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        current_step=job.status.value
    )

@router.get("/jobs/{job_id}/segments", response_model=List[SpeechSegment])
def get_job_segments(job_id: str):
    """Retrieve timestamped segments showing original Hindi vs dubbed Telugu."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job.segments

@router.get("/jobs/{job_id}/video/original")
def stream_original_video(job_id: str):
    """Stream original uploaded video file."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    path = settings.UPLOAD_DIR / f"{job_id}_{job.original_filename}"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
    return FileResponse(path, media_type="video/mp4", filename=job.original_filename)

@router.get("/jobs/{job_id}/video/dubbed")
def stream_dubbed_video(job_id: str, subtitles: Optional[str] = None):
    """Stream final synchronized Telugu dubbed video. Pass ?subtitles=burned for hardcoded subtitles."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed yet (current status: {job.status})"
        )

    # Check if user requested burned-in subtitles
    if subtitles == "burned":
        subtitled_path = settings.OUTPUT_DIR / f"dubbed_subtitled_{job_id}_{job.original_filename}"
        if not subtitled_path.exists():
            srt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.srt"
            clean_path = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"
            if srt_path.exists() and clean_path.exists():
                try:
                    MediaService.burn_subtitles(clean_path, srt_path, subtitled_path)
                except Exception as e:
                    logger.warning(f"Could not generate subtitled video on-the-fly: {e}")
        if subtitled_path.exists():
            return FileResponse(subtitled_path, media_type="video/mp4", filename=f"telugu_subtitled_{job.original_filename}")

    path = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dubbed video file not found")
    return FileResponse(path, media_type="video/mp4", filename=f"telugu_dubbed_{job.original_filename}")

@router.get("/jobs/{job_id}/video/subtitled")
def stream_subtitled_video(job_id: str):
    """Stream final Telugu dubbed video with permanently visible Telugu subtitles."""
    return stream_dubbed_video(job_id, subtitles="burned")

@router.get("/jobs/{job_id}/download")
def download_dubbed_video(job_id: str, subtitles: Optional[str] = None):
    """Download final dubbed Telugu video file. Pass ?subtitles=burned for hardcoded subtitles."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not completed")

    if subtitles == "burned":
        subtitled_path = settings.OUTPUT_DIR / f"dubbed_subtitled_{job_id}_{job.original_filename}"
        if not subtitled_path.exists():
            srt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.srt"
            clean_path = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"
            if srt_path.exists() and clean_path.exists():
                try:
                    MediaService.burn_subtitles(clean_path, srt_path, subtitled_path)
                except Exception as e:
                    logger.warning(f"Could not generate subtitled video for download: {e}")
        if subtitled_path.exists():
            return FileResponse(
                subtitled_path,
                media_type="application/octet-stream",
                filename=f"telugu_subtitled_{job.original_filename}"
            )

    path = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"telugu_dubbed_{job.original_filename}"
    )

@router.get("/jobs/{job_id}/download/subtitled")
def download_subtitled_video(job_id: str):
    """Download final dubbed Telugu video file with permanently visible Telugu subtitles."""
    return download_dubbed_video(job_id, subtitles="burned")

@router.get("/jobs/{job_id}/subtitles/srt")
def download_subtitles_srt(job_id: str):
    """Download refined broadcast-quality Telugu subtitles in SubRip (.srt) format."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    srt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.srt"
    if not srt_path.exists():
        if job.segments and any(s.telugu_text for s in job.segments):
            SubtitleService.generate_srt(job.segments, srt_path)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telugu subtitles not yet available for this job")

    return FileResponse(
        srt_path,
        media_type="application/x-subrip; charset=utf-8",
        filename=f"telugu_subtitles_{job.original_filename}.srt"
    )

@router.get("/jobs/{job_id}/subtitles/vtt")
def stream_subtitles_vtt(job_id: str):
    """Stream refined Telugu subtitles in WebVTT (.vtt) format for web and mobile players."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    vtt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.vtt"
    if not vtt_path.exists():
        if job.segments and any(s.telugu_text for s in job.segments):
            SubtitleService.generate_vtt(job.segments, vtt_path)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telugu subtitles not yet available for this job")

    return FileResponse(
        vtt_path,
        media_type="text/vtt; charset=utf-8",
        filename=f"telugu_subtitles_{job.original_filename}.vtt"
    )

@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """Delete a dubbing job and remove all associated files from disk."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Remove specific named files
    orig_path = settings.UPLOAD_DIR / f"{job_id}_{job.original_filename}"
    out_path = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"
    subtitled_path = settings.OUTPUT_DIR / f"subtitled_{job_id}_{job.original_filename}"
    srt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.srt"
    vtt_path = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.vtt"
    for p in (orig_path, out_path, subtitled_path, srt_path, vtt_path):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # Clean any other temp, upload, or output files matching this job_id
    for directory in (settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR):
        if directory.exists():
            for f in directory.glob(f"*{job_id}*"):
                try:
                    if f.is_file():
                        f.unlink()
                except Exception:
                    pass

    job_store.delete_job(job_id)
    return {"message": f"Job {job_id} deleted successfully"}

