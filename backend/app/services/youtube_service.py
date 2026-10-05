import logging
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import yt_dlp

logger = logging.getLogger(__name__)

class YouTubeService:
    YOUTUBE_URL_REGEX = re.compile(
        r'^(https?://)?(www\.|m\.)?(youtube\.com/(watch\?.*v=|shorts/|embed/)|youtu\.be/)([\w-]{11})',
        re.IGNORECASE
    )

    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        """Check if a URL matches common YouTube formats."""
        if not url or not isinstance(url, str):
            return False
        clean = url.strip()
        return bool(cls.YOUTUBE_URL_REGEX.search(clean))

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extract the 11-character YouTube video ID."""
        match = cls.YOUTUBE_URL_REGEX.search(url.strip())
        if match:
            return match.group(5)
        return None

    @classmethod
    def get_video_info(cls, url: str, max_duration: int = 900) -> Dict[str, Any]:
        """
        Fast inspection of YouTube metadata without downloading video stream.
        Validates url, live streams, and duration limit (default: 15 minutes).
        """
        if not cls.is_valid_youtube_url(url):
            raise ValueError("Invalid YouTube URL. Please provide a valid youtube.com or youtu.be link.")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'noplaylist': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url.strip(), download=False)
        except Exception as e:
            logger.error(f"Failed to fetch YouTube metadata: {e}")
            raise ValueError(f"Could not access YouTube video: {str(e)}")

        if not info:
            raise ValueError("No video metadata returned from YouTube.")

        is_live = info.get('is_live', False) or (info.get('was_live', False) and info.get('live_status') == 'is_live')
        if is_live:
            raise ValueError("Live streams cannot be dubbed. Please provide a link to a recorded video.")

        duration = info.get('duration')
        if duration and duration > max_duration:
            mins = int(duration // 60)
            secs = int(duration % 60)
            max_mins = max_duration // 60
            raise ValueError(f"Video length ({mins}m {secs}s) exceeds the maximum allowed limit of {max_mins} minutes.")

        title = info.get('title') or "youtube_video"
        return {
            "id": info.get('id') or cls.extract_video_id(url),
            "title": title,
            "duration": duration or 0,
            "uploader": info.get('uploader') or "Unknown",
            "thumbnail": info.get('thumbnail') or "",
        }

    @classmethod
    def download_video(
        cls,
        url: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Path:
        """
        Download YouTube video stream up to 720p HD with merged audio into an MP4 file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = output_path.parent / f"yt_tmp_{output_path.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_out_template = temp_dir / "video.%(ext)s"

        def _progress_hook(d):
            if progress_callback and d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    pct = int(min(90, max(5, (downloaded / total) * 100)))
                    mb = round(downloaded / (1024 * 1024), 1)
                    tot_mb = round(total / (1024 * 1024), 1)
                    progress_callback(pct, f"Downloading YouTube video: {mb}MB / {tot_mb}MB ({pct}%)")

        ydl_opts = {
            'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
            'outtmpl': str(temp_out_template),
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'progress_hooks': [_progress_hook] if progress_callback else [],
        }

        try:
            logger.info(f"Downloading YouTube video from {url} to {temp_dir}...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url.strip()])

            # Find the merged file
            downloaded_files = list(temp_dir.glob("video.*"))
            if not downloaded_files:
                raise FileNotFoundError("yt-dlp completed but output file was not found.")

            merged_file = temp_dir / "video.mp4"
            if not merged_file.exists():
                merged_file = downloaded_files[0]

            if output_path.exists():
                output_path.unlink()

            shutil.move(str(merged_file), str(output_path))
            logger.info(f"Successfully downloaded YouTube video to {output_path} (size: {output_path.stat().st_size} bytes)")
            return output_path

        except Exception as e:
            logger.error(f"Error downloading YouTube video: {e}")
            raise RuntimeError(f"Failed to download YouTube video: {str(e)}")
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
