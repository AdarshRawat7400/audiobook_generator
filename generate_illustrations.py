import os
from pathlib import Path
import logging
import time
from tqdm import tqdm
from google.genai import types
import config
from gemini_client import client, _track_call, _wait_for_rate_limit, _is_retryable, _parse_retry_delay
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

# Setup logging
logger = logging.getLogger("illustrations")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(str(config.LOGS_DIR / "illustrations.log"), encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

source_dir = Path(r"C:\Users\adars\Desktop\audiobook_generator\Nadiya_Teer_Kachare_Mera_Gaon_Re\Source")
output_dir = Path(r"C:\Users\adars\Desktop\audiobook_generator\output\illustrations")
output_dir.mkdir(parents=True, exist_ok=True)

PROMPT_GENERATION_INSTRUCTION = """You are an expert art director and illustrator specializing in Indian history, specifically the Bundelkhand region.
Read the following Hindi text. 
Based on its core theme, generate a highly detailed English image generation prompt.
Requirements:
1. Authentic representation of Bundelkhand landscapes, architecture, clothing, and daily life.
2. Painterly, storybook-style aesthetic with rich natural colors and cinematic composition.
3. Capture the exact emotion or key subject of the text.
4. CRITICAL: Do NOT show people with visible faces. Use pure landscapes, symbolic objects, silhouettes, or people facing away from the camera.
5. Output ONLY the English prompt string, nothing else. No quotes, no markdown, no intro text.
Text:
"""

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_image_prompt(text: str) -> str:
    """Generate an English image prompt from the Hindi text using gemini-2.5-flash."""
    _track_call("gemini-2.5-flash")
    time.sleep(config.API_CALL_DELAY)
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=PROMPT_GENERATION_INSTRUCTION + text,
        config=types.GenerateContentConfig(
            temperature=0.7,
        )
    )
    return response.text.strip()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_illustration(prompt: str, output_path: str):
    """Generate the image using Imagen 3 and save it."""
    _track_call("imagen-3.0-generate-001")
    time.sleep(config.API_CALL_DELAY)
    
    result = client.models.generate_images(
        model='imagen-3.0-generate-001',
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/jpeg",
            aspect_ratio="1:1",
        )
    )
    
    with open(output_path, "wb") as f:
        f.write(result.generated_images[0].image.image_bytes)

def main():
    md_files = sorted(list(source_dir.glob("*.md")))
    logger.info(f"Found {len(md_files)} files to process.")
    
    succeeded = 0
    failed = 0
    skipped = 0
    
    for md_file in tqdm(md_files, desc="Illustrations"):
        base_name = md_file.stem
        output_path = output_dir / f"{base_name}.jpg"
        
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"[SKIP] Illustration already exists: {base_name}")
            skipped += 1
            continue
            
        logger.info(f"Processing: {base_name}")
        
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                text = f.read()
                
            # Strip some basic YAML frontmatter if it exists to help the LLM focus on body
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    text = parts[2].strip()
            
            if not text.strip():
                logger.warning(f"[SKIP] Empty file: {base_name}")
                skipped += 1
                continue
                
            logger.debug("Generating prompt...")
            prompt = generate_image_prompt(text)
            logger.debug(f"Prompt: {prompt}")
            
            logger.debug("Generating image...")
            generate_illustration(prompt, str(output_path))
            
            logger.info(f"[OK] Completed: {base_name}")
            succeeded += 1
            
        except Exception as e:
            logger.error(f"[FAIL] Error processing {base_name}: {str(e)}")
            failed += 1
            
    logger.info("=" * 60)
    logger.info("  PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  [OK]      Succeeded: {succeeded}")
    logger.info(f"  [FAIL]    Failed:    {failed}")
    logger.info(f"  [SKIP]    Skipped:   {skipped}")
    logger.info(f"  [TOTAL]   Total:     {succeeded + failed + skipped}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
