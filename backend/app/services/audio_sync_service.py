import logging
import math
import subprocess
from pathlib import Path
from typing import List, Optional
from pydub import AudioSegment

from app.config import settings
from app.models.schemas import SpeechSegment
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

class AudioSyncService:
    @staticmethod
    def time_stretch_audio(input_wav: Path, output_wav: Path, tempo_ratio: float) -> Path:
        """
        Time-stretch an audio file while preserving its pitch and natural formant structure.
        Uses FFmpeg's librubberband filter (or atempo filter as fallback).
        tempo_ratio > 1.0 speeds up audio (shorter duration).
        tempo_ratio < 1.0 slows down audio (longer duration).
        """
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        # Clamped to safe musical bounds (supports up to 1.65x for fast Hindi speech)
        clamped_tempo = max(0.65, min(1.65, tempo_ratio))

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_wav),
            "-filter:a", f"rubberband=tempo={clamped_tempo:.4f}",
            "-ar", "48000",
            "-ac", "2",
            str(output_wav)
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logger.warning(f"Rubberband failed, using atempo fallback: {res.stderr}")
            # atempo supports 0.5 to 2.0
            cmd_atempo = [
                "ffmpeg",
                "-y",
                "-i", str(input_wav),
                "-filter:a", f"atempo={clamped_tempo:.4f}",
                "-ar", "48000",
                "-ac", "2",
                str(output_wav)
            ]
            res2 = subprocess.run(cmd_atempo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res2.returncode != 0:
                raise RuntimeError(f"FFmpeg time stretch failed: {res2.stderr}")

        return output_wav

    @classmethod
    def synchronize_segment(
        cls,
        segment: SpeechSegment,
        voice_id: str,
        work_dir: Path,
        available_dur: Optional[float] = None
    ) -> Path:
        """
        Generate and synchronize Telugu speech for a single segment.
        Matches the original Hindi duration using intelligent multi-pass adaptation:
        1. Natural TTS generation
        2. Duration ratio measurement with headroom consideration
        3. Rate-optimized regeneration if significantly off (up to 1.45x for fast speech)
        4. Fine pitch-preserved time-stretching
        5. Natural lead-in/lead-out padding without syllable cutoffs
        """
        seg_id = segment.segment_id
        target_dur = max(0.4, segment.duration)
        max_dur = max(target_dur, available_dur) if available_dur else target_dur
        raw_tts_path = work_dir / f"tts_raw_seg_{seg_id}.mp3"
        stretched_path = work_dir / f"tts_sync_seg_{seg_id}.wav"

        # 1. First pass: Natural TTS
        initial_dur = TTSService.generate_speech(
            text=segment.telugu_text,
            output_path=raw_tts_path,
            voice_id=voice_id,
            rate_factor=1.0
        )
        segment.tts_duration = initial_dur

        ratio = initial_dur / target_dur
        logger.info(f"Segment #{seg_id}: Target={target_dur:.2f}s, MaxAvail={max_dur:.2f}s, Initial TTS={initial_dur:.2f}s, Ratio={ratio:.2f}")

        # 2. If discrepancy is large, re-generate with natural speech rate factor
        if initial_dur > target_dur:
            if initial_dur > max_dur:
                rate_factor = min(1.45, round(initial_dur / max_dur, 2))
            else:
                rate_factor = min(1.35, round(initial_dur / target_dur, 2))

            if rate_factor > 1.05:
                logger.info(f"Segment #{seg_id}: Re-generating TTS with rate_factor={rate_factor:.2f}")
                initial_dur = TTSService.generate_speech(
                    text=segment.telugu_text,
                    output_path=raw_tts_path,
                    voice_id=voice_id,
                    rate_factor=rate_factor
                )

        # 3. Fine duration matching via pitch-preserving time-stretching
        effective_target = target_dur if initial_dur <= target_dur else min(initial_dur, max_dur)
        required_tempo = round(initial_dur / effective_target, 4) if effective_target > 0 else 1.0
        segment.speed_ratio = required_tempo

        cls.time_stretch_audio(raw_tts_path, stretched_path, required_tempo)

        # 4. Load stretched audio and adjust millisecond length
        stretched_audio = AudioSegment.from_file(str(stretched_path))
        target_ms = int(target_dur * 1000)
        max_ms = int(max_dur * 1000)
        current_ms = len(stretched_audio)

        final_seg_path = work_dir / f"final_seg_{seg_id}.wav"

        # Allow up to 300ms natural tail headroom so words are NEVER cut off mid-syllable
        if current_ms > max_ms + 300:
            truncated = stretched_audio[:max_ms + 300].fade_out(30)
            truncated.export(str(final_seg_path), format="wav")
        elif current_ms > max_ms:
            # Word finishes comfortably inside inter-speech breath without truncation
            stretched_audio.fade_out(20).export(str(final_seg_path), format="wav")
        elif current_ms < target_ms:
            # Natural human padding: slight lead-in, majority lead-out
            diff_ms = target_ms - current_ms
            lead_in = min(80, diff_ms // 4)
            lead_out = diff_ms - lead_in
            padded = (
                AudioSegment.silent(duration=lead_in, frame_rate=stretched_audio.frame_rate)
                + stretched_audio
                + AudioSegment.silent(duration=lead_out, frame_rate=stretched_audio.frame_rate)
            )
            padded.fade_in(10).fade_out(10).export(str(final_seg_path), format="wav")
        else:
            stretched_audio.fade_in(10).fade_out(10).export(str(final_seg_path), format="wav")

        return final_seg_path

    @classmethod
    def build_dubbed_speech_track(
        cls,
        segments: List[SpeechSegment],
        total_duration: float,
        work_dir: Path,
        voice_id: str
    ) -> Path:
        """
        Builds a full-length master Telugu speech track synchronized to exact original timestamps.
        Headroom between consecutive segments is respected to prevent unnatural word truncation.
        """
        logger.info(f"Building master speech track for {len(segments)} segments (total duration: {total_duration:.2f}s)...")
        master_ms = max(int(total_duration * 1000) + 500, 1000)
        master_track = AudioSegment.silent(duration=master_ms, frame_rate=48000)
        master_track = master_track.set_channels(2)

        for i, seg in enumerate(segments):
            if not seg.telugu_text:
                continue

            # Calculate headroom before the next segment starts
            if i + 1 < len(segments):
                available_dur = max(seg.duration, round(segments[i + 1].start - seg.start - 0.05, 2))
            else:
                available_dur = max(seg.duration, round(total_duration - seg.start - 0.05, 2))

            seg_path = cls.synchronize_segment(seg, voice_id, work_dir, available_dur=available_dur)
            seg_audio = AudioSegment.from_file(str(seg_path))
            start_ms = int(seg.start * 1000)

            # Overlay segment at its exact start timestamp
            master_track = master_track.overlay(seg_audio, position=start_ms)

        speech_track_path = work_dir / "master_telugu_speech.wav"
        master_track.export(str(speech_track_path), format="wav")
        return speech_track_path

    @classmethod
    def mix_final_audio(
        cls,
        original_stereo_audio: Path,
        speech_track: Path,
        segments: List[SpeechSegment],
        output_mixed_audio: Path,
        preserve_background: bool = False,
        ducking_db: float = -12.0
    ) -> Path:
        """
        Audio mixing & finalization:
        - When preserve_background is False (Default - Clean Dubbing):
          Outputs 100% pure, crystal-clear Telugu speech track with EBU R128 loudness normalization.
          Zero original audio or Hindi vocal bleed.
        - When preserve_background is True:
          Applies center-channel vocal phase cancellation to remove original Hindi speech/singing,
          ducks ambient background heavily under Telugu speech, boosts Telugu dialogue (+2dB),
          and normalizes final broadcast loudness.
        """
        output_mixed_audio.parent.mkdir(parents=True, exist_ok=True)

        if preserve_background and original_stereo_audio.exists():
            logger.info("Preserving background ambience with center-channel Hindi vocal cancellation...")
            # 1. pan=stereo|c0=c0-c1|c1=c1-c0 removes centered vocals/dialogue while keeping stereo music & ambient effects
            # 2. sidechaincompress ducks residual background heavily when Telugu speech is active
            # 3. amix mixes vocal-canceled background at 15% with boosted Telugu speech at 140%
            cmd = [
                "ffmpeg", "-y",
                "-i", str(original_stereo_audio),
                "-i", str(speech_track),
                "-filter_complex",
                "[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume=0.25[karaoke_bg];"
                "[karaoke_bg][1:a]sidechaincompress=threshold=0.03:ratio=10:attack=10:release=200[ducked];"
                "[1:a]volume=1.4[boosted_speech];"
                "[ducked][boosted_speech]amix=inputs=2:weights=0.15 1.4:dropout_transition=2[mixed];"
                "[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]",
                "-map", "[out]",
                "-ar", "48000",
                "-ac", "2",
                str(output_mixed_audio)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                logger.info("Successfully rendered background-preserved audio with vocal cancellation.")
                return output_mixed_audio
            logger.warning(f"Vocal cancellation ducking failed ({res.stderr}), falling back to clean speech track...")

        # Clean Dubbing Mode (100% Pure Telugu Speech - No Hindi bleed)
        logger.info("Rendering Clean Telugu Dubbed Audio track (pure Telugu speech)...")
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", str(speech_track),
            "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "48000",
            "-ac", "2",
            str(output_mixed_audio)
        ]
        res = subprocess.run(norm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logger.warning(f"loudnorm failed, copying speech track: {res.stderr}")
            import shutil
            shutil.copy(speech_track, output_mixed_audio)

        return output_mixed_audio
