import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.models.schemas import (
    DubbingJobResponse,
    JobProgressResponse,
    JobSettings,
    JobStatus,
    MediaMetadata,
    SpeechSegment,
)

from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "dubbing_jobs.db"

class JobStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    message TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    media_metadata TEXT,
                    settings TEXT NOT NULL,
                    segments TEXT,
                    original_video_path TEXT,
                    output_video_path TEXT,
                    error_message TEXT
                )
            """)
            conn.commit()
            conn.close()

    def create_job(
        self,
        job_id: str,
        original_filename: str,
        original_video_path: Path,
        job_settings: JobSettings
    ) -> DubbingJobResponse:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, original_filename, source_language, target_language,
                    status, progress, message, created_at, updated_at,
                    settings, original_video_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                original_filename,
                job_settings.source_language,
                job_settings.target_language,
                JobStatus.UPLOADED.value,
                5,
                "Video uploaded successfully. Ready to process.",
                now,
                now,
                job_settings.model_dump_json(),
                str(original_video_path)
            ))
            conn.commit()
            conn.close()

        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[DubbingJobResponse]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        media_meta = json.loads(row["media_metadata"]) if row["media_metadata"] else None
        settings_dict = json.loads(row["settings"])
        segments_raw = json.loads(row["segments"]) if row["segments"] else []
        segments = [SpeechSegment(**s) for s in segments_raw]

        out_url = f"/api/jobs/{job_id}/video/dubbed" if row["output_video_path"] else None
        orig_url = f"/api/jobs/{job_id}/video/original" if row["original_video_path"] else None

        return DubbingJobResponse(
            job_id=row["job_id"],
            status=JobStatus(row["status"]),
            progress=row["progress"],
            message=row["message"] or "",
            original_filename=row["original_filename"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            media_metadata=MediaMetadata(**media_meta) if media_meta else None,
            settings=JobSettings(**settings_dict),
            segments=segments,
            error_message=row["error_message"],
            output_video_url=out_url,
            original_video_url=orig_url
        )

    def update_status(self, job_id: str, status: JobStatus, progress: int, message: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET status = ?, progress = ?, message = ?, updated_at = ?
                WHERE job_id = ?
            """, (status.value, progress, message, now, job_id))
            conn.commit()
            conn.close()

    def update_metadata(self, job_id: str, metadata: MediaMetadata):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET media_metadata = ?, updated_at = ?
                WHERE job_id = ?
            """, (metadata.model_dump_json(), now, job_id))
            conn.commit()
            conn.close()

    def update_segments(self, job_id: str, segments: List[SpeechSegment]):
        now = datetime.now(timezone.utc).isoformat()
        segments_json = json.dumps([s.model_dump() for s in segments])
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET segments = ?, updated_at = ?
                WHERE job_id = ?
            """, (segments_json, now, job_id))
            conn.commit()
            conn.close()

    def set_completed(self, job_id: str, output_path: Path):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET status = ?, progress = 100, message = 'Dubbing completed successfully!',
                    output_video_path = ?, updated_at = ?
                WHERE job_id = ?
            """, (JobStatus.COMPLETED.value, str(output_path), now, job_id))
            conn.commit()
            conn.close()

    def set_failed(self, job_id: str, error_message: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs
                SET status = ?, message = 'Processing failed',
                    error_message = ?, updated_at = ?
                WHERE job_id = ?
            """, (JobStatus.FAILED.value, error_message, now, job_id))
            conn.commit()
            conn.close()

    def list_jobs(self, limit: int = 20) -> List[DubbingJobResponse]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        jobs = []
        for r in rows:
            job = self.get_job(r["job_id"])
            if job:
                jobs.append(job)
        return jobs

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted

job_store = JobStore()
