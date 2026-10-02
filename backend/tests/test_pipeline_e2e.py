import time
import subprocess
import pytest
from pathlib import Path
from gtts import gTTS
from app.config import settings
from app.models.schemas import JobSettings, JobStatus
from app.storage.job_store import job_store
from app.services.pipeline import DubbingPipeline
from app.services.media_service import MediaService

def test_full_dubbing_pipeline_e2e(tmp_path):
    job_id = "test_e2e_001"
    raw_hi_audio = tmp_path / "hindi_speech.mp3"
    test_video = tmp_path / "sample_hindi.mp4"

    # 1. Generate real Hindi speech
    tts = gTTS(text="नमस्ते, आप कैसे हैं? आपका स्वागत है।", lang="hi")
    tts.save(str(raw_hi_audio))
    assert raw_hi_audio.exists()

    # 2. Create sample MP4 video using FFmpeg combining test video pattern and Hindi speech
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=navy:s=640x360:r=25",
        "-i", str(raw_hi_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(test_video)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0
    assert test_video.exists()

    # Copy to uploads dir
    dest_video = settings.UPLOAD_DIR / f"{job_id}_sample_hindi.mp4"
    import shutil
    shutil.copy(test_video, dest_video)

    # 3. Create job in store
    job_settings = JobSettings(
        source_language="hi",
        target_language="te",
        voice_id="te-IN-MohanNeural",
        preserve_background=True,
        ducking_db=-12.0
    )
    job = job_store.create_job(
        job_id=job_id,
        original_filename="sample_hindi.mp4",
        original_video_path=dest_video,
        job_settings=job_settings
    )
    assert job is not None

    # 4. Execute pipeline
    DubbingPipeline.execute_job(job_id)

    # 5. Verify final job status
    finished_job = job_store.get_job(job_id)
    assert finished_job is not None
    assert finished_job.status == JobStatus.COMPLETED
    assert finished_job.progress == 100
    assert len(finished_job.segments) > 0
    assert finished_job.output_video_url is not None

    # Verify dubbed video file exists and is valid media
    dubbed_file = settings.OUTPUT_DIR / f"dubbed_{job_id}_sample_hindi.mp4"
    assert dubbed_file.exists()
    assert MediaService.validate_rendered_video(dubbed_file)

    # Clean up test artifacts
    job_store.delete_job(job_id)
    if dest_video.exists():
        dest_video.unlink()
    if dubbed_file.exists():
        dubbed_file.unlink()
