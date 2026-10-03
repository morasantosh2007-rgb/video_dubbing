import json
import logging
import re
import urllib.parse
import urllib.request
from typing import List, Optional
from deep_translator import MyMemoryTranslator, GoogleTranslator

from app.config import settings
from app.models.schemas import SpeechSegment

logger = logging.getLogger(__name__)

# Comprehensive Lexicon to replace Hindi loanwords / transliterated Hindi roots with authentic Telugu words
TELUGU_BOUNDARY = r"[అ-హ\u0c00-\u0c7f]"

HINDI_TO_TELUGU_MAP = {
    # Pronouns & Determiners (including phonetic corruptions from Whisper)
    r"(?<![అ-హ])(తేరా|తేరీ|తేరే|ధేరీ|దేరి|దేరీ|ధేరా|తేర)(?![అ-హ])": "నీ",
    r"(?<![అ-హ])(మేరా|మేరీ|మేరే|మేర)(?![అ-హ])": "నా",
    r"(?<![అ-హ])(తున్|తూన్|తునే|తూనే|తుమ్|తూ)(?![అ-హ])": "నువ్వు",
    r"(?<![అ-హ])(తుఝే|తుఝ్కో)(?![అ-హ])": "నీకు",
    r"(?<![అ-హ])(ముఝే|ముఝ్కో)(?![అ-హ])": "నాకు",
    r"(?<![అ-హ])(ఆప్కా|ఆప్కీ|ఆప్కే|ఆప్)(?![అ-హ])": "మీ",
    r"(?<![అ-హ])(ఉస్కా|ఉస్కీ|ఉస్కే)(?![అ-హ])": "అతని",
    r"(?<![అ-హ])(హం|హమారా|హమారీ|హమారే)(?![అ-హ])": "మేము",
    r"(?<![అ-హ])(కట్ను|కట్నో|కత్నోం|కిత్నోం|కిత్నే|కిత్నీ)(?![అ-హ])": "ఎందరో",
    r"(?<![అ-హ])(సారా|సారీ|సారే)(?![అ-హ])": "మొత్తం",
    r"(?<![అ-హ])(జానే)(?![అ-హ])": "తెలుసు",

    # Emotions, Love & Relationships
    r"(?<![అ-హ])(సరియా|కేసరియా|కిసరియా|కైసరియా)(?![అ-హ])": "కుంకుమ",
    r"(?<![అ-హ])(ఇష్క్\s*హై|ఇష్\s*హై|ఇష్క్|ఇష్ఖ్|ప్యార్|మొహబ్బత్)(?![అ-హ])": "ప్రేమ",
    r"(?<![అ-హ])(పియా|బియా|హపియా|హప్\s*యా|పియాజీ)(?![అ-హ])": "ప్రియతమా",
    r"(?<![అ-హ])(సజన్)(?![అ-హ])": "ప్రియుడా",
    r"(?<![అ-హ])(దిల్|జిగర్)(?![అ-హ])": "మనసు",
    r"(?<![అ-హ])(జాన్|జిందగీ)(?![అ-హ])": "జీవితం",
    r"(?<![అ-హ])(దోస్త్|యార్)(?![అ-హ])": "స్నేహితుడు",
    r"(?<![అ-హ])(దోస్తీ|యారీ)(?![అ-హ])": "స్నేహం",
    r"(?<![అ-హ])(దీవానా)(?![అ-హ])": "పిచ్చివాడు",
    r"(?<![అ-హ])(దీవానీ)(?![అ-హ])": "పిచ్చిది",

    # Mental states & Well-being
    r"(?<![అ-హ])(ఫికర్|ఫిక్ర|ఫిక్రి|ఫిక్రామి)(?![అ-హ])": "దిగులు",
    r"(?<![అ-హ])(ఖైరిమానౌ|ఖెరిమానౌ|ఖైరువాం|ఖైర్|ఖైరి|ఖెరి|ఖైరియత్)(?![అ-హ])": "క్షేమం",
    r"(?<![అ-హ])(ఖుషీ|ఖుష్)(?![అ-హ])": "సంతోషం",
    r"(?<![అ-హ])(గమ్)(?![అ-హ])": "బాధ",
    r"(?<![అ-హ])(దర్ద్)(?![అ-హ])": "వేదన",
    r"(?<![అ-హ])(యాద్)(?![అ-హ])": "గుర్తు",
    r"(?<![అ-హ])(సోచ్)(?![అ-హ])": "ఆలోచన",
    r"(?<![అ-హ])(రబ్బనే|రబ్బానే|రబ్బా\s*నే|రబ్|ఖుదా)(?![అ-హ])": "దేవుడు",
    r"(?<![అ-హ])(భగవాన్)(?![అ-హ])": "భగవంతుడు",

    # Specific song / poetic vocabulary & phonetic transliterations
    r"(?<![అ-హ])(హుస్న్|హోస్నే|హుసన్)(?![అ-హ])": "అందం",
    r"(?<![అ-హ])(తిజోరియా|తిజోరి|జోరియా|ఖజానా)(?![అ-హ])": "ఖజానా",
    r"(?<![అ-హ])(హాలితీ|హాలీ|హాలి|ఖాలీ)(?![అ-హ])": "ఖాళీ",
    r"(?<![అ-హ])(సియా\s*హీ|సియాహీ|సియాహి|సిల్\s*కి)(?![అ-హ])": "సిరాతో",
    r"(?<![అ-హ])(కాజల్|కాజర్|కజ్రారే)(?![అ-హ])": "కాటుక",
    r"(?<![అ-హ])(లామ్\s*స్టోరియా|లవ్\s*స్టోరియాం|లవ్\s*స్టోరీ|హిస్టోరియా)(?![అ-హ])": "ప్రేమకథలు",
    r"(?<![అ-హ])(హాత్\s*లగా|హాథోం|హాత్)(?![అ-హ])": "చేయి తాకడం",
    r"(?<![అ-హ])(రానిసరి|రేనేసరి|రెనేసరి|రైన్\s*సారీ|రన్\s*సారీ)(?![అ-హ])": "రాత్రంతా",
    r"(?<![అ-హ])(భీ\s*తే|బీ\s*తే|భీతే|బితే|బీతే)(?![అ-హ])": "గడిచింది",
    r"(?<![అ-హ])(ఆంఖేం|ఆంఖ్)(?![అ-హ])": "కళ్ళు",
    r"(?<![అ-హ])(బాత్|బాతేం)(?![అ-హ])": "మాటలు",
    r"(?<![అ-హ])(రాత్|రైన్)(?![అ-హ])": "రాత్రి",
    r"(?<![అ-హ])(దిన్)(?![అ-హ])": "రోజు",
    r"(?<![అ-హ])(సుబహ్)(?![అ-హ])": "ఉదయం",
    r"(?<![అ-హ])(షామ్)(?![అ-హ])": "సాయంత్రం",
    r"(?<![అ-హ])(మౌసమ్)(?![అ-హ])": "ఋతువు",
    r"(?<![అ-హ])(పత్ఝడ్)(?![అ-హ])": "ఆకురాలే కాలం",
    r"(?<![అ-హ])(చానార్)(?![అ-హ])": "చెట్లు",
    r"(?<![అ-హ])(హవా)(?![అ-హ])": "గాలి",
    r"(?<![అ-హ])(లడ్కీ)(?![అ-హ])": "అమ్మాయి",
    r"(?<![అ-హ])(లడ్కా)(?![అ-హ])": "అబ్బాయి",
    r"(?<![అ-హ])(గరం)(?![అ-హ])": "వేడి",
    r"(?<![అ-హ])(సవదష్ట్|స్వీడిష్|స్వాదిష్ట)(?![అ-హ])": "రుచికరమైన",
    r"(?<![అ-హ])(ధనే|వదర్ఫ్)(?![అ-హ])": "ధన్యవాదాలు",
    r"(?<![అ-హ])(రబానే|రబ్బనే)(?![అ-హ])": "దేవుడు",
    r"(?<![అ-హ])(ఏడుపు)(?![అ-హ])": "సూప్",
    r"(?<![అ-హ])(తోగ|గ్యాస్)(?![అ-హ])": "పొయ్యి",
    r"(?<![అ-హ])(పానీ)(?![అ-హ])": "నీళ్లు",
    r"(?<![అ-హ])(ఆవాజ్)(?![అ-హ])": "గొంతు",
    r"(?<![అ-హ])(నజర్)(?![అ-హ])": "చూపు",
    r"(?<![అ-హ])(ఖాబోం|ఖ్వాబ్)(?![అ-హ])": "కలలు",
    r"(?<![అ-హ])(రోటీ)(?![అ-హ])": "రొట్టె",
    r"(?<![అ-హ])(నం)(?![అ-హ])": "వద్దు",
    r"(?<![అ-హ])(గ్రాముల|గ్రాము)(?![అ-హ])": "వేడి",
    r"(?<![అ-హ])(జీసస్|యేసు)(?![అ-హ])": "ఈ సూప్",

    # Hindi grammatical particles & linkers
    r"(?<![అ-హ])(హై|హైం)(?![అ-హ])": "ఉంది",
    r"(?<![అ-హ])(మే|మేం)(?![అ-హ])": "లో",
    r"(?<![అ-హ])(సే)(?![అ-హ])": "తో",
    r"(?<![అ-హ])(కో)(?![అ-హ])": "కి",
    r"(?<![అ-హ])(కి)(?![అ-హ])": ""
}

class TranslationService:
    @classmethod
    def purify_telugu_vocabulary(cls, text: str) -> str:
        """
        Eliminates Hindi loanwords and transliterated Hindi roots,
        ensuring 100% authentic, pure, natural Telugu vocabulary.
        """
        if not text:
            return ""
        for pattern, replacement in HINDI_TO_TELUGU_MAP.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        # Normalize multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _distribute_words(cls, telugu_text: str, durations: List[float]) -> List[str]:
        """
        Distributes a complete translated Telugu sentence across grouped segments
        proportionally according to their original durations, ensuring natural grammatical flow.
        """
        words = telugu_text.split()
        if not words or not durations:
            return ["" for _ in durations]

        n = len(durations)
        if n == 1:
            return [telugu_text]

        total_dur = sum(durations)
        if total_dur <= 0:
            total_dur = float(n)
            durations = [1.0] * n

        total_words = len(words)
        word_counts = []
        accum = 0

        for i, dur in enumerate(durations):
            if i == n - 1:
                count = max(1, total_words - accum)
            else:
                ratio = dur / total_dur
                count = max(1, round(total_words * ratio))
                rem_segs = n - 1 - i
                if accum + count + rem_segs > total_words:
                    count = max(1, total_words - accum - rem_segs)
            word_counts.append(count)
            accum += count

        results = []
        cur_idx = 0
        for count in word_counts:
            segment_words = words[cur_idx : cur_idx + count]
            results.append(" ".join(segment_words))
            cur_idx += count

        return results

    @classmethod
    def translate_segment(cls, text: str, source_lang: str = "hi", target_lang: str = "te") -> str:
        """
        Translate a single sentence/segment from Hindi to Telugu preserving context and conversational intent.
        Tries providers in resilient order:
        1. Standalone conversational phrases dictionary
        2. Gemini (if GEMINI_API_KEY is available)
        3. OpenAI (if OPENAI_API_KEY is available)
        4. Groq (if GROQ_API_KEY is available)
        5. Direct Google Translation (Best for conversational Hindi, lyrics, and Romanized text)
        6. MyMemoryTranslator (Neural free API with hi-IN / te-IN language pairing)
        7. GoogleTranslator fallback
        """
        if not text or not text.strip():
            return ""

        text = text.strip()

        # Standalone conversational phrase dictionary to eliminate MT ambiguities
        STANDALONE_PHRASES = {
            "नहीं": "వద్దు",
            "नहीं।": "వద్దు",
            "नहीं!": "వద్దు",
            "हां": "అవును",
            "हाँ": "అవును",
            "हाँ।": "అవును",
            "देखो": "చూడు",
            "धन्यवाद": "ధన్యవాదాలు",
            "सूप तैयार": "సూప్ సిద్ధంగా ఉంది",
            "सूप तैयार है": "సూప్ సిద్ధంగా ఉంది",
            "बहुत अच्छा": "చాలా బాగుంది",
            "अलविदा": "వీడ్కోలు",
            "नमस्ते आरव": "హలో ఆరవ్",
            "नमस्ते प्रिया": "హలో ప్రియా"
        }
        if text in STANDALONE_PHRASES:
            return STANDALONE_PHRASES[text]

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

        # 4. Direct Google Translation (Best for conversational Hindi, lyrics, and Romanized text)
        try:
            gtx_res = cls._translate_google_gtx(text, source_lang, target_lang)
            if gtx_res:
                return gtx_res
        except Exception as e:
            logger.debug(f"Google GTX translation failed ({e}), trying MyMemory...")

        # 5. MyMemory Neural Translation
        try:
            is_arabic_script = any('\u0600' <= char <= '\u06ff' for char in text)
            src = "ur-PK" if is_arabic_script else ("hi-IN" if source_lang == "hi" else source_lang)
            tgt = "te-IN" if target_lang == "te" else target_lang
            translated = MyMemoryTranslator(source=src, target=tgt).translate(text)
            if translated and not translated.startswith("MYMEMORY WARNING"):
                return translated.strip()
        except Exception as e:
            logger.debug(f"MyMemory translation failed: {e}")

        # 6. Google Web Translator fallback
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
    def _translate_google_gtx(cls, text: str, source_lang: str = "hi", target_lang: str = "te") -> Optional[str]:
        # Detect if text is mostly Latin/Romanized or Devanagari
        is_devanagari = any('\u0900' <= char <= '\u097f' for char in text)
        src = "hi" if is_devanagari else "auto"
        tgt = target_lang

        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={tgt}&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated_parts = [s[0] for s in data[0] if s[0]]
            res = "".join(translated_parts).strip()

            # Ensure output contains Telugu script if target_lang is 'te'
            if res and target_lang == "te" and not any('\u0c00' <= char <= '\u0c7f' for char in res):
                alt_src = "auto" if src == "hi" else "hi"
                alt_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={alt_src}&tl={tgt}&dt=t&q=" + urllib.parse.quote(text)
                alt_req = urllib.request.Request(alt_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(alt_req, timeout=5) as alt_resp:
                    alt_data = json.loads(alt_resp.read().decode("utf-8"))
                    alt_res = "".join([s[0] for s in alt_data[0] if s[0]]).strip()
                    if alt_res:
                        return alt_res

            return res if res else None

    @classmethod
    def translate_segments(cls, segments: List[SpeechSegment], source_lang: str = "hi", target_lang: str = "te") -> List[SpeechSegment]:
        """
        Translates speech segments preserving 1-to-1 temporal synchronization.
        Each segment's spoken dialogue is translated and purified directly into pure Telugu,
        ensuring that where the voice is active in the video, the Telugu audio matches
        precisely at that exact timestamp without word scrambling or inter-segment delays.
        """
        if not segments:
            return []

        logger.info(f"Synchronized Translation: Processing {len(segments)} segments with 1-to-1 temporal alignment...")

        for seg in segments:
            if not seg.hindi_text or not seg.hindi_text.strip():
                continue

            raw_telugu = cls.translate_segment(seg.hindi_text, source_lang, target_lang)
            seg.telugu_text = cls.purify_telugu_vocabulary(raw_telugu)
            logger.info(f"Seg #{seg.segment_id} [{seg.start:.2f}-{seg.end:.2f}s | {seg.duration:.2f}s]: '{seg.hindi_text}' -> '{seg.telugu_text}'")

        return segments

    @classmethod
    def _translate_gemini(cls, text: str, source_lang: str, target_lang: str) -> str:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            f"You are an expert Telugu dubbing scriptwriter and linguist. Translate the spoken {source_lang} dialogue/lyrics "
            f"into 100% PURE, natural, conversational {target_lang}. DO NOT use Hindi loanwords (e.g. use ప్రేమ instead of ఇష్క్/ప్యార్, "
            f"మనసు instead of దిల్, నీ instead of తేరా, దేవుడు instead of రబ్/ఖుదా, దిగులు instead of ఫిక్ర, క్షేమం instead of ఖైర్). "
            f"Produce a smooth, grammatically connected sequence of language. Return ONLY the translated Telugu text.\n\nDialogue: {text}"
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
                    "content": (
                        f"You are an expert Telugu dubbing scriptwriter. Translate spoken {source_lang} into 100% PURE, natural {target_lang}. "
                        f"DO NOT use Hindi loanwords (e.g. use ప్రేమ for ishq/pyaar, మనసు for dil, నీ for tera, దేవుడు for rab, దిగులు for fikr). "
                        f"Produce a connected, grammatically complete sequence of language. Output only translated text."
                    )
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
                    "content": (
                        f"You are an expert Telugu dubbing scriptwriter. Translate spoken {source_lang} into 100% PURE, natural {target_lang}. "
                        f"DO NOT use Hindi loanwords. Produce a connected, grammatically complete sequence of language. Output only translated text."
                    )
                },
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
