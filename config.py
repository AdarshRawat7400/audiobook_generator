import os
from pathlib import Path

# Input Configuration
DEFAULT_INPUT_DIR = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re") / "Source"

# Output Directories
OUTPUT_DIR = Path("output")
AUDIO_DIR = OUTPUT_DIR / "audio"

MALE_DIR = AUDIO_DIR / "male"
FEMALE_DIR = AUDIO_DIR / "female"
MALE_EXP_DIR = AUDIO_DIR / "male_explainer"
FEMALE_EXP_DIR = AUDIO_DIR / "female_explainer"

MANIFEST_DIR = OUTPUT_DIR / "manifests"
LOGS_DIR = OUTPUT_DIR / "logs"
EXPLAINER_TEXT_DIR = OUTPUT_DIR / "explainer_texts"

# Ensure directories exist
for d in [MALE_DIR, FEMALE_DIR, MALE_EXP_DIR, FEMALE_EXP_DIR,
          MANIFEST_DIR, LOGS_DIR, EXPLAINER_TEXT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Model Settings — Vertex AI compatible models
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
AUDIO_MODEL = os.getenv("GEMINI_AUDIO_MODEL", "gemini-3.1-flash-tts-preview")

# Voices Configuration
MALE_VOICE = "Charon"
FEMALE_VOICE = "Kore"

# Feature Toggles (turn off to save API requests)
ENABLE_FEMALE_VOICE = True
ENABLE_EXPLAINER = True

# Rate Limiting & Retry Settings (tuned for paid tier with 1000 credits)
API_CALL_DELAY = int(os.getenv("API_CALL_DELAY", "1"))          # Seconds between API calls (low for paid tier)
MAX_RETRIES_TEXT = int(os.getenv("MAX_RETRIES_TEXT", "5"))       # Max retry attempts for text generation
MAX_RETRIES_AUDIO = int(os.getenv("MAX_RETRIES_AUDIO", "5"))    # Max retry attempts for audio generation
RETRY_MAX_WAIT = int(os.getenv("RETRY_MAX_WAIT", "120"))        # Max seconds to wait between retries

# Chunking Settings for TTS (prevents voice deepening/distortion over long texts)
MAX_TTS_CHARS = int(os.getenv("MAX_TTS_CHARS", "1600"))
TTS_CHUNK_SILENCE_SECONDS = float(os.getenv("TTS_CHUNK_SILENCE_SECONDS", "0.5"))

# Execution Settings — paid tier can handle concurrent requests
MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_WORKERS", "2"))

# Explainer Skip Rules
SKIP_EXPLAINER_KEYWORDS = [
    "समर्पण",
    "मंगल कामना",
    "आमुख",
    "दो-शब्द",
    "रचनाकार परिचय"
]

# ---------------------------------------------------------------------------
# Audio Style Instructions (All India Radio / Akashvani style)
# ---------------------------------------------------------------------------

# System instruction for POEM narration audio
# Style: Authentic All India Radio (Akashvani) — classic senior Hindi announcer
NARRATION_SYSTEM_INSTRUCTION = """\
You are a veteran All India Radio Akashvani Hindi poetry narrator. \
Read the text exactly as written with a deep, warm, dignified baritone voice. \
Slow graceful pace with measured pauses. Pure Hindi pronunciation. \
Preserve Bundeli words. Reverent for devotional poems, inspiring for patriotic ones, \
reflective for philosophical poems, nostalgic for village poems. \
No introductions, no conclusions, no explanations. Start reading immediately.\
"""

# System instruction for EXPLAINER narration audio
# Style: AIR educational literary program — warm, wise, classic broadcast
EXPLAINER_SYSTEM_INSTRUCTION = """\
You are an All India Radio Akashvani Hindi literary program presenter explaining poetry. \
Read the text exactly as written with a warm, dignified, cultured voice. \
Moderate comfortable pace with natural pauses between ideas. \
Emphasize important literary terms. Pure Hindi pronunciation. \
No introductions, no conclusions, no explanations. Start reading immediately.\
"""