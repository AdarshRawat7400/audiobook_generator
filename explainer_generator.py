import logging
from pathlib import Path
import config
from gemini_client import generate_text, generate_audio

def requires_explainer(title: str) -> bool:
    for keyword in config.SKIP_EXPLAINER_KEYWORDS:
        if keyword in title:
            return False
    return True

def generate_explainer_content(title: str, text: str) -> str:
    """Generate explainer text using the text model.
    Saves the text to a file for debugging/review."""
    prompt = f"""
Please act as an experienced, respected Hindi literature professor. 
Create an educational explanation for the following poem in simple, clear Hindi. 
Do not include any English words. Format the explanation as a continuous, flowing speech:
1. Poem Introduction
2. Simple Meaning
3. Important Words
4. Main Themes
5. Imagery and Symbolism
6. Cultural References
7. Emotional Tone
8. Author Message
9. Key Takeaways

Title: {title}
{text}
"""
    logging.info(f"[TEXT] Generating explainer text for: {title}")
    explainer_text = generate_text(prompt, config.TEXT_MODEL)

    if not explainer_text or not explainer_text.strip():
        raise ValueError(f"Explainer text generation returned empty content for: {title}")

    # Save explainer text for review/debugging
    text_path = config.EXPLAINER_TEXT_DIR / f"{title}_explainer.md"
    text_path.write_text(explainer_text, encoding="utf-8")
    logging.info(f"[TEXT] Explainer text saved: {text_path} ({len(explainer_text)} chars)")

    return explainer_text

def generate_explainer_audio(file_id: int, title: str, original_text: str) -> tuple[str, str]:
    """Generate explainer narration (male + female) for a poem.
    Returns empty strings if the title matches skip keywords."""
    if not config.ENABLE_EXPLAINER or not requires_explainer(title):
        logging.info(f"[SKIP] Skipping explainer: {title}")
        return "", ""

    base_filename = f"{file_id:03d}_{title}_explainer.wav"
    male_exp_path = config.MALE_EXP_DIR / base_filename
    female_exp_path = config.FEMALE_EXP_DIR / base_filename

    # Check what needs generating
    need_male = not male_exp_path.exists()
    need_female = config.ENABLE_FEMALE_VOICE and not female_exp_path.exists()

    if not need_male and not need_female:
        logging.info(f"[SKIP] Explainer audio already exists: {title}")
        female_audio_rel = str(female_exp_path.relative_to(config.OUTPUT_DIR)) if config.ENABLE_FEMALE_VOICE else ""
        return (str(male_exp_path.relative_to(config.OUTPUT_DIR)), female_audio_rel)

    explainer_text = generate_explainer_content(title, original_text)

    if need_male:
        logging.info(f"[TTS] Generating Male Explainer Audio: {title}")
        generate_audio(explainer_text, config.MALE_VOICE, config.AUDIO_MODEL, str(male_exp_path))
    
    female_audio_rel = ""
    if need_female:
        logging.info(f"[TTS] Generating Female Explainer Audio: {title}")
        generate_audio(explainer_text, config.FEMALE_VOICE, config.AUDIO_MODEL, str(female_exp_path))
        female_audio_rel = str(female_exp_path.relative_to(config.OUTPUT_DIR))
    elif config.ENABLE_FEMALE_VOICE:
        female_audio_rel = str(female_exp_path.relative_to(config.OUTPUT_DIR))

    return (
        str(male_exp_path.relative_to(config.OUTPUT_DIR)),
        female_audio_rel
    )