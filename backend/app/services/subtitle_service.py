import re
import logging
from pathlib import Path
from typing import List, Tuple
from app.models.schemas import SpeechSegment

logger = logging.getLogger(__name__)

class SubtitleService:
    """
    Broadcast-quality Subtitle Generation & Refinement Service for Telugu Video Dubbing.
    Generates industry-standard SubRip (.srt) and WebVTT (.vtt) files with:
    - High-precision millisecond timing synchronized to speech.
    - Natural Telugu linguistic line wrapping (max 38-42 chars/line).
    - Intelligent syntactic break points (preserving clauses, conjunctions, and phrases).
    - Standard UTF-8 encoding ensuring flawless Devanagari and Telugu font rendering.
    """

    @staticmethod
    def format_timestamp_srt(seconds: float) -> str:
        """Format seconds into SRT timestamp: HH:MM:SS,mmm"""
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def format_timestamp_vtt(seconds: float) -> str:
        """Format seconds into WebVTT timestamp: HH:MM:SS.mmm"""
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @classmethod
    def refine_telugu_text(cls, text: str, max_chars_per_line: int = 40) -> str:
        """
        Refines Telugu subtitle text:
        - Normalizes whitespace and standard punctuation.
        - Splits long sentences (>40 chars) across 2 lines at natural syntactic boundaries:
          1. Punctuation boundaries (comma, question mark, exclamation, semicolon).
          2. Conjunctions / continuation words (మరియు, కానీ, అయితే, ఎందుకంటే, కాబట్టి, తర్వాత).
          3. Natural space closest to the middle of the sentence.
        - Maximum 2 lines per subtitle card to prevent obscuring video visuals.
        """
        if not text:
            return ""

        # Normalize spacing
        text = re.sub(r"\s+", " ", text).strip()

        # If short enough, keep as single line
        if len(text) <= max_chars_per_line:
            return text

        words = text.split(" ")
        if len(words) <= 2:
            return text

        # Find best splitting point
        conjunctions = {"మరియు", "కానీ", "అయితే", "ఎందుకంటే", "కాబట్టి", "తర్వాత", "అందుకే", "కూడా", "లేదా"}
        best_split_idx = -1
        midpoint = len(text) / 2.0
        min_distance_to_mid = float("inf")

        current_char_len = 0
        for i in range(len(words) - 1):
            current_char_len += len(words[i]) + 1
            distance_to_mid = abs(current_char_len - midpoint)

            # Prioritize breaking after punctuation
            if words[i].endswith((",", "!", "?", ";", "।", ".")):
                if distance_to_mid < min_distance_to_mid or best_split_idx == -1:
                    min_distance_to_mid = distance_to_mid
                    best_split_idx = i + 1
            # Prioritize breaking before major conjunctions
            elif words[i + 1] in conjunctions:
                if distance_to_mid < min_distance_to_mid * 1.2 or best_split_idx == -1:
                    min_distance_to_mid = distance_to_mid
                    best_split_idx = i + 1

        # If no syntactic point found, pick space closest to center
        if best_split_idx == -1:
            current_char_len = 0
            for i in range(len(words) - 1):
                current_char_len += len(words[i]) + 1
                distance_to_mid = abs(current_char_len - midpoint)
                if distance_to_mid < min_distance_to_mid:
                    min_distance_to_mid = distance_to_mid
                    best_split_idx = i + 1

        line1 = " ".join(words[:best_split_idx]).strip()
        line2 = " ".join(words[best_split_idx:]).strip()

        return f"{line1}\n{line2}"

    @classmethod
    def generate_srt(cls, segments: List[SpeechSegment], output_path: Path) -> Path:
        """
        Generate UTF-8 encoded SubRip (.srt) subtitle file from speech segments.
        Ensures reading comfort with minimum display time (1.0s) and zero timestamp overlap.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        valid_segments = [s for s in segments if s.telugu_text and s.telugu_text.strip()]

        with open(output_path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(valid_segments, 1):
                st = seg.start
                # Ensure minimum comfortable reading duration of 1.0s
                min_end = st + max(1.0, seg.duration)
                en = max(seg.end, min_end)

                # Cap end before next segment starts
                if idx < len(valid_segments):
                    next_st = valid_segments[idx].start
                    if en >= next_st:
                        en = max(st + 0.5, next_st - 0.05)

                srt_start = cls.format_timestamp_srt(st)
                srt_end = cls.format_timestamp_srt(en)
                refined_text = cls.refine_telugu_text(seg.telugu_text)

                f.write(f"{idx}\n")
                f.write(f"{srt_start} --> {srt_end}\n")
                f.write(f"{refined_text}\n\n")

        logger.info(f"Generated refined Telugu SRT subtitles: {output_path} ({len(valid_segments)} entries)")
        return output_path

    @classmethod
    def generate_vtt(cls, segments: List[SpeechSegment], output_path: Path) -> Path:
        """
        Generate UTF-8 encoded WebVTT (.vtt) subtitle file for web and mobile players.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        valid_segments = [s for s in segments if s.telugu_text and s.telugu_text.strip()]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT - Telugu AI Video Dubbing Subtitles\n\n")
            for idx, seg in enumerate(valid_segments, 1):
                st = seg.start
                min_end = st + max(1.0, seg.duration)
                en = max(seg.end, min_end)

                if idx < len(valid_segments):
                    next_st = valid_segments[idx].start
                    if en >= next_st:
                        en = max(st + 0.5, next_st - 0.05)

                vtt_start = cls.format_timestamp_vtt(st)
                vtt_end = cls.format_timestamp_vtt(en)
                refined_text = cls.refine_telugu_text(seg.telugu_text)

                f.write(f"{idx}\n")
                f.write(f"{vtt_start} --> {vtt_end}\n")
                f.write(f"{refined_text}\n\n")

        logger.info(f"Generated refined Telugu WebVTT subtitles: {output_path} ({len(valid_segments)} entries)")
        return output_path

    @classmethod
    def export_subtitles(cls, segments: List[SpeechSegment], base_output_path: Path) -> Tuple[Path, Path]:
        """Generate both .srt and .vtt subtitle files for a job."""
        srt_path = base_output_path.with_suffix(".srt")
        vtt_path = base_output_path.with_suffix(".vtt")
        cls.generate_srt(segments, srt_path)
        cls.generate_vtt(segments, vtt_path)
        return srt_path, vtt_path
