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

# Model Settings — gemini-3.5-flash for both text & audio (best quality, supports native audio)
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
AUDIO_MODEL = os.getenv("GEMINI_AUDIO_MODEL", "gemini-3.5-flash")

# Voices Configuration
MALE_VOICE = "Algieba"
FEMALE_VOICE = "Aoede"

# Feature Toggles (turn off to save API requests)
ENABLE_FEMALE_VOICE = False
ENABLE_EXPLAINER = True

# Rate Limiting & Retry Settings (tuned for paid tier with 1000 credits)
API_CALL_DELAY = int(os.getenv("API_CALL_DELAY", "1"))          # Seconds between API calls (low for paid tier)
MAX_RETRIES_TEXT = int(os.getenv("MAX_RETRIES_TEXT", "5"))       # Max retry attempts for text generation
MAX_RETRIES_AUDIO = int(os.getenv("MAX_RETRIES_AUDIO", "5"))    # Max retry attempts for audio generation
RETRY_MAX_WAIT = int(os.getenv("RETRY_MAX_WAIT", "120"))        # Max seconds to wait between retries

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