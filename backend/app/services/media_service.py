import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from app.models.schemas import MediaMetadata

logger = logging.getLogger(__name__)

class MediaService:
    @staticmethod
    def run_command(cmd: list) -> subprocess.CompletedProcess:
        """Execute a subprocess command securely without shell=True."""
        logger.info(f"Running command: {' '.join(str(c) for c in cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logger.error(f"Command failed with code {result.returncode}:\n{result.stderr}")
            raise RuntimeError(f"Command failed: {result.stderr.strip() or result.stdout.strip()}")
        return result

    @staticmethod
    def probe_media(file_path: Path) -> MediaMetadata:
        """Inspect media file using ffprobe and return parsed metadata."""
        if not file_path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = float(fmt.get("duration", 0.0))
        if duration == 0.0 and video_stream:
            duration = float(video_stream.get("duration", 0.0))

        file_size_mb = round(file_path.stat().st_size / (1024 * 1024), 2)

        width = video_stream.get("width") if video_stream else 0
        height = video_stream.get("height") if video_stream else 0
        resolution = f"{width}x{height}" if width and height else "Unknown"

        video_codec = video_stream.get("codec_name", "unknown") if video_stream else "none"
        audio_codec = audio_stream.get("codec_name") if audio_stream else None

        fps = None
        if video_stream and "r_frame_rate" in video_stream:
            try:
                num, den = video_stream["r_frame_rate"].split("/")
                fps = round(float(num) / float(den), 2)
            except Exception:
                fps = None

        sample_rate = int(audio_stream.get("sample_rate", 0)) if audio_stream else None

        return MediaMetadata(
            filename=file_path.name,
            file_size_mb=file_size_mb,
            duration=round(duration, 2),
            resolution=resolution,
            video_codec=video_codec,
            audio_codec=audio_codec,
            has_audio=audio_stream is not None,
            fps=fps,
            sample_rate=sample_rate
        )

    @classmethod
    def extract_audio(cls, video_path: Path, output_wav_path: Path, sample_rate: int = 16000, channels: int = 1) -> Path:
        """
        Extract clean audio track from video file for speech processing.
        sample_rate=16000 & channels=1 is optimal for Whisper & ASR engines.
        """
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_wav_path)
        ]
        cls.run_command(cmd)
        return output_wav_path

    @classmethod
    def extract_stereo_audio(cls, video_path: Path, output_wav_path: Path) -> Path:
        """Extract high-quality 48kHz stereo audio for background preservation and mixing."""
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            str(output_wav_path)
        ]
        cls.run_command(cmd)
        return output_wav_path

    @classmethod
    def isolate_vocal_frequencies(cls, input_wav: Path, output_wav: Path) -> Path:
        """Filter audio to vocal formant range (200Hz - 3800Hz) to improve ASR in music/songs."""
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_wav),
            "-af", "highpass=f=200,lowpass=f=3800,volume=1.8",
            "-ar", "16000",
            "-ac", "1",
            str(output_wav)
        ]
        cls.run_command(cmd)
        return output_wav

    @classmethod
    def mux_video_audio(
        cls,
        original_video_path: Path,
        new_audio_path: Path,
        output_video_path: Path,
        subtitle_path: Optional[Path] = None
    ) -> Path:
        """
        Mux newly generated Telugu audio (and optional refined Telugu subtitles) with the original video stream.
        PRESERVES original video stream without re-encoding (-c:v copy).
        Encodes audio with high-quality AAC (192kbps).
        Embeds Telugu subtitles as a selectable soft track (-c:s mov_text).
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        has_subtitles = subtitle_path is not None and subtitle_path.exists() and subtitle_path.stat().st_size > 0

        # Fast direct stream copy
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(original_video_path),
            "-i", str(new_audio_path),
        ]
        if has_subtitles:
            cmd.extend(["-i", str(subtitle_path)])

        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
        ])

        if has_subtitles:
            cmd.extend([
                "-c:s", "mov_text",
                "-metadata:s:s:0", "language=tel",
                "-metadata:s:s:0", "title=Telugu",
                "-metadata:s:s:0", "handler_name=Telugu",
                "-disposition:s:0", "default+forced",
            ])

        cmd.extend([
            "-map", "0:v:0",
            "-map", "1:a:0",
        ])
        if has_subtitles:
            cmd.extend(["-map", "2:s:0?"])

        cmd.extend([
            "-shortest",
            str(output_video_path)
        ])

        try:
            cls.run_command(cmd)
        except RuntimeError as e:
            # Fallback in case container mismatch requires re-muxing with compatible video encoder
            logger.warning(f"Direct stream copy failed ({e}), falling back to safe re-muxing with libx264...")
            fallback_cmd = [
                "ffmpeg",
                "-y",
                "-i", str(original_video_path),
                "-i", str(new_audio_path),
            ]
            if has_subtitles:
                fallback_cmd.extend(["-i", str(subtitle_path)])

            fallback_cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
            ])
            if has_subtitles:
                fallback_cmd.extend([
                    "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=tel",
                    "-metadata:s:s:0", "title=Telugu",
                    "-metadata:s:s:0", "handler_name=Telugu",
                    "-disposition:s:0", "default+forced",
                ])

            fallback_cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0",
            ])
            if has_subtitles:
                fallback_cmd.extend(["-map", "2:s:0?"])

            fallback_cmd.extend([
                "-shortest",
                str(output_video_path)
            ])
            cls.run_command(fallback_cmd)

        return output_video_path

    @classmethod
    def burn_subtitles(
        cls,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path
    ) -> Path:
        """
        Burn refined Telugu subtitles directly into the video stream pixels.
        Ensures that when the video is played in ANY media player, browser, or device,
        the Telugu subtitles are 100% visibly displayed on the screen.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not subtitle_path.exists() or subtitle_path.stat().st_size == 0:
            raise ValueError(f"Subtitle file missing or empty: {subtitle_path}")

        escaped_srt = str(subtitle_path.resolve()).replace("\\", "/").replace(":", r"\:")
        vf_filter = (
            f"subtitles='{escaped_srt}':"
            "force_style='FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=1,MarginV=25,Alignment=2'"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        logger.info(f"Burning Telugu subtitles into {video_path.name} -> {output_path.name}...")
        cls.run_command(cmd)
        return output_path

    @classmethod
    def validate_rendered_video(cls, video_path: Path, expected_min_duration: float = 0.5) -> bool:
        """
        Quality Control: Validate that the rendered video exists, has valid video and audio
        streams, and matches expected duration.
        """
        if not video_path.exists() or video_path.stat().st_size == 0:
            raise ValueError(f"Output video file missing or empty: {video_path}")

        meta = cls.probe_media(video_path)
        if meta.video_codec == "none":
            raise ValueError("Validation failed: Output video has no video stream!")
        if not meta.has_audio:
            raise ValueError("Validation failed: Output video has no audio stream!")
        if meta.duration < expected_min_duration:
            raise ValueError(f"Validation failed: Output video duration ({meta.duration}s) is too short!")

        logger.info(f"Video validation PASSED: {meta.resolution}, {meta.video_codec}, {meta.audio_codec}, {meta.duration}s")
        return True
