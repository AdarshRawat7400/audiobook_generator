"""
Gemini Model Diagnostics -- tests configured and alternative models for
both text generation and audio generation capabilities.
"""
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Import current config to show what's active
try:
    import config
    configured_text = config.TEXT_MODEL
    configured_audio = config.AUDIO_MODEL
except Exception:
    configured_text = "unknown"
    configured_audio = "unknown"

# ANSI colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"
BOLD = "\033[1m"

def test_text(model: str) -> bool:
    """Test if a model can generate text."""
    try:
        response = client.models.generate_content(
            model=model,
            contents="Say 'Hello' in one word.",
            config=types.GenerateContentConfig(temperature=0.3)
        )
        text = response.text.strip() if response.text else "(empty)"
        print(f"  {GREEN}[OK]   TEXT{RESET}  -- Response: {text[:50]}")
        return True
    except Exception as e:
        reason = _extract_reason(e)
        print(f"  {RED}[FAIL] TEXT{RESET}  -- {reason}")
        return False

def test_audio(model: str) -> bool:
    """Test if a model can generate audio."""
    try:
        response = client.models.generate_content(
            model=model,
            contents="Testing.",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Algieba")
                    )
                )
            )
        )
        # Validate audio data exists
        if (response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
                and response.candidates[0].content.parts[0].inline_data):
            data = response.candidates[0].content.parts[0].inline_data.data
            print(f"  {GREEN}[OK]   AUDIO{RESET} -- {len(data)} bytes of audio")
            return True
        else:
            print(f"  {RED}[FAIL] AUDIO{RESET} -- Response contained no audio data")
            return False
    except Exception as e:
        reason = _extract_reason(e)
        print(f"  {RED}[FAIL] AUDIO{RESET} -- {reason}")
        return False

def _extract_reason(e: Exception) -> str:
    """Extract a concise error reason from an API exception."""
    msg = str(e)
    if "429" in msg:
        return "RATE LIMITED (429) -- quota exceeded"
    if "400" in msg:
        return "INVALID (400) -- model doesn't support this mode"
    if "404" in msg:
        return "NOT FOUND (404) -- model unavailable"
    return msg[:100]

# ---------------------------------------------------------------------------
# Run diagnostics
# ---------------------------------------------------------------------------
models_to_test = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

print(f"\n{BOLD}{'=' * 60}{RESET}")
print(f"{BOLD}  GEMINI MODEL DIAGNOSTICS{RESET}")
print(f"{BOLD}{'=' * 60}{RESET}")
print(f"\n  {CYAN}Configured TEXT_MODEL:  {configured_text}{RESET}")
print(f"  {CYAN}Configured AUDIO_MODEL: {configured_audio}{RESET}\n")

text_results = {}
audio_results = {}

for model in models_to_test:
    tag = ""
    if model == configured_text and model == configured_audio:
        tag = f" {YELLOW}<-- TEXT + AUDIO model{RESET}"
    elif model == configured_text:
        tag = f" {YELLOW}<-- TEXT model{RESET}"
    elif model == configured_audio:
        tag = f" {YELLOW}<-- AUDIO model{RESET}"

    print(f"\n{BOLD}[{model}]{RESET}{tag}")
    text_results[model] = test_text(model)
    audio_results[model] = test_audio(model)

# Summary
print(f"\n{BOLD}{'=' * 60}{RESET}")
print(f"{BOLD}  SUMMARY{RESET}")
print(f"{'=' * 60}")
print(f"  {'Model':<40} {'Text':>6} {'Audio':>6}")
print(f"  {'-' * 52}")
for model in models_to_test:
    t = f"{GREEN}OK{RESET}" if text_results.get(model) else f"{RED}FAIL{RESET}"
    a = f"{GREEN}OK{RESET}" if audio_results.get(model) else f"{RED}FAIL{RESET}"
    print(f"  {model:<40} {t:>15} {a:>15}")
print(f"{'=' * 60}\n")

# Check if configured models passed
all_ok = True
if not text_results.get(configured_text):
    print(f"  {RED}[!] Your configured TEXT_MODEL ({configured_text}) failed the text test!{RESET}")
    all_ok = False
if not audio_results.get(configured_audio):
    print(f"  {RED}[!] Your configured AUDIO_MODEL ({configured_audio}) failed the audio test!{RESET}")
    all_ok = False
if all_ok:
    print(f"  {GREEN}[OK] All configured models are working correctly.{RESET}")

print()
sys.exit(0 if all_ok else 1)
