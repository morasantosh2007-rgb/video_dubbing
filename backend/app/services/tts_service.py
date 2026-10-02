import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from pydub import AudioSegment
import edge_tts
from gtts import gTTS

from app.config import settings
from app.models.schemas import VoiceOption

logger = logging.getLogger(__name__)

SUPPORTED_VOICES: List[VoiceOption] = [
    VoiceOption(
        voice_id="te-IN-MohanNeural",
        name="Mohan (Natural Male)",
        language="te",
        gender="Male",
        provider="edge-tts",
        sample_text="నమస్కారం, ఇది తెలుగు వాయిస్ డబ్బింగ్."
    ),
    VoiceOption(
        voice_id="te-IN-ShrutiNeural",
        name="Shruti (Natural Female)",
        language="te",
        gender="Female",
        provider="edge-tts",
        sample_text="నమస్కారం, ఇది తెలుగు వాయిస్ డబ్బింగ్."
    ),
    VoiceOption(
        voice_id="gtts-te",
        name="Google Telugu Standard",
        language="te",
        gender="Neutral",
        provider="gtts",
        sample_text="నమస్కారం"
    )
]

class TTSService:
    @staticmethod
    def get_available_voices(language: str = "te") -> List[VoiceOption]:
        """Return available voices filtered by language."""
        return [v for v in SUPPORTED_VOICES if v.language == language]

    @classmethod
    async def _generate_edge_tts(cls, text: str, voice_id: str, output_path: Path, rate_factor: float = 1.0) -> Path:
        """
        Generate natural speech using edge-tts with rate percentage.
        rate_factor: 1.0 = normal (+0%), 1.2 = +20%, 0.85 = -15%
        """
        pct = int(round((rate_factor - 1.0) * 100))
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"

        communicate = edge_tts.Communicate(text=text, voice=voice_id, rate=rate_str)
        await communicate.save(str(output_path))
        return output_path

    @classmethod
    def _generate_gtts(cls, text: str, output_path: Path) -> Path:
        """Fallback TTS using Google Text-to-Speech."""
        tts = gTTS(text=text, lang="te")
        tts.save(str(output_path))
        return output_path

    @classmethod
    def generate_speech(
        cls,
        text: str,
        output_path: Path,
        voice_id: Optional[str] = None,
        rate_factor: float = 1.0
    ) -> float:
        """
        Generate Telugu speech audio for a text segment and save to output_path.
        Returns the duration of the generated audio in seconds.
        """
        if not text or not text.strip():
            # Generate 100ms of silence
            silence = AudioSegment.silent(duration=100)
            silence.export(str(output_path), format="mp3")
            return 0.1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        chosen_voice = voice_id or settings.DEFAULT_TELUGU_VOICE

        try:
            if chosen_voice.startswith("gtts"):
                cls._generate_gtts(text, output_path)
            else:
                # Run async edge_tts in event loop
                asyncio.run(cls._generate_edge_tts(text, chosen_voice, output_path, rate_factor))
        except Exception as e:
            logger.warning(f"Primary TTS ({chosen_voice}) failed: {e}. Falling back to gTTS...")
            try:
                cls._generate_gtts(text, output_path)
            except Exception as e2:
                logger.error(f"Fallback gTTS also failed: {e2}")
                raise RuntimeError(f"TTS generation completely failed: {e2}")

        # Measure audio duration
        audio = AudioSegment.from_file(str(output_path))
        duration_sec = round(len(audio) / 1000.0, 3)
        logger.info(f"Generated TTS for '{text[:20]}...' -> duration: {duration_sec}s (rate: {rate_factor})")
        return duration_sec
