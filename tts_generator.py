import logging
from pathlib import Path
import config
from gemini_client import generate_audio

def generate_narration(file_id: int, title: str, text: str) -> tuple[str, str]:
    """Generate male and female narration audio for a text.
    Raises on failure so the caller can track it."""
    base_filename = f"{file_id:03d}_{title}.wav"
    male_audio_path = config.MALE_DIR / base_filename
    female_audio_path = config.FEMALE_DIR / base_filename

    if not male_audio_path.exists():
        logging.info(f"[TTS] Generating Male Narration: {title}")
        generate_audio(text, config.MALE_VOICE, config.AUDIO_MODEL, str(male_audio_path))
    else:
        logging.info(f"[SKIP] Male narration already exists: {title}")

    female_audio_rel = ""
    if config.ENABLE_FEMALE_VOICE:
        if not female_audio_path.exists():
            logging.info(f"[TTS] Generating Female Narration: {title}")
            generate_audio(text, config.FEMALE_VOICE, config.AUDIO_MODEL, str(female_audio_path))
        else:
            logging.info(f"[SKIP] Female narration already exists: {title}")
        female_audio_rel = str(female_audio_path.relative_to(config.OUTPUT_DIR))

    return (
        str(male_audio_path.relative_to(config.OUTPUT_DIR)),
        female_audio_rel
    )