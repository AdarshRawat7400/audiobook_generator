import os
from pathlib import Path
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

# ---------------------------------------------------------------------------
# Client initialization: Vertex AI (GCP credits) or AI Studio (API key)
# ---------------------------------------------------------------------------
gcp_project = os.getenv("GCP_PROJECT_ID")
gcp_location = os.getenv("GCP_LOCATION", "us-central1")
api_key = os.getenv("GEMINI_API_KEY")

if gcp_project:
    # Use Vertex AI — bills to GCP project (uses GCP credits)
    client = genai.Client(vertexai=True, project=gcp_project, location=gcp_location)
    print(f"✅ Using Vertex AI (project={gcp_project}, location={gcp_location})")
elif api_key:
    # Fallback to AI Studio — uses API key billing
    client = genai.Client(api_key=api_key)
    print("✅ Using Google AI Studio (API key)")
else:
    raise ValueError(
        "No credentials found. Set either GCP_PROJECT_ID (for Vertex AI / GCP credits) "
        "or GEMINI_API_KEY (for AI Studio) in your .env file."
    )

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
# Audio generation with Chunking
# ---------------------------------------------------------------------------
def split_text_for_tts(text: str, max_chars: int = 800) -> list[str]:
    """Splits text into chunks of maximum max_chars while keeping sentences/paragraphs intact."""
    # First, split by paragraphs/double newlines
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            # Split by sentence boundaries (।, ., ?, !)
            sentences = re.split(r'([।\.!\?\n])', para)
            current_chunk = ""
            i = 0
            while i < len(sentences):
                sentence = sentences[i]
                delimiter = sentences[i+1] if i + 1 < len(sentences) else ""
                full_sentence = (sentence + delimiter).strip()
                i += 2
                
                if not full_sentence:
                    continue
                    
                if len(current_chunk) + len(full_sentence) + 1 <= max_chars:
                    if current_chunk:
                        current_chunk += " " + full_sentence
                    else:
                        current_chunk = full_sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    if len(full_sentence) > max_chars:
                        # Split by clauses/commas
                        sub_sentences = re.split(r'([,，;])', full_sentence)
                        j = 0
                        sub_chunk = ""
                        while j < len(sub_sentences):
                            sub_s = sub_sentences[j]
                            sub_delim = sub_sentences[j+1] if j + 1 < len(sub_sentences) else ""
                            full_sub = (sub_s + sub_delim).strip()
                            j += 2
                            if not full_sub:
                                continue
                            if len(sub_chunk) + len(full_sub) + 1 <= max_chars:
                                if sub_chunk:
                                    sub_chunk += " " + full_sub
                                else:
                                    sub_chunk = full_sub
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk)
                                if len(full_sub) > max_chars:
                                    # Fallback: force split by characters
                                    for k in range(0, len(full_sub), max_chars):
                                        chunks.append(full_sub[k:k+max_chars])
                                    sub_chunk = ""
                                else:
                                    sub_chunk = full_sub
                        if sub_chunk:
                            current_chunk = sub_chunk
                    else:
                        current_chunk = full_sentence
            if current_chunk:
                chunks.append(current_chunk)
                
    # Filter out empty chunks or chunks that only contain punctuation/spaces
    valid_chunks = []
    for c in chunks:
        c = c.strip()
        # Ensure it contains at least one letter or number (filters out standalone punctuation like "." or "-")
        if c and re.search(r'[^\W_]', c):
            valid_chunks.append(c)
    return valid_chunks


@retry(
    stop=stop_after_attempt(config.MAX_RETRIES_AUDIO),
    wait=wait_exponential(multiplier=2, min=2, max=config.RETRY_MAX_WAIT),
    retry=retry_if_exception(_is_retryable),
    before_sleep=_wait_for_rate_limit,
    reraise=True,
)
def _generate_audio_chunk(text: str, voice_name: str, model: str, output_path: str,
                         system_instruction: str | None = None):
    """Generate audio narration for a single text chunk and save as WAV file."""
    time.sleep(config.API_CALL_DELAY)
    _track_call(model)
    logger.debug(f"Calling {model} for audio chunk generation (voice={voice_name})...")

    if system_instruction is None:
        system_instruction = config.NARRATION_SYSTEM_INSTRUCTION

    # Dedicated TTS models (e.g. gemini-2.5-flash-tts) do NOT support
    # system_instruction — embed the style instruction in the content instead.
    is_tts_model = "tts" in model.lower()

    if is_tts_model:
        # Prepend style instruction to the text content
        styled_content = f"{system_instruction.strip()}\n\n---\n\nText to read:\n{text}"
        response = client.models.generate_content(
            model=model,
            contents=styled_content,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                    )
                )
            )
        )
    else:
        # Standard Gemini models support system_instruction
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
    logger.debug(f"Chunk audio saved: {output_path} ({file_size_kb:.1f} KB)")


def generate_audio(text: str, voice_name: str, model: str, output_path: str,
                   system_instruction: str | None = None):
    """Generate audio narration, chunking if the text is too long, and save as WAV file.
    
    Args:
        text: The text to narrate.
        voice_name: Gemini voice preset name.
        model: Model identifier.
        output_path: Where to save the WAV file.
        system_instruction: Custom system instruction for audio style.
    """
    # Check if we need to chunk the text
    if len(text) <= config.MAX_TTS_CHARS:
        _generate_audio_chunk(text, voice_name, model, output_path, system_instruction)
        file_size_kb = os.path.getsize(output_path) / 1024
        logger.info(f"Audio saved: {output_path} ({file_size_kb:.1f} KB)")
        return

    # Chunking required
    chunks = split_text_for_tts(text, config.MAX_TTS_CHARS)
    logger.info(f"Generating audio in {len(chunks)} chunks for: {output_path}")

    chunk_files = []
    try:
        for idx, chunk in enumerate(chunks):
            # Unique temp file for each chunk in the same directory as output_path
            chunk_file = Path(output_path).with_suffix(f".chunk_{idx}.wav")
            chunk_files.append(str(chunk_file))
            
            logger.debug(f"Generating chunk {idx+1}/{len(chunks)} ({len(chunk)} chars) for {output_path}")
            _generate_audio_chunk(chunk, voice_name, model, str(chunk_file), system_instruction)

        # Concatenate all chunk files
        silence_duration = config.TTS_CHUNK_SILENCE_SECONDS
        silence_bytes = b'\x00' * int(24000 * 2 * silence_duration)

        data = []
        params = None

        for path in chunk_files:
            with wave.open(path, 'rb') as w:
                w_params = w.getparams()
                if params is None:
                    params = w_params
                data.append(w.readframes(w.getnframes()))

        if params is not None:
            with wave.open(output_path, 'wb') as w_out:
                w_out.setparams(params)
                for idx, frames in enumerate(data):
                    if idx > 0 and silence_duration > 0:
                        w_out.writeframes(silence_bytes)
                    w_out.writeframes(frames)

        file_size_kb = os.path.getsize(output_path) / 1024
        logger.info(f"Audio saved (concatenated {len(chunks)} chunks): {output_path} ({file_size_kb:.1f} KB)")

    finally:
        # Cleanup chunk files
        for path in chunk_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to remove temp chunk file {path}: {e}")