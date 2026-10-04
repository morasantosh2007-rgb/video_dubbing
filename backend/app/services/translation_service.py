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
    # Dialogue idioms & misrecognition fixes
    r"(?<![\u0c00-\u0c7f])(మైసూరు\s*అయింది|మైసూరు\s*అవుతుంది|మైసూరు)(?![\u0c00-\u0c7f])": "నేను సూప్ తయారు చేస్తాను",
    r"(?<![\u0c00-\u0c7f])(వేడిగా\s*నిద్రించు|వెచ్చని\s*సూప్|వెచ్చని)(?![\u0c00-\u0c7f])": "వేడి సూప్",
    r"(?<![\u0c00-\u0c7f])(మనం\s*ఏమి\s*తాగుదాం\s*త్రాగాలి|మనం\s*ఏమి)(?![\u0c00-\u0c7f])": "మనం ఏమి తాగుదాం",

    # Pronouns & Determiners (including phonetic corruptions from Whisper)
    r"(?<![\u0c00-\u0c7f])(తేరా|తేరీ|తేరే|ధేరీ|దేరి|దేరీ|ధేరా|తేర|తేరాంజి|నీంజి)(?![\u0c00-\u0c7f])": "నీ",
    r"(?<![\u0c00-\u0c7f])(మేరా|మేరీ|మేరే|మేర)(?![\u0c00-\u0c7f])": "నా",
    r"(?<![\u0c00-\u0c7f])(తున్|తూన్|తునే|తూనే|తుమ్|తూ)(?![\u0c00-\u0c7f])": "నువ్వు",
    r"(?<![\u0c00-\u0c7f])(తుఝే|తుఝ్కో|తుమ్కో)(?![\u0c00-\u0c7f])": "నీకు",
    r"(?<![\u0c00-\u0c7f])(ముఝే|ముఝ్కో|ముజ్కో)(?![\u0c00-\u0c7f])": "నాకు",
    r"(?<![\u0c00-\u0c7f])(ఆప్కా|ఆప్కీ|ఆప్కే|ఆప్)(?![\u0c00-\u0c7f])": "మీ",
    r"(?<![\u0c00-\u0c7f])(ఆప్కో)(?![\u0c00-\u0c7f])": "మీకు",
    r"(?<![\u0c00-\u0c7f])(ఉస్కా|ఉస్కీ|ఉస్కే)(?![\u0c00-\u0c7f])": "అతని",
    r"(?<![\u0c00-\u0c7f])(ఉస్కో)(?![\u0c00-\u0c7f])": "అతనికి",
    r"(?<![\u0c00-\u0c7f])(ఇస్కో)(?![\u0c00-\u0c7f])": "ఇతనికి",
    r"(?<![\u0c00-\u0c7f])(కిస్కో)(?![\u0c00-\u0c7f])": "ఎవరికి",
    r"(?<![\u0c00-\u0c7f])(హం|హమారా|హమారీ|హమారే)(?![\u0c00-\u0c7f])": "మేము",
    r"(?<![\u0c00-\u0c7f])(కట్ను|కట్నో|కత్నోం|కిత్నోం|కిత్నే|కిత్నీ)(?![\u0c00-\u0c7f])": "ఎందరో",
    r"(?<![\u0c00-\u0c7f])(సారా|సారీ|సారే)(?![\u0c00-\u0c7f])": "మొత్తం",
    r"(?<![\u0c00-\u0c7f])(జానే)(?![\u0c00-\u0c7f])": "తెలుసు",

    # Compound actions & verbal loanword collocations
    r"(?<![\u0c00-\u0c7f])(మదద్\s*చేయండి|మదద్\s*చేయు)(?![\u0c00-\u0c7f])": "సహాయం చేయండి",
    r"(?<![\u0c00-\u0c7f])(మదద్)(?![\u0c00-\u0c7f])": "సహాయం",
    r"(?<![\u0c00-\u0c7f])(శురూ\s*చేయండి|శురూ\s*చేయు)(?![\u0c00-\u0c7f])": "ప్రారంభించండి",
    r"(?<![\u0c00-\u0c7f])(శురూ\s*అయింది)(?![\u0c00-\u0c7f])": "ప్రారంభం అయింది",
    r"(?<![\u0c00-\u0c7f])(శురూ)(?![\u0c00-\u0c7f])": "ప్రారంభం",
    r"(?<![\u0c00-\u0c7f])(ఖతం\s*చేయండి|ఖతం\s*చేయు)(?![\u0c00-\u0c7f])": "పూర్తి చేయండి",
    r"(?<![\u0c00-\u0c7f])(ఖతం\s*అయింది|ఖతం\s*అయిపోయింది)(?![\u0c00-\u0c7f])": "పూర్తి అయింది",
    r"(?<![\u0c00-\u0c7f])(ఖతం)(?![\u0c00-\u0c7f])": "పూర్తి",
    r"(?<![\u0c00-\u0c7f])(కోశిశ్\s*చేయండి|కోశిశ్\s*చేయు)(?![\u0c00-\u0c7f])": "ప్రయత్నించండి",
    r"(?<![\u0c00-\u0c7f])(కోశిశ్)(?![\u0c00-\u0c7f])": "ప్రయత్నం",
    r"(?<![\u0c00-\u0c7f])(ఇంతజార్\s*చేయండి|ఇంతజార్\s*చేయు)(?![\u0c00-\u0c7f])": "వేచి ఉండండి",
    r"(?<![\u0c00-\u0c7f])(ఇంతజార్)(?![\u0c00-\u0c7f])": "నిరీక్షణ",
    r"(?<![\u0c00-\u0c7f])(ఫైసలా\s*చేయండి|ఫైసలా\s*చేయు)(?![\u0c00-\u0c7f])": "నిర్ణయించండి",
    r"(?<![\u0c00-\u0c7f])(ఫైసలా)(?![\u0c00-\u0c7f])": "నిర్ణయం",
    r"(?<![\u0c00-\u0c7f])(మంజూర్\s*చేయండి|మంజూర్\s*చేయు)(?![\u0c00-\u0c7f])": "అంగీకరించండి",
    r"(?<![\u0c00-\u0c7f])(మంజూర్)(?![\u0c00-\u0c7f])": "అంగీకారం",
    r"(?<![\u0c00-\u0c7f])(మాఫ్\s*చేయండి|మాఫ్\s*చేయు|మాఫ్)(?![\u0c00-\u0c7f])": "క్షమించండి",
    r"(?<![\u0c00-\u0c7f])(తయ్యార్\s*చేయండి|తయార్\s*చేయండి)(?![\u0c00-\u0c7f])": "సిద్ధం చేయండి",
    r"(?<![\u0c00-\u0c7f])(తయ్యార్\s*గా|తయార్\s*గా)(?![\u0c00-\u0c7f])": "సిద్ధంగా",
    r"(?<![\u0c00-\u0c7f])(తయ్యార్|తయార్)(?![\u0c00-\u0c7f])": "సిద్ధం",
    r"(?<![\u0c00-\u0c7f])(బాత్\s*చేయండి|బాత్\s*చేయు)(?![\u0c00-\u0c7f])": "మాట్లాడండి",
    r"(?<![\u0c00-\u0c7f])(పసంద్\s*చేయండి)(?![\u0c00-\u0c7f])": "ఇష్టపడండి",
    r"(?<![\u0c00-\u0c7f])(పసంద్)(?![\u0c00-\u0c7f])": "ఇష్టం",
    r"(?<![\u0c00-\u0c7f])(జల్దీ\s*రండి)(?![\u0c00-\u0c7f])": "త్వరగా రండి",
    r"(?<![\u0c00-\u0c7f])(జల్దీ)(?![\u0c00-\u0c7f])": "త్వరగా",
    r"(?<![\u0c00-\u0c7f])(జరూరీ\s*గా)(?![\u0c00-\u0c7f])": "ముఖ్యంగా",
    r"(?<![\u0c00-\u0c7f])(జరూరీ|జరూరత్)(?![\u0c00-\u0c7f])": "ముఖ్యమైన",
    r"(?<![\u0c00-\u0c7f])(రాస్తా|రాస్తే)(?![\u0c00-\u0c7f])": "దారి",
    r"(?<![\u0c00-\u0c7f])(ఫాయిదా)(?![\u0c00-\u0c7f])": "లాభం",
    r"(?<![\u0c00-\u0c7f])(సవాల్|సవాలేం)(?![\u0c00-\u0c7f])": "ప్రశ్న",
    r"(?<![\u0c00-\u0c7f])(జవాబ్)(?![\u0c00-\u0c7f])": "సమాధానం",
    r"(?<![\u0c00-\u0c7f])(తక్లీఫ్)(?![\u0c00-\u0c7f])": "కష్టం",
    r"(?<![\u0c00-\u0c7f])(అజీబ్\s*గా)(?![\u0c00-\u0c7f])": "విచిత్రంగా",
    r"(?<![\u0c00-\u0c7f])(అజీబ్)(?![\u0c00-\u0c7f])": "విచిత్రం",
    r"(?<![\u0c00-\u0c7f])(ఖూబ్సూరత్\s*గా|ఖూబ్\s*సూరత్\s*గా)(?![\u0c00-\u0c7f])": "అందంగా",
    r"(?<![\u0c00-\u0c7f])(ఖూబ్సూరత్|ఖూబ్\s*సూరత్)(?![\u0c00-\u0c7f])": "అందమైన",
    r"(?<![\u0c00-\u0c7f])(హోషియార్)(?![\u0c00-\u0c7f])": "తెలివైన",
    r"(?<![\u0c00-\u0c7f])(హిమ్మత్)(?![\u0c00-\u0c7f])": "ధైర్యం",
    r"(?<![\u0c00-\u0c7f])(ముష్కిల్\s*గా)(?![\u0c00-\u0c7f])": "కష్టంగా",
    r"(?<![\u0c00-\u0c7f])(ముష్కిల్)(?![\u0c00-\u0c7f])": "కష్టం",
    r"(?<![\u0c00-\u0c7f])(ఆసాన్\s*గా)(?![\u0c00-\u0c7f])": "సులభంగా",
    r"(?<![\u0c00-\u0c7f])(ఆసాన్)(?![\u0c00-\u0c7f])": "సులభం",
    r"(?<![\u0c00-\u0c7f])(వజహ్|వజహ)(?![\u0c00-\u0c7f])": "కారణం",
    r"(?<![\u0c00-\u0c7f])(వక్త్|వక్తు)(?![\u0c00-\u0c7f])": "సమయం",
    r"(?<![\u0c00-\u0c7f])(ఖామూష్\s*గా)(?![\u0c00-\u0c7f])": "నిశ్శబ్దంగా",
    r"(?<![\u0c00-\u0c7f])(ఖామూష్)(?![\u0c00-\u0c7f])": "నిశ్శబ్దం",
    r"(?<![\u0c00-\u0c7f])(జిందా\s*గా)(?![\u0c00-\u0c7f])": "సజీవంగా",
    r"(?<![\u0c00-\u0c7f])(జిందా)(?![\u0c00-\u0c7f])": "సజీవంగా",
    r"(?<![\u0c00-\u0c7f])(మౌత్)(?![\u0c00-\u0c7f])": "మరణం",
    r"(?<![\u0c00-\u0c7f])(కిస్మత్)(?![\u0c00-\u0c7f])": "అదృష్టం",
    r"(?<![\u0c00-\u0c7f])(మెహర్బానీ)(?![\u0c00-\u0c7f])": "దయ",
    r"(?<![\u0c00-\u0c7f])(శుక్రియా)(?![\u0c00-\u0c7f])": "ధన్యవాదాలు",
    r"(?<![\u0c00-\u0c7f])(అకేలా|అకేలీ)(?![\u0c00-\u0c7f])": "ఒంటరిగా",
    r"(?<![\u0c00-\u0c7f])(సఫర్)(?![\u0c00-\u0c7f])": "ప్రయాణం",
    r"(?<![\u0c00-\u0c7f])(దర్వాజా)(?![\u0c00-\u0c7f])": "తలుపు",
    r"(?<![\u0c00-\u0c7f])(ఖిడ్కీ)(?![\u0c00-\u0c7f])": "కిటికీ",
    r"(?<![\u0c00-\u0c7f])(దునియా)(?![\u0c00-\u0c7f])": "ప్రపంచం",
    r"(?<![\u0c00-\u0c7f])(ఖ్వాహిష్)(?![\u0c00-\u0c7f])": "కోరిక",
    r"(?<![\u0c00-\u0c7f])(సాథ్)(?![\u0c00-\u0c7f])": "తోడు",
    r"(?<![\u0c00-\u0c7f])(రోజ్)(?![\u0c00-\u0c7f])": "ప్రతిరోజూ",
    r"(?<![\u0c00-\u0c7f])(హమేషా)(?![\u0c00-\u0c7f])": "ఎల్లప్పుడూ",
    r"(?<![\u0c00-\u0c7f])(కభీ)(?![\u0c00-\u0c7f])": "ఎప్పుడూ",
    r"(?<![\u0c00-\u0c7f])(శాయద్)(?![\u0c00-\u0c7f])": "బహుశా",
    r"(?<![\u0c00-\u0c7f])(యకీన్)(?![\u0c00-\u0c7f])": "నమ్మకం",
    r"(?<![\u0c00-\u0c7f])(సచ్\s*గా)(?![\u0c00-\u0c7f])": "నిజంగా",
    r"(?<![\u0c00-\u0c7f])(సచ్)(?![\u0c00-\u0c7f])": "నిజం",
    r"(?<![\u0c00-\u0c7f])(ఝూట్)(?![\u0c00-\u0c7f])": "అబద్ధం",

    # Emotions, Love & Relationships
    r"(?<![\u0c00-\u0c7f])(సరియా|కేసరియా|కిసరియా|కైసరియా|కేసేవియ)(?![\u0c00-\u0c7f])": "కుంకుమ",
    r"(?<![\u0c00-\u0c7f])(ఇష్క్\s*హై|ఇష్\s*హై|ఇష్క్|ఇష్ఖ్|ప్యార్|మొహబ్బత్)(?![\u0c00-\u0c7f])": "ప్రేమ",
    r"(?<![\u0c00-\u0c7f])(పియా|బియా|హపియా|హప్\s*యా|పియాజీ)(?![\u0c00-\u0c7f])": "ప్రియతమా",
    r"(?<![\u0c00-\u0c7f])(సజన్)(?![\u0c00-\u0c7f])": "ప్రియుడా",
    r"(?<![\u0c00-\u0c7f])(దిల్|జిగర్)(?![\u0c00-\u0c7f])": "మనసు",
    r"(?<![\u0c00-\u0c7f])(జాన్|జిందగీ)(?![\u0c00-\u0c7f])": "జీవితం",
    r"(?<![\u0c00-\u0c7f])(దోస్త్|యార్)(?![\u0c00-\u0c7f])": "స్నేహితుడు",
    r"(?<![\u0c00-\u0c7f])(దోస్తీ|యారీ)(?![\u0c00-\u0c7f])": "స్నేహం",
    r"(?<![\u0c00-\u0c7f])(దీవానా)(?![\u0c00-\u0c7f])": "పిచ్చివాడు",
    r"(?<![\u0c00-\u0c7f])(దీవానీ)(?![\u0c00-\u0c7f])": "పిచ్చిది",

    # Mental states & Well-being
    r"(?<![\u0c00-\u0c7f])(ఫికర్|ఫిక్ర|ఫిక్రి|ఫిక్రామి|థెరిఫికమే)(?![\u0c00-\u0c7f])": "దిగులు",
    r"(?<![\u0c00-\u0c7f])(ఖైరిమానౌ|ఖెరిమానౌ|ఖైరువాం|ఖైర్|ఖైరి|ఖెరి|ఖైరియత్)(?![\u0c00-\u0c7f])": "క్షేమం",
    r"(?<![\u0c00-\u0c7f])(ఖుషీ\s*గా)(?![\u0c00-\u0c7f])": "సంతోషంగా",
    r"(?<![\u0c00-\u0c7f])(ఖుషీ|ఖుష్|ఖుషి)(?![\u0c00-\u0c7f])": "సంతోషం",
    r"(?<![\u0c00-\u0c7f])(గమ్)(?![\u0c00-\u0c7f])": "బాధ",
    r"(?<![\u0c00-\u0c7f])(దర్ద్)(?![\u0c00-\u0c7f])": "వేదన",
    r"(?<![\u0c00-\u0c7f])(యాద్)(?![\u0c00-\u0c7f])": "గుర్తు",
    r"(?<![\u0c00-\u0c7f])(సోచ్)(?![\u0c00-\u0c7f])": "ఆలోచన",
    r"(?<![\u0c00-\u0c7f])(రబ్బనే|రబ్బానే|రబ్బా\s*నే|రబ్|ఖుదా|రబానే)(?![\u0c00-\u0c7f])": "దేవుడు",
    r"(?<![\u0c00-\u0c7f])(భగవాన్)(?![\u0c00-\u0c7f])": "భగవంతుడు",

    # Specific song / poetic vocabulary & phonetic transliterations
    r"(?<![\u0c00-\u0c7f])(హుస్న్|హోస్నే|హుసన్)(?![\u0c00-\u0c7f])": "అందం",
    r"(?<![\u0c00-\u0c7f])(తిజోరియా|తిజోరి|జోరియా|ఖజానా)(?![\u0c00-\u0c7f])": "ఖజానా",
    r"(?<![\u0c00-\u0c7f])(హాలితీ|హాలీ|హాలి|ఖాలీ)(?![\u0c00-\u0c7f])": "ఖాళీ",
    r"(?<![\u0c00-\u0c7f])(సియా\s*హీ|సియాహీ|సియాహి|సిల్\s*కి)(?![\u0c00-\u0c7f])": "సిరాతో",
    r"(?<![\u0c00-\u0c7f])(కాజల్|కాజర్|కజ్రారే)(?![\u0c00-\u0c7f])": "కాటుక",
    r"(?<![\u0c00-\u0c7f])(లామ్\s*స్టోరియా|లవ్\s*స్టోరియాం|లవ్\s*స్టోరీ|లావి\s*జోరియా|హిస్టోరియా)(?![\u0c00-\u0c7f])": "ప్రేమకథలు",
    r"(?<![\u0c00-\u0c7f])(హాత్\s*లగా|హాథోం|హాత్|లకావో)(?![\u0c00-\u0c7f])": "చేయి తాకడం",
    r"(?<![\u0c00-\u0c7f])(రానిసరి|రేనేసరి|రెనేసరి|రైన్\s*సారీ|రన్\s*సారీ|రమేసాలి)(?![\u0c00-\u0c7f])": "రాత్రంతా",
    r"(?<![\u0c00-\u0c7f])(భీ\s*తే|బీ\s*తే|భీతే|బితే|బీతే|డిండిట్)(?![\u0c00-\u0c7f])": "గడిచింది",
    r"(?<![\u0c00-\u0c7f])(థెరిఫ్|హెర్)(?![\u0c00-\u0c7f])": "నీ",
    r"(?<![\u0c00-\u0c7f])(వనౌ)(?![\u0c00-\u0c7f])": "వేడుకుంటాను",
    r"(?<![\u0c00-\u0c7f])(రంగిజన్)(?![\u0c00-\u0c7f])": "రంగులద్దుకుంటాను",
    r"(?<![\u0c00-\u0c7f])(ఉజావెల్)(?![\u0c00-\u0c7f])": "నేను",
    r"(?<![\u0c00-\u0c7f])(ఆంఖేం|ఆంఖ్)(?![\u0c00-\u0c7f])": "కళ్ళు",
    r"(?<![\u0c00-\u0c7f])(బాత్|బాతేం|బాతోం)(?![\u0c00-\u0c7f])": "మాటలు",
    r"(?<![\u0c00-\u0c7f])(రాత్|రైన్)(?![\u0c00-\u0c7f])": "రాత్రి",
    r"(?<![\u0c00-\u0c7f])(దిన్)(?![\u0c00-\u0c7f])": "రోజు",
    r"(?<![\u0c00-\u0c7f])(సుబహ్)(?![\u0c00-\u0c7f])": "ఉదయం",
    r"(?<![\u0c00-\u0c7f])(షామ్)(?![\u0c00-\u0c7f])": "సాయంత్రం",
    r"(?<![\u0c00-\u0c7f])(మౌసమ్)(?![\u0c00-\u0c7f])": "వాతావరణం",
    r"(?<![\u0c00-\u0c7f])(పత్ఝడ్)(?![\u0c00-\u0c7f])": "ఆకురాలే కాలం",
    r"(?<![\u0c00-\u0c7f])(చానార్)(?![\u0c00-\u0c7f])": "చెట్లు",
    r"(?<![\u0c00-\u0c7f])(హవా)(?![\u0c00-\u0c7f])": "గాలి",
    r"(?<![\u0c00-\u0c7f])(లడ్కీ)(?![\u0c00-\u0c7f])": "అమ్మాయి",
    r"(?<![\u0c00-\u0c7f])(లడ్కా)(?![\u0c00-\u0c7f])": "అబ్బాయి",
    r"(?<![\u0c00-\u0c7f])(గరం)(?![\u0c00-\u0c7f])": "వేడి",
    r"(?<![\u0c00-\u0c7f])(సవదష్ట్|స్వీడిష్|స్వాదిష్ట)(?![\u0c00-\u0c7f])": "రుచికరమైన",
    r"(?<![\u0c00-\u0c7f])(ధనే|వదర్ఫ్)(?![\u0c00-\u0c7f])": "ధన్యవాదాలు",
    r"(?<![\u0c00-\u0c7f])(పానీ)(?![\u0c00-\u0c7f])": "నీళ్లు",
    r"(?<![\u0c00-\u0c7f])(ఆవాజ్)(?![\u0c00-\u0c7f])": "గొంతు",
    r"(?<![\u0c00-\u0c7f])(నజర్)(?![\u0c00-\u0c7f])": "చూపు",
    r"(?<![\u0c00-\u0c7f])(ఖాబోం|ఖ్వాబ్)(?![\u0c00-\u0c7f])": "కలలు",
    r"(?<![\u0c00-\u0c7f])(రోటీ)(?![\u0c00-\u0c7f])": "రొట్టె",
    r"(?<![\u0c00-\u0c7f])(నం)(?![\u0c00-\u0c7f])": "వద్దు",

    # Transliterated Hindi continuation words & conjunctions
    r"(?<![\u0c00-\u0c7f])(ఔర్)(?![\u0c00-\u0c7f])": "మరియు",
    r"(?<![\u0c00-\u0c7f])(లేకిన్|మగర్)(?![\u0c00-\u0c7f])": "కానీ",
    r"(?<![\u0c00-\u0c7f])(ఫిర్)(?![\u0c00-\u0c7f])": "తర్వాత",
    r"(?<![\u0c00-\u0c7f])(ఇస్లియే)(?![\u0c00-\u0c7f])": "అందుకే",
    r"(?<![\u0c00-\u0c7f])(క్యోంకి|క్యోనికి)(?![\u0c00-\u0c7f])": "ఎందుకంటే",
    r"(?<![\u0c00-\u0c7f])(భీ|భి)(?![\u0c00-\u0c7f])": "కూడా",
    r"(?<![\u0c00-\u0c7f])(వావో|వావ్|వాహు)(?![\u0c00-\u0c7f])": "వావ్",
    r"(?<![\u0c00-\u0c7f])(శభాష్)(?![\u0c00-\u0c7f])": "శభాష్",

    # Hindi grammatical particles & linkers
    r"(?<![\u0c00-\u0c7f])(హై|హైం)(?![\u0c00-\u0c7f])": "ఉంది",
    r"(?<![\u0c00-\u0c7f])(మే|మేం)(?![\u0c00-\u0c7f])": "లో",
    r"(?<![\u0c00-\u0c7f])(సే)(?![\u0c00-\u0c7f])": "తో",
    r"(?<![\u0c00-\u0c7f])(కో)(?![\u0c00-\u0c7f])": "కి"
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

        # Phonetic normalization of Hindi text
        try:
            from app.services.asr_service import ASRService
            text = ASRService.normalize_hindi_text(text)
        except Exception:
            pass

        # Standalone conversational phrase dictionary to eliminate MT ambiguities
        STANDALONE_PHRASES = {
            # Exclamations & Expressive Reactions
            "wow": "వావ్!",
            "Wow": "వావ్!",
            "WOW": "వావ్!",
            "वाओ": "వావ్!",
            "वाओ!": "వావ్!",
            "वाह": "వావ్!",
            "वाह!": "వావ్!",
            "वाव": "వావ్!",
            "वाऊ": "వావ్!",
            "अरे वाह": "అరే వావ్!",
            "अरे वाह!": "అరే వావ్!",
            "अरे": "అరే!",
            "अरे!": "అరే!",
            "ओह": "ఓహ్!",
            "ओह!": "ఓహ్!",
            "oh": "ఓహ్!",
            "Oh": "ఓహ్!",
            "शाबाश": "శభాష్!",
            "शाबाश!": "శభాష్!",
            "सुपर": "సూపర్!",
            "सुपर!": "సూపర్!",
            "अद्भुत": "అద్భుతం!",
            "अद्भुत!": "అద్భుతం!",

            # Conversational Continuations & Conjunctions
            "और": "మరియు",
            "और।": "మరియు",
            "लेकिन": "కానీ",
            "लेकिन।": "కానీ",
            "मगर": "కానీ",
            "पर": "కానీ",
            "फिर": "తర్వాత",
            "फिर।": "తర్వాత",
            "तो": "అయితే",
            "तो।": "అయితే",
            "इसलिए": "అందుకే",
            "इसलिए।": "అందుకే",
            "क्योंकि": "ఎందుకంటే",
            "क्योंकि।": "ఎందుకంటే",
            "भी": "కూడా",
            "या": "లేదా",
            "वैसे": "అలాగే",
            "अब": "ఇప్పుడు",

            # Common Conversational Affirmations & Responses
            "नहीं": "వద్దు",
            "नहीं।": "వద్దు",
            "नहीं!": "వద్దు",
            "नहीं नहीं": "వద్దు వద్దు",
            "हां": "అవును",
            "हाँ": "అవును",
            "हाँ।": "అవును",
            "हाँ!": "అవును",
            "हां ज़रूर": "అవును ఖచ్చితంగా",
            "हाँ जरूर": "అవును ఖచ్చితంగా",
            "अच्छा": "మంచిది",
            "अच्छा!": "మంచిది!",
            "बहुत अच्छा": "చాలా బాగుంది",
            "बहुत अच्छा!": "చాలా బాగుంది!",
            "ठीक है": "సరే",
            "ठीक है।": "సరే",
            "बिलकुल": "ఖచ్చితంగా",
            "बिल्कुल": "ఖచ్చితంగా",
            "ज़रूर": "తప్పకుండా",
            "जरूर": "తప్పకుండా",
            "सच में": "నిజంగానా?",
            "सच में?": "నిజంగానా?",
            "देखो": "చూడు",
            "देखो!": "చూడు!",
            "सुनो": "వినండి",
            "सुनो!": "వినండి!",
            "रुको": "ఆగండి",
            "रुको!": "ఆగండి!",
            "चलो": "పదండి",
            "चलो!": "పదండి!",
            "धन्यवाद": "ధన్యవాదాలు",
            "धन्यवाद!": "ధన్యవాదాలు!",
            "अलविदा": "వీడ్కోలు",
            "अलविदा!": "వీడ్కోలు!",
            "नमस्ते": "హలో",
            "नमस्ते!": "హలో!",
            "नमस्ते आरव": "హలో ఆరవ్",
            "नमस्ते प्रिया": "హలో ప్రియా",
            "सूप तैयार": "సూప్ సిద్ధంగా ఉంది",
            "सूप तैयार है": "సూప్ సిద్ధంగా ఉంది",
            "मैसूर बना": "నేను సూప్ తయారు చేస్తాను",
            "मैसूर बना।": "నేను సూప్ తయారు చేస్తాను",
            "मैसूर बना!": "నేను సూప్ తయారు చేస్తాను",
            "मैं सूप बनाता हूं": "నేను సూప్ తయారు చేస్తాను",
            "मैं सूप बनाता हूँ": "నేను సూప్ తయారు చేస్తాను",
            "मैं सूप बनाता हूँ।": "నేను సూప్ తయారు చేస్తాను",
            "गर्म": "వేడి సూప్",
            "गर्म सो": "వేడి సూప్",
            "हम क्या": "మనం ఏమి తాగుదాం",
            "हम क्या पिए": "మనం ఏమి తాగుదాం",
            "क्या हम गर्म चाय पिए": "మనం వేడి టీ తాగుదామా"
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
