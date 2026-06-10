import os
import re
import sys
import logging
import wave
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception, before_sleep_log
)
import config

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

client = genai.Client(api_key=api_key)

# ---------------------------------------------------------------------------
# Logging: dual output — file + console
# ---------------------------------------------------------------------------
logger = logging.getLogger("audiobook")
logger.setLevel(logging.DEBUG)

# File handler — full detail
file_handler = logging.FileHandler(
    str(config.LOGS_DIR / "generation.log"), encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

# Console handler — concise, with color
class ColorFormatter(logging.Formatter):
    """ANSI color formatter for console output."""
    COLORS = {
        "DEBUG": "\033[90m",    # grey
        "INFO": "\033[36m",     # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[91m", # bright red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ColorFormatter("%(levelname)s: %(message)s"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Also wire up the root logger so existing logging.info() calls still work
logging.root.handlers = []
logging.root.addHandler(file_handler)
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# API call tracking
# ---------------------------------------------------------------------------
_api_call_counts: dict[str, int] = {}

def get_api_call_counts() -> dict[str, int]:
    """Return a copy of the API call counter."""
    return dict(_api_call_counts)

def _track_call(model: str):
    _api_call_counts[model] = _api_call_counts.get(model, 0) + 1

# ---------------------------------------------------------------------------
# Smart retry logic
# ---------------------------------------------------------------------------
def _is_retryable(exc: BaseException) -> bool:
    """Only retry on rate-limit (429) and server errors (500/502/503).
    Do NOT retry on 400 INVALID_ARGUMENT, 404 NOT_FOUND, etc."""
    if isinstance(exc, ClientError):
        return exc.status == 429
    if isinstance(exc, ServerError):
        return True
    if isinstance(exc, AttributeError):
        # Malformed response — retry in case it's transient
        return True
    return False

def _parse_retry_delay(exc: BaseException) -> float | None:
    """Try to extract the server-suggested retryDelay from a 429 error."""
    try:
        msg = str(exc)
        match = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", msg)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None

def _wait_for_rate_limit(retry_state):
    """Custom before-sleep hook: if the error is a 429 with a retryDelay,
    sleep for the server-suggested duration instead of the exponential backoff."""
    exc = retry_state.outcome.exception()
    if exc:
        delay = _parse_retry_delay(exc)
        if delay and delay > 0:
            logger.warning(
                f"Rate limited (429). Server says retry in {delay:.0f}s — waiting..."
            )
            time.sleep(delay)
            return
    # Fallback: log the default backoff
    wait_time = retry_state.next_action.sleep
    logger.warning(f"Retrying in {wait_time:.1f}s (attempt {retry_state.attempt_number})...")

# ---------------------------------------------------------------------------
# Text generation
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(config.MAX_RETRIES_TEXT),
    wait=wait_exponential(multiplier=2, min=2, max=config.RETRY_MAX_WAIT),
    retry=retry_if_exception(_is_retryable),
    before_sleep=_wait_for_rate_limit,
    reraise=True,
)
def generate_text(prompt: str, model: str) -> str:
    """Generate text content using the specified Gemini model."""
    time.sleep(config.API_CALL_DELAY)
    _track_call(model)
    logger.debug(f"Calling {model} for text generation...")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3)
    )

    if not response.text:
        raise ValueError(f"Model {model} returned empty text response.")

    return response.text

# ---------------------------------------------------------------------------
# Audio generation
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(config.MAX_RETRIES_AUDIO),
    wait=wait_exponential(multiplier=2, min=2, max=config.RETRY_MAX_WAIT),
    retry=retry_if_exception(_is_retryable),
    before_sleep=_wait_for_rate_limit,
    reraise=True,
)
def generate_audio(text: str, voice_name: str, model: str, output_path: str):
    """Generate audio narration and save as WAV file."""
    time.sleep(config.API_CALL_DELAY)
    _track_call(model)
    logger.debug(f"Calling {model} for audio generation (voice={voice_name})...")

    system_instruction = (
        "You are a professional Indian literary narrator. "
        "Your ONLY task is to read the provided text EXACTLY as written. "
        "Do NOT summarize, explain, add greetings, or skip any content. "
        "Read it warmly, clearly, and with dignity."
    )

    response = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            )
        )
    )

    # --- Validate the response before writing ---
    if not response.candidates:
        raise ValueError(
            f"Model {model} returned no candidates. "
            f"Response: {response}"
        )

    candidate = response.candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)

    if not candidate.content or not candidate.content.parts:
        raise ValueError(
            f"Model {model} returned empty content. "
            f"finish_reason={finish_reason}"
        )

    part = candidate.content.parts[0]
    if not hasattr(part, "inline_data") or part.inline_data is None:
        raise ValueError(
            f"Model {model} returned no audio data in response. "
            f"finish_reason={finish_reason}, part_type={type(part)}"
        )

    audio_data = part.inline_data.data
    if not audio_data:
        raise ValueError(
            f"Model {model} returned empty audio bytes. "
            f"finish_reason={finish_reason}"
        )

    # --- Write validated audio data ---
    with wave.open(output_path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(audio_data)

    file_size_kb = os.path.getsize(output_path) / 1024
    logger.info(f"Audio saved: {output_path} ({file_size_kb:.1f} KB)")