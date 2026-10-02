import logging
import os
from pathlib import Path
from typing import List, Optional
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

from app.config import settings
from app.models.schemas import SpeechSegment

logger = logging.getLogger(__name__)

import faster_whisper.audio
import faster_whisper.transcribe
import numpy as np
import subprocess

def _patched_decode_audio(input_file, sampling_rate=16000, split_stereo=False):
    """Robust FFmpeg-based audio decoder that avoids PyAV 19 metadata_errors incompatibility."""
    cmd = [
        "ffmpeg", "-nostdin", "-threads", "0", "-i", str(input_file),
        "-f", "s16le", "-ac", "1" if not split_stereo else "2",
        "-acodec", "pcm_s16le", "-ar", str(sampling_rate), "-"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    audio = np.frombuffer(res.stdout, np.int16).flatten().astype(np.float32) / 32768.0
    if split_stereo:
        return audio[0::2], audio[1::2]
    return audio

# Apply patch to faster-whisper modules
faster_whisper.audio.decode_audio = _patched_decode_audio
faster_whisper.transcribe.decode_audio = _patched_decode_audio

# Cache for faster-whisper model instance to avoid reloading per request
_WHISPER_MODEL = None

def get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        logger.info(f"Loading faster-whisper model: {settings.WHISPER_MODEL_SIZE} on {settings.WHISPER_DEVICE}")
        _WHISPER_MODEL = WhisperModel(
            model_size_or_path=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            download_root=str(settings.DATA_DIR / "models" / "whisper")
        )
    return _WHISPER_MODEL

class ASRService:
    @classmethod
    def transcribe(cls, audio_path: Path, language: str = "hi") -> List[SpeechSegment]:
        """
        Transcribe speech from an audio file with timestamps.
        Prioritizes configured provider:
        1. faster_whisper (local high-accuracy model with VAD)
        2. groq (Groq Whisper-large-v3)
        3. openai (OpenAI Whisper)
        4. google (Google SpeechRecognition + silence detection)
        """
        provider = settings.ASR_PROVIDER.lower()

        if provider == "groq" and settings.GROQ_API_KEY:
            try:
                return cls._transcribe_groq(audio_path, language)
            except Exception as e:
                logger.warning(f"Groq ASR failed ({e}), falling back to faster-whisper...")

        if provider == "openai" and settings.OPENAI_API_KEY:
            try:
                return cls._transcribe_openai(audio_path, language)
            except Exception as e:
                logger.warning(f"OpenAI ASR failed ({e}), falling back to faster-whisper...")

        # Default & primary: faster-whisper
        try:
            return cls._transcribe_faster_whisper(audio_path, language)
        except Exception as e:
            logger.warning(f"faster-whisper failed ({e}), falling back to silence-chunking ASR...")
            return cls._transcribe_silence_chunking(audio_path, language)

    @classmethod
    def _transcribe_faster_whisper(cls, audio_path: Path, language: str = "hi") -> List[SpeechSegment]:
        model = get_whisper_model()
        logger.info(f"Transcribing {audio_path.name} with faster-whisper (lang={language})...")

        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=200)
        )

        speech_segments: List[SpeechSegment] = []
        seg_idx = 1

        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            duration = round(seg.end - seg.start, 2)
            if duration <= 0:
                continue

            confidence = round(float(seg.avg_logprob), 3) if hasattr(seg, "avg_logprob") else None

            speech_segments.append(
                SpeechSegment(
                    segment_id=seg_idx,
                    start=round(seg.start, 2),
                    end=round(seg.end, 2),
                    duration=duration,
                    hindi_text=text,
                    telugu_text="",
                    confidence=confidence,
                    speaker=f"Speaker {(seg_idx % 2) + 1}" if seg_idx > 4 else "Speaker 1"
                )
            )
            seg_idx += 1

        logger.info(f"Detected {len(speech_segments)} speech segments via faster-whisper")
        return speech_segments

    @classmethod
    def _transcribe_groq(cls, audio_path: Path, language: str = "hi") -> List[SpeechSegment]:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)

        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_path.name, file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language=language,
                temperature=0.0
            )

        speech_segments = []
        segments_data = getattr(transcription, "segments", []) or []
        for i, s in enumerate(segments_data, start=1):
            text = s.get("text", "").strip() if isinstance(s, dict) else getattr(s, "text", "").strip()
            start = float(s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0))
            end = float(s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0))
            if text and end > start:
                speech_segments.append(
                    SpeechSegment(
                        segment_id=i,
                        start=round(start, 2),
                        end=round(end, 2),
                        duration=round(end - start, 2),
                        hindi_text=text,
                        telugu_text="",
                        speaker="Speaker 1"
                    )
                )
        return speech_segments

    @classmethod
    def _transcribe_openai(cls, audio_path: Path, language: str = "hi") -> List[SpeechSegment]:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=file,
                model="whisper-1",
                response_format="verbose_json",
                language=language
            )

        speech_segments = []
        segments_data = getattr(transcription, "segments", []) or []
        for i, s in enumerate(segments_data, start=1):
            text = s.get("text", "").strip() if isinstance(s, dict) else getattr(s, "text", "").strip()
            start = float(s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0))
            end = float(s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0))
            if text and end > start:
                speech_segments.append(
                    SpeechSegment(
                        segment_id=i,
                        start=round(start, 2),
                        end=round(end, 2),
                        duration=round(end - start, 2),
                        hindi_text=text,
                        telugu_text="",
                        speaker="Speaker 1"
                    )
                )
        return speech_segments

    @classmethod
    def _transcribe_silence_chunking(cls, audio_path: Path, language: str = "hi") -> List[SpeechSegment]:
        """
        Silence-based chunking with Google SpeechRecognition as fallback.
        """
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        sound = AudioSegment.from_file(str(audio_path))
        
        # Detect non-silent chunks (speech intervals)
        silence_thresh = sound.dBFS - 14
        intervals = detect_nonsilent(sound, min_silence_len=500, silence_thresh=silence_thresh, seek_step=20)

        speech_segments: List[SpeechSegment] = []
        seg_idx = 1

        for start_ms, end_ms in intervals:
            chunk = sound[start_ms:end_ms]
            chunk_path = settings.TEMP_DIR / f"chunk_{seg_idx}.wav"
            chunk.export(str(chunk_path), format="wav")

            try:
                with sr.AudioFile(str(chunk_path)) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language="hi-IN")
                    if text.strip():
                        start_sec = round(start_ms / 1000.0, 2)
                        end_sec = round(end_ms / 1000.0, 2)
                        speech_segments.append(
                            SpeechSegment(
                                segment_id=seg_idx,
                                start=start_sec,
                                end=end_sec,
                                duration=round(end_sec - start_sec, 2),
                                hindi_text=text.strip(),
                                telugu_text="",
                                speaker="Speaker 1"
                            )
                        )
                        seg_idx += 1
            except Exception as e:
                logger.debug(f"Chunk {seg_idx} speech recognition error: {e}")
            finally:
                if chunk_path.exists():
                    try:
                        chunk_path.unlink()
                    except Exception:
                        pass

        return speech_segments
