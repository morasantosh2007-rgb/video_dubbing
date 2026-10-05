import logging
import shutil
import traceback
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.schemas import JobStatus
from app.services.media_service import MediaService
from app.services.asr_service import ASRService
from app.services.translation_service import TranslationService
from app.services.tts_service import TTSService
from app.services.audio_sync_service import AudioSyncService
from app.services.subtitle_service import SubtitleService
from app.services.youtube_service import YouTubeService
from app.storage.job_store import job_store

logger = logging.getLogger(__name__)

class DubbingPipeline:
    @classmethod
    def execute_job(cls, job_id: str, youtube_url: Optional[str] = None):
        """
        Executes the end-to-end Hindi -> Telugu dubbing pipeline synchronously in background worker.
        If youtube_url is provided, downloads the video first before speech processing.
        """
        job = job_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in store!")
            return

        work_dir = settings.TEMP_DIR / f"job_{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        original_video = settings.UPLOAD_DIR / f"{job_id}_{job.original_filename}"
        output_video = settings.OUTPUT_DIR / f"dubbed_{job_id}_{job.original_filename}"

        try:
            # Step 0 (If YouTube): DOWNLOADING
            if youtube_url:
                logger.info(f"[{job_id}] Step 0: Downloading YouTube video from {youtube_url}...")
                job_store.update_status(
                    job_id,
                    JobStatus.DOWNLOADING,
                    5,
                    "Connecting to YouTube & downloading video stream..."
                )

                def on_download_progress(pct: int, msg: str):
                    job_store.update_status(job_id, JobStatus.DOWNLOADING, pct, msg)

                YouTubeService.download_video(
                    url=youtube_url,
                    output_path=original_video,
                    progress_callback=on_download_progress
                )

                if not original_video.exists() or original_video.stat().st_size == 0:
                    raise RuntimeError("YouTube video download failed or resulted in an empty file.")

                job_store.update_status(
                    job_id,
                    JobStatus.ANALYZING,
                    10,
                    "YouTube video downloaded successfully. Inspecting media..."
                )

            # Step 1: ANALYZING
            logger.info(f"[{job_id}] Step 1: Analyzing video...")
            job_store.update_status(job_id, JobStatus.ANALYZING, 10, "Inspecting video format and audio streams...")
            meta = MediaService.probe_media(original_video)
            job_store.update_metadata(job_id, meta)

            if not meta.has_audio:
                raise ValueError("The uploaded video has no audio track. Please provide a video with speech.")
            if meta.duration <= 0.5:
                raise ValueError("The uploaded video duration is too short for speech dubbing.")

            # Step 2: EXTRACTING_AUDIO
            logger.info(f"[{job_id}] Step 2: Extracting audio...")
            job_store.update_status(job_id, JobStatus.EXTRACTING_AUDIO, 20, "Extracting audio track for speech recognition...")
            audio_16k = work_dir / "audio_16k.wav"
            MediaService.extract_audio(original_video, audio_16k, sample_rate=16000, channels=1)

            original_stereo = work_dir / "original_stereo.wav"
            MediaService.extract_stereo_audio(original_video, original_stereo)

            # Step 3: TRANSCRIBING
            logger.info(f"[{job_id}] Step 3: Transcribing Hindi speech...")
            job_store.update_status(job_id, JobStatus.TRANSCRIBING, 35, "Recognizing Hindi speech and timestamps...")
            segments = ASRService.transcribe(audio_16k, language=job.settings.source_language)

            if not segments:
                logger.info(f"[{job_id}] No vocal lyrics or speech detected across all recognition passes. Preserving original video audio.")
                shutil.copy(original_video, output_video)
                job_store.update_status(job_id, JobStatus.COMPLETED, 100, "No vocal lyrics or dialogue detected. Original audio track preserved intact.")
                job_store.set_completed(job_id, output_video)
                return

            job_store.update_segments(job_id, segments)

            # Step 4: TRANSLATING
            logger.info(f"[{job_id}] Step 4: Translating Hindi -> Telugu...")
            job_store.update_status(job_id, JobStatus.TRANSLATING, 50, f"Translating {len(segments)} speech segments to Telugu...")
            segments = TranslationService.translate_segments(
                segments,
                source_lang=job.settings.source_language,
                target_lang=job.settings.target_language
            )
            job_store.update_segments(job_id, segments)

            # Step 5: GENERATING_TELUGU_AUDIO
            logger.info(f"[{job_id}] Step 5: Generating Telugu speech...")
            job_store.update_status(job_id, JobStatus.GENERATING_TELUGU_AUDIO, 65, "Generating natural Telugu voice synthesis...")

            # Step 6: SYNCHRONIZING
            logger.info(f"[{job_id}] Step 6: Synchronizing speech with original timings...")
            job_store.update_status(job_id, JobStatus.SYNCHRONIZING, 75, "Matching durations and aligning Telugu speech with video...")
            speech_track = AudioSyncService.build_dubbed_speech_track(
                segments=segments,
                total_duration=meta.duration,
                work_dir=work_dir,
                voice_id=job.settings.voice_id
            )
            job_store.update_segments(job_id, segments)

            # Step 7: MIXING_AUDIO
            logger.info(f"[{job_id}] Step 7: Mixing audio...")
            mix_msg = "Preserving background audio and applying vocal ducking..." if job.settings.preserve_background else "Finalizing clean Telugu audio track..."
            job_store.update_status(job_id, JobStatus.MIXING_AUDIO, 85, mix_msg)
            final_audio = work_dir / "final_dubbed_audio.wav"
            AudioSyncService.mix_final_audio(
                original_stereo_audio=original_stereo,
                speech_track=speech_track,
                segments=segments,
                output_mixed_audio=final_audio,
                preserve_background=job.settings.preserve_background,
                ducking_db=job.settings.ducking_db
            )

            # Step 8: GENERATING_SUBTITLES & RENDERING
            logger.info(f"[{job_id}] Step 8: Generating refined Telugu subtitles & muxing video...")
            job_store.update_status(job_id, JobStatus.RENDERING, 92, "Generating broadcast-quality Telugu subtitles (.srt/.vtt)...")

            # Generate refined Telugu subtitles
            output_srt = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.srt"
            output_vtt = settings.OUTPUT_DIR / f"subtitles_{job_id}_{job.original_filename}.vtt"
            try:
                SubtitleService.generate_srt(segments, output_srt)
                SubtitleService.generate_vtt(segments, output_vtt)
            except Exception as e_sub:
                logger.warning(f"Failed to generate subtitles: {e_sub}")

            job_store.update_status(job_id, JobStatus.RENDERING, 94, "Muxing video stream with new Telugu audio track & subtitles...")
            MediaService.mux_video_audio(
                original_video_path=original_video,
                new_audio_path=final_audio,
                output_video_path=output_video,
                subtitle_path=output_srt if output_srt.exists() else None
            )

            # Generate video with burned-in Telugu subtitles for universal player support
            if output_srt.exists() and output_srt.stat().st_size > 0:
                try:
                    job_store.update_status(job_id, JobStatus.RENDERING, 96, "Rendering video with permanently visible Telugu subtitles...")
                    output_subtitled = settings.OUTPUT_DIR / f"dubbed_subtitled_{job_id}_{job.original_filename}"
                    MediaService.burn_subtitles(
                        video_path=output_video,
                        subtitle_path=output_srt,
                        output_path=output_subtitled
                    )
                except Exception as e_burn:
                    logger.warning(f"Failed to burn subtitles into video: {e_burn}")

            # Step 9: VALIDATING
            logger.info(f"[{job_id}] Step 9: Validating final media...")
            job_store.update_status(job_id, JobStatus.VALIDATING, 98, "Validating synchronized video output...")
            MediaService.validate_rendered_video(output_video, expected_min_duration=0.5)

            # Step 10: COMPLETED
            logger.info(f"[{job_id}] Step 10: Dubbing completed successfully!")
            job_store.set_completed(job_id, output_video)

        except Exception as e:
            err_msg = str(e)
            logger.error(f"[{job_id}] Pipeline failed: {err_msg}\n{traceback.format_exc()}")
            job_store.set_failed(job_id, err_msg)
        finally:
            # Clean up temporary working directory
            try:
                if work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)
            except Exception as e_clean:
                logger.warning(f"Failed to clean up temp dir {work_dir}: {e_clean}")
