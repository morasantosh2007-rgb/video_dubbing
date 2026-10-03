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
        import re
        model = get_whisper_model()
        logger.info(f"Transcribing {audio_path.name} with faster-whisper (lang={language})...")

        # Pattern to filter out pure music notation tokens
        MUSIC_TOKENS = re.compile(r"^(\[संगीत\]|\[music\]|\(संगीत\)|\(music\)|♪|♫|\[applause\]|\[cheering\]|\s)+$", re.IGNORECASE)

        HINDI_PROMPT = "यह एक स्पष्ट हिंदी संवाद या गीत है। कृपया केवल देवनागरी लिपि में लिखें। उदाहरण: केसरिया तेरा इश्क है पिया, रंग जाऊं जो मैं हाथ लगाऊं, दिन बीते सारा तेरी फिक्र में।"

        def _extract_segments(raw_segments) -> List[SpeechSegment]:
            extracted = []
            idx = 1
            for seg in raw_segments:
                text = seg.text.strip()
                if not text or MUSIC_TOKENS.match(text):
                    continue

                duration = round(seg.end - seg.start, 2)
                if duration <= 0:
                    continue

                # Filter out hallucination repetition loops & no-speech noise on music/outro
                no_speech = getattr(seg, "no_speech_prob", 0.0)
                if no_speech > 0.70:
                    continue

                comp_ratio = getattr(seg, "compression_ratio", 1.0)
                if comp_ratio > 2.4:
                    continue

                # Detect repeated syllable/word loops on instrumental sections
                if len(text) > 15 and len(set(text)) <= 6:
                    continue
                words = text.split()
                if len(words) >= 4 and len(set(words)) <= 2:
                    continue

                confidence = round(float(seg.avg_logprob), 3) if hasattr(seg, "avg_logprob") else None
                if confidence is not None and confidence < -1.25 and duration > 10.0:
                    continue

                extracted.append(
                    SpeechSegment(
                        segment_id=idx,
                        start=round(seg.start, 2),
                        end=round(seg.end, 2),
                        duration=duration,
                        hindi_text=text,
                        telugu_text="",
                        confidence=confidence,
                        speaker=f"Speaker {(idx % 2) + 1}" if idx > 4 else "Speaker 1"
                    )
                )
                idx += 1
            return extracted

        # Pass 1: Standard speech decoding with VAD filter (fast & ideal for dialogues/speech)
        try:
            logger.info("Pass 1: Attempting transcription with VAD filter...")
            raw_segs1, _ = model.transcribe(
                str(audio_path),
                language=language,
                task="transcribe",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=250),
                initial_prompt=HINDI_PROMPT
            )
            speech_segments = _extract_segments(raw_segs1)
            if speech_segments:
                max_seg_duration = max(s.duration for s in speech_segments)
                # If audio was collapsed into 1 or 2 mega-segments with music, fallback to fine-grained song acoustic decoding
                if len(speech_segments) <= 2 and max_seg_duration > 20.0:
                    logger.info(f"Pass 1 collapsed audio into {len(speech_segments)} long segment(s) ({max_seg_duration}s). Song/music detected. Switching to fine-grained acoustic decoding...")
                else:
                    logger.info(f"Pass 1 (VAD) succeeded: {len(speech_segments)} speech segments detected.")
                    return speech_segments
        except Exception as e:
            logger.warning(f"Pass 1 (VAD) error: {e}")

        # Pass 2: Full acoustic decoding without VAD (essential for songs, singing, rap, and videos with heavy background music)
        try:
            logger.info("Pass 2: VAD yielded 0 segments (song/music detected). Retrying with full acoustic decoding (vad_filter=False)...")
            raw_segs2, _ = model.transcribe(
                str(audio_path),
                language=language,
                task="transcribe",
                vad_filter=False,
                condition_on_previous_text=False,
                beam_size=5,
                best_of=5,
                initial_prompt=HINDI_PROMPT
            )
            speech_segments = _extract_segments(raw_segs2)
            if speech_segments:
                logger.info(f"Pass 2 (Song/Music Mode) succeeded: {len(speech_segments)} lyrical/speech segments detected.")
                return speech_segments
        except Exception as e:
            logger.warning(f"Pass 2 (Song Mode) error: {e}")

        # Pass 3: Vocal frequency bandpass isolation (200Hz - 3800Hz) to separate vocals from heavy instruments/drums
        enhanced_path = audio_path.parent / f"vocal_enhanced_{audio_path.name}"
        try:
            logger.info("Pass 3: Isolating vocal formant frequencies with FFmpeg bandpass filter...")
            from app.services.media_service import MediaService
            MediaService.isolate_vocal_frequencies(audio_path, enhanced_path)
            raw_segs3, _ = model.transcribe(
                str(enhanced_path),
                language=language,
                task="transcribe",
                vad_filter=False,
                condition_on_previous_text=False,
                beam_size=5
            )
            speech_segments = _extract_segments(raw_segs3)
            if speech_segments:
                logger.info(f"Pass 3 (Vocal-Isolated Mode) succeeded: {len(speech_segments)} segments detected.")
                return speech_segments
        except Exception as e:
            logger.warning(f"Pass 3 (Vocal-Isolated Mode) error: {e}")
        finally:
            if enhanced_path.exists():
                try:
                    enhanced_path.unlink()
                except Exception:
                    pass

        # Pass 4: Auto-detect language (for code-mixed, Hinglish, or dialect songs)
        try:
            logger.info("Pass 4: Retrying with auto-language detection...")
            raw_segs4, _ = model.transcribe(
                str(audio_path),
                language=None,
                task="transcribe",
                vad_filter=False,
                condition_on_previous_text=False
            )
            speech_segments = _extract_segments(raw_segs4)
            if speech_segments:
                logger.info(f"Pass 4 (Auto-Detect Mode) succeeded: {len(speech_segments)} segments detected.")
                return speech_segments
        except Exception as e:
            logger.warning(f"Pass 4 error: {e}")

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
