from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class JobStatus(str, Enum):
    UPLOADED = "UPLOADED"
    DOWNLOADING = "DOWNLOADING"
    ANALYZING = "ANALYZING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_TELUGU_AUDIO = "GENERATING_TELUGU_AUDIO"
    SYNCHRONIZING = "SYNCHRONIZING"
    MIXING_AUDIO = "MIXING_AUDIO"
    RENDERING = "RENDERING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SpeechSegment(BaseModel):
    segment_id: int
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    duration: float = Field(..., description="Duration in seconds")
    hindi_text: str = Field(..., description="Transcribed Hindi speech")
    telugu_text: str = Field(default="", description="Translated Telugu speech")
    speaker: Optional[str] = Field(default="Speaker 1", description="Detected speaker identifier")
    confidence: Optional[float] = Field(default=None, description="Recognition confidence")
    tts_duration: Optional[float] = Field(default=None, description="Generated TTS audio duration")
    speed_ratio: Optional[float] = Field(default=None, description="Time stretch/speed adaptation ratio")

class MediaMetadata(BaseModel):
    filename: str
    file_size_mb: float
    duration: float
    resolution: str
    video_codec: str
    audio_codec: Optional[str] = None
    has_audio: bool = True
    fps: Optional[float] = None
    sample_rate: Optional[int] = None

class JobSettings(BaseModel):
    source_language: str = "hi"
    target_language: str = "te"
    voice_id: str = "te-IN-MohanNeural"
    speaking_rate: float = 1.0
    preserve_background: bool = True
    ducking_db: float = -12.0

class YoutubeJobRequest(BaseModel):
    url: str = Field(..., description="Direct YouTube video or Shorts URL")
    source_language: str = Field(default="hi", description="Source spoken language code")
    target_language: str = Field(default="te", description="Target dubbing language code")
    voice_id: str = Field(default="te-IN-MohanNeural", description="TTS voice identifier")
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate adjustment")
    preserve_background: bool = Field(default=False, description="Whether to duck background ambience")
    ducking_db: float = Field(default=-12.0, description="Background ducking depth in dB")


class JobProgressResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(..., ge=0, le=100)
    message: str
    current_step: str

class DubbingJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    message: str = ""
    original_filename: str
    created_at: str
    updated_at: str
    media_metadata: Optional[MediaMetadata] = None
    settings: JobSettings
    segments: List[SpeechSegment] = []
    error_message: Optional[str] = None
    output_video_url: Optional[str] = None
    original_video_url: Optional[str] = None
    subtitles_srt_url: Optional[str] = None
    subtitles_vtt_url: Optional[str] = None

class VoiceOption(BaseModel):
    voice_id: str
    name: str
    language: str
    gender: str
    provider: str
    sample_text: str = ""

class LanguageOption(BaseModel):
    code: str
    name: str
    native_name: str
