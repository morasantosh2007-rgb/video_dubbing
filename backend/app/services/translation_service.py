import logging
from typing import List, Optional
from deep_translator import MyMemoryTranslator, GoogleTranslator

from app.config import settings
from app.models.schemas import SpeechSegment

logger = logging.getLogger(__name__)

class TranslationService:
    @classmethod
    def translate_segment(cls, text: str, source_lang: str = "hi", target_lang: str = "te") -> str:
        """
        Translate a single sentence/segment from Hindi to Telugu preserving context and conversational intent.
        Tries providers in resilient order:
        1. Gemini (if GEMINI_API_KEY is available)
        2. OpenAI (if OPENAI_API_KEY is available)
        3. Groq (if GROQ_API_KEY is available)
        4. MyMemoryTranslator (Neural free API with hi-IN / te-IN language pairing)
        5. GoogleTranslator fallback
        """
        if not text or not text.strip():
            return ""

        text = text.strip()

        # 1. Gemini AI translation (most contextual and natural)
        if settings.GEMINI_API_KEY and settings.TRANSLATION_PROVIDER == "gemini":
            try:
                return cls._translate_gemini(text, source_lang, target_lang)
            except Exception as e:
                logger.warning(f"Gemini translation failed ({e}), trying fallback...")

        # 2. OpenAI translation
        if settings.OPENAI_API_KEY and settings.TRANSLATION_PROVIDER == "openai":
            try:
                return cls._translate_openai(text, source_lang, target_lang)
            except Exception as e:
                logger.warning(f"OpenAI translation failed ({e}), trying fallback...")

        # 3. Groq translation
        if settings.GROQ_API_KEY and settings.TRANSLATION_PROVIDER == "groq":
            try:
                return cls._translate_groq(text, source_lang, target_lang)
            except Exception as e:
                logger.warning(f"Groq translation failed ({e}), trying fallback...")

        # 4. MyMemory Neural Translation
        try:
            src = "hi-IN" if source_lang == "hi" else source_lang
            tgt = "te-IN" if target_lang == "te" else target_lang
            translated = MyMemoryTranslator(source=src, target=tgt).translate(text)
            if translated and not translated.startswith("MYMEMORY WARNING"):
                return translated.strip()
        except Exception as e:
            logger.debug(f"MyMemory translation failed: {e}")

        # 5. Google Web Translator fallback
        try:
            translated = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
            if translated:
                return translated.strip()
        except Exception as e:
            logger.debug(f"GoogleTranslator fallback failed: {e}")

        # Final fallback: return original text if all failed
        logger.error(f"All translation providers failed for text: {text}")
        return text

    @classmethod
    def translate_segments(cls, segments: List[SpeechSegment], source_lang: str = "hi", target_lang: str = "te") -> List[SpeechSegment]:
        """Translate all speech segments preserving sequential context."""
        logger.info(f"Translating {len(segments)} segments from {source_lang} to {target_lang}...")
        for seg in segments:
            if seg.hindi_text:
                seg.telugu_text = cls.translate_segment(seg.hindi_text, source_lang, target_lang)
                logger.info(f"Segment #{seg.segment_id}: '{seg.hindi_text}' -> '{seg.telugu_text}'")
        return segments

    @classmethod
    def _translate_gemini(cls, text: str, source_lang: str, target_lang: str) -> str:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            f"You are a professional video dubbing translator. Translate the following spoken {source_lang} dialogue "
            f"into natural conversational {target_lang} suitable for voice actors. Match the cadence and length closely. "
            f"Only return the raw translated text with no explanations or quotes.\n\nDialogue: {text}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    @classmethod
    def _translate_openai(cls, text: str, source_lang: str, target_lang: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Translate conversational {source_lang} speech into natural {target_lang} dubbing dialogue. Match length and cadence. Output only translated text."
                },
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()

    @classmethod
    def _translate_groq(cls, text: str, source_lang: str, target_lang: str) -> str:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"Translate conversational {source_lang} speech into natural {target_lang} dubbing dialogue. Match length and cadence. Output only translated text."
                },
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
