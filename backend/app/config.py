import os
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"

# Ensure runtime directories exist
for directory in (UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)

class Settings:
    PROJECT_NAME: str = "Hindi -> Telugu AI Video Dubbing"
    VERSION: str = "1.1.0"
    API_PREFIX: str = "/api"

    # Storage paths
    DATA_DIR: Path = DATA_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    OUTPUT_DIR: Path = OUTPUT_DIR
    TEMP_DIR: Path = TEMP_DIR

    # ASR Configuration
    # Options: "faster_whisper", "groq", "openai", "google"
    ASR_PROVIDER: str = os.getenv("ASR_PROVIDER", "faster_whisper")
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    # Translation Configuration
    # Options: "mymemory", "google", "gemini", "openai", "groq"
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "mymemory")

    # TTS Configuration
    # Options: "edge-tts", "gtts"
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "edge-tts")
    DEFAULT_TELUGU_VOICE: str = os.getenv("DEFAULT_TELUGU_VOICE", "te-IN-MohanNeural")
    DEFAULT_FEMALE_VOICE: str = os.getenv("DEFAULT_FEMALE_VOICE", "te-IN-ShrutiNeural")

    # API Keys (optional if using local/free providers)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Media Constraints
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    ALLOWED_EXTENSIONS: List[str] = [".mp4", ".mov", ".mkv", ".webm"]

    # Audio Mixing Configuration
    BACKGROUND_DUCKING_DB: float = float(os.getenv("BACKGROUND_DUCKING_DB", "-12.0"))
    PRESERVE_BACKGROUND_AUDIO: bool = os.getenv("PRESERVE_BACKGROUND_AUDIO", "false").lower() == "true"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

settings = Settings()
