import pytest
from pathlib import Path
from app.models.schemas import SpeechSegment
from app.services.translation_service import TranslationService
from app.services.tts_service import TTSService
from app.services.audio_sync_service import AudioSyncService
from app.config import settings

def test_translation_service():
    hindi_text = "आप कैसे हैं?"
    telugu_text = TranslationService.translate_segment(hindi_text, "hi", "te")
    assert telugu_text is not None
    assert len(telugu_text) > 0
    # Telugu characters should be in Unicode range 0x0C00-0x0C7F
    assert any('\u0c00' <= char <= '\u0c7f' for char in telugu_text)

def test_tts_service_generation(tmp_path):
    output_mp3 = tmp_path / "test_tts.mp3"
    duration = TTSService.generate_speech(
        text="నమస్కారం",
        output_path=output_mp3,
        voice_id="te-IN-MohanNeural",
        rate_factor=1.0
    )
    assert output_mp3.exists()
    assert duration > 0.1

def test_audio_time_stretch(tmp_path):
    # Generate audio
    raw_mp3 = tmp_path / "raw.mp3"
    TTSService.generate_speech("నమస్కారం", raw_mp3)
    
    stretched_wav = tmp_path / "stretched.wav"
    AudioSyncService.time_stretch_audio(raw_mp3, stretched_wav, tempo_ratio=1.2)
    assert stretched_wav.exists()
    assert stretched_wav.stat().st_size > 0
