"""
generate_explainers.py
Generates deep literary explanations for each poem in the collection,
using the ENTIRE book content as context for best quality generation.

Key Design:
- Loads ALL 56 source files to build full book context
- For each poem, sends the full book + focused prompt to Gemini
- Produces scholarly Hindi explanations covering meaning, themes, 
  literary devices, cultural references, and cross-poem connections
- Supports resume (skips already-generated explainers)
- Rate-limited with retry logic
"""

import os
import re
import sys
import time
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOURCE_DIR = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re") / "Source"
OUTPUT_DIR = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re") / "Explainers"

# Which model to use — use the best available for deep literary analysis
EXPLAINER_MODEL = os.getenv("EXPLAINER_MODEL", "gemini-3.5-flash")

# Rate limiting
API_CALL_DELAY = int(os.getenv("API_CALL_DELAY", "3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# File classification
PREFACE_RANGE = range(1, 5)      # 001–004
POEM_RANGE = range(5, 56)        # 005–055
POSTFACE_RANGE = range(56, 57)   # 056

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("explainer_generation.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini Client Setup
# ---------------------------------------------------------------------------
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

client = genai.Client(api_key=api_key)

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def parse_file_id(filename: str) -> int | None:
    """Extract numeric prefix from filename."""
    match = re.match(r'^(\d+)', filename)
    return int(match.group(1)) if match else None


def clean_title(filename: str) -> str:
    """Extract title from filename, stripping numeric prefix."""
    match = re.match(r'^\d+[_\-\s]*(.+)$', filename)
    return match.group(1) if match else filename


def load_all_source_files() -> tuple[str, list[dict]]:
    """
    Load all source files and return:
    - full_book_text: the entire book as a single string
    - poems: list of dicts with {id, title, text, filename} for poem files only
    """
    md_files = sorted(SOURCE_DIR.glob("*.md"), key=lambda p: p.name)
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {SOURCE_DIR}")

    full_book_parts = []
    poems = []

    for f in md_files:
        file_id = parse_file_id(f.name)
        title = clean_title(f.stem)
        text = f.read_text(encoding="utf-8").strip()

        # Add to full book text
        full_book_parts.append(f"### {title}\n\n{text}")

        # Track poems separately
        if file_id is not None and file_id in POEM_RANGE:
            poems.append({
                "id": file_id,
                "seq": file_id - 4,  # 005→1, 006→2, ...
                "title": title,
                "text": text,
                "filename": f.name
            })

    full_book_text = "\n\n---\n\n".join(full_book_parts)
    logger.info(f"Loaded {len(md_files)} files, {len(poems)} poems, "
                f"total book size: {len(full_book_text):,} chars")

    return full_book_text, poems


def build_explainer_prompt(full_book: str, poem: dict) -> str:
    """
    Build the prompt for generating an explainer for a specific poem.
    The full book is included as context so the model understands 
    the complete collection before analyzing an individual poem.
    """
    return f"""आप एक विख्यात हिन्दी साहित्य के प्रोफेसर और काव्य समीक्षक हैं। आपको बुन्देलखण्डी संस्कृति, 
वैष्णव भक्ति काव्य परंपरा, और स्वतंत्रता-पश्चात हिन्दी साहित्य का गहन ज्ञान है।

आपको कवि अवध बिहारी रावत का सम्पूर्ण काव्य संग्रह "नदिया तीर कछारे मेरा गाँव रे" दिया जा रहा है। 
कृपया पहले पूरे संग्रह को पढ़ें और कवि की शैली, विषय-वस्तु, भाव-भूमि और सांस्कृतिक पृष्ठभूमि को आत्मसात करें।

═══════════════════════════════════════════════
सम्पूर्ण काव्य संग्रह:
═══════════════════════════════════════════════

{full_book}

═══════════════════════════════════════════════
अब इस विशिष्ट कविता की व्याख्या करें:
═══════════════════════════════════════════════

कविता: "{poem['title']}"

{poem['text']}

═══════════════════════════════════════════════

कृपया इस कविता की गहन, विद्वतापूर्ण व्याख्या निम्नलिखित शीर्षकों के अंतर्गत प्रस्तुत करें। 
सम्पूर्ण व्याख्या शुद्ध हिन्दी में होनी चाहिए:

## कविता का परिचय
(कवि ने यह कविता किस संदर्भ में लिखी, इसका सामान्य विषय क्या है)

## सरल अर्थ
(कविता का पंक्ति-दर-पंक्ति या पद-दर-पद सरल अर्थ, जिसे कोई भी पाठक समझ सके)

## काव्य विधा एवं छंद
(यह किस काव्य विधा में है — गीत, ग़ज़ल, घनाक्षरी, सैर, छंदबद्ध कविता आदि। छंद, लय और तुकांत की विशेषताएँ)

## प्रमुख विषय-वस्तु
(कविता के मुख्य विषय — भक्ति, शृंगार, देशप्रेम, दर्शन, सामाजिक चेतना आदि)

## बिम्ब एवं प्रतीक
(कविता में प्रयुक्त बिम्ब-विधान और प्रतीकात्मकता)

## अलंकार
(प्रमुख अलंकार — उपमा, रूपक, अनुप्रास, यमक, श्लेष आदि — उदाहरण सहित)

## सांस्कृतिक एवं ऐतिहासिक संदर्भ
(बुन्देलखण्डी संस्कृति, ऐतिहासिक घटनाएँ, पौराणिक कथाएँ, स्थानीय परंपराएँ — जो भी इस कविता से संबंधित हों)

## कवि का संदेश
(कवि क्या कहना चाहते हैं, पाठकों के लिए क्या सीख है)

## इस संग्रह की अन्य कविताओं से संबंध
(इस कविता का संग्रह की अन्य कविताओं से विषयगत, भावगत या शैलीगत संबंध)

## कठिन शब्दार्थ
(इस कविता में प्रयुक्त कठिन, संस्कृतनिष्ठ, बुन्देलखण्डी, या असामान्य शब्दों का अर्थ — तालिका रूप में)

| शब्द | अर्थ | मूल |
|------|------|------|
| ... | ... | ... |
"""


def generate_with_retry(prompt: str, model: str) -> str:
    """Call Gemini with retry logic for rate limits and server errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(API_CALL_DELAY)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=8192
                )
            )
            if response.text:
                return response.text
            else:
                raise ValueError("Model returned empty text response.")

        except ClientError as e:
            if e.status == 429:
                # Rate limited — extract retry delay if available
                delay_match = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(e))
                wait = float(delay_match.group(1)) if delay_match else (30 * attempt)
                logger.warning(f"Rate limited (429). Waiting {wait:.0f}s... (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                logger.error(f"Client error (status={e.status}): {e}")
                raise

        except ServerError as e:
            wait = 15 * attempt
            logger.warning(f"Server error. Waiting {wait}s... (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)

        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(10 * attempt)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate literary explainers for each poem using Gemini with full book context."
    )
    parser.add_argument("--test-one", action="store_true",
                        help="Generate explainer for only the first poem (test mode).")
    parser.add_argument("--poem-id", type=int, default=None,
                        help="Generate explainer for a specific poem sequence number (1-51).")
    parser.add_argument("--model", type=str, default=EXPLAINER_MODEL,
                        help=f"Gemini model to use (default: {EXPLAINER_MODEL}).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if explainer file already exists.")
    args = parser.parse_args()

    model = args.model
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  EXPLAINER GENERATOR — नदिया तीर कछारे मेरा गाँव रे")
    print(f"{'='*60}")
    print(f"  Model:   {model}")
    print(f"  Output:  {OUTPUT_DIR}")
    print(f"  Delay:   {API_CALL_DELAY}s between calls")
    if args.test_one:
        print(f"  Mode:    TEST (first poem only)")
    elif args.poem_id:
        print(f"  Mode:    SINGLE (poem #{args.poem_id})")
    else:
        print(f"  Mode:    FULL (all 51 poems)")
    print(f"{'='*60}\n")

    # Load everything
    logger.info("Loading entire book content...")
    full_book, poems = load_all_source_files()

    # Filter poems if needed
    if args.test_one:
        poems = poems[:1]
    elif args.poem_id:
        poems = [p for p in poems if p["seq"] == args.poem_id]
        if not poems:
            logger.error(f"No poem found with sequence number {args.poem_id}")
            sys.exit(1)

    # Generate explainers
    success = 0
    skipped = 0
    failed = 0

    for i, poem in enumerate(poems, 1):
        output_file = OUTPUT_DIR / f"{poem['seq']:02d}_{poem['title']}_explainer.md"

        # Resume support
        if output_file.exists() and not args.force:
            logger.info(f"[SKIP] Already exists: {output_file.name}")
            skipped += 1
            continue

        logger.info(f"[{i}/{len(poems)}] Generating explainer for: {poem['title']} (seq={poem['seq']})")

        try:
            prompt = build_explainer_prompt(full_book, poem)
            explainer_text = generate_with_retry(prompt, model)

            # Add header
            header = f"# {poem['title']} — काव्य व्याख्या\n\n"
            header += f"*काव्य संग्रह: नदिया तीर कछारे मेरा गाँव रे*  \n"
            header += f"*कवि: अवध बिहारी रावत*  \n"
            header += f"*व्याख्या मॉडल: {model}*\n\n---\n\n"

            full_content = header + explainer_text

            output_file.write_text(full_content, encoding="utf-8")
            logger.info(f"[OK] Saved: {output_file.name} ({len(full_content):,} chars)")
            success += 1

        except Exception as e:
            logger.error(f"[FAIL] {poem['title']}: {e}")
            failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  EXPLAINER GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  \033[32m[OK]   Generated: {success}\033[0m")
    print(f"  \033[33m[SKIP] Skipped:   {skipped}\033[0m")
    print(f"  \033[31m[FAIL] Failed:    {failed}\033[0m")
    print(f"  Total:           {success + skipped + failed}")
    print(f"{'='*60}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
