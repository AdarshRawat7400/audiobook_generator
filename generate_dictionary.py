"""
generate_dictionary.py
Generates a comprehensive Hindi word dictionary (शब्दकोश) for complex, archaic,
Sanskrit, Bundelkhandi, and Persian-origin words used across all poems.

The entire poem collection is sent to the LLM so it can identify and explain
every difficult word in context, organized alphabetically in Devanagari order.
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
OUTPUT_DIR = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re") / "Word_Dictionary"
OUTPUT_FILE = OUTPUT_DIR / "shabdakosh.md"

DICTIONARY_MODEL = os.getenv("DICTIONARY_MODEL", "gemini-3.5-flash")
API_CALL_DELAY = int(os.getenv("API_CALL_DELAY", "3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# File classification — only poems
POEM_RANGE = range(5, 56)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dictionary_generation.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

client = genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_file_id(filename: str) -> int | None:
    match = re.match(r'^(\d+)', filename)
    return int(match.group(1)) if match else None


def clean_title(filename: str) -> str:
    match = re.match(r'^\d+[_\-\s]*(.+)$', filename)
    return match.group(1) if match else filename


def load_poems() -> tuple[str, list[str]]:
    """Load all poem files and return combined text + list of titles."""
    md_files = sorted(SOURCE_DIR.glob("*.md"), key=lambda p: p.name)
    poem_parts = []
    titles = []

    for f in md_files:
        file_id = parse_file_id(f.name)
        if file_id is not None and file_id in POEM_RANGE:
            title = clean_title(f.stem)
            text = f.read_text(encoding="utf-8").strip()
            poem_parts.append(f"### कविता: {title}\n\n{text}")
            titles.append(title)

    combined = "\n\n---\n\n".join(poem_parts)
    logger.info(f"Loaded {len(titles)} poems, total size: {len(combined):,} chars")
    return combined, titles


def build_dictionary_prompt(all_poems: str, titles: list[str]) -> str:
    """Build the prompt for dictionary generation."""
    titles_str = ", ".join(titles)

    return f"""आप एक विद्वान हिन्दी भाषाविज्ञानी और शब्दकोशकार हैं। आपको संस्कृत, बुन्देलखण्डी बोली, 
फ़ारसी-अरबी मूल के हिन्दी शब्दों, और प्राचीन/अप्रचलित हिन्दी शब्दावली का गहन ज्ञान है।

आपको कवि अवध बिहारी रावत के काव्य संग्रह "नदिया तीर कछारे मेरा गाँव रे" की समस्त 51 कविताएँ दी जा रही हैं।

═══════════════════════════════════════════════
कविताएँ:
═══════════════════════════════════════════════

{all_poems}

═══════════════════════════════════════════════

कृपया इन सभी कविताओं में प्रयुक्त कठिन, असामान्य, संस्कृतनिष्ठ (तत्सम), बुन्देलखण्डी, 
फ़ारसी/अरबी मूल के, और ऐसे सभी शब्दों का एक विस्तृत शब्दकोश तैयार करें जो 
आधुनिक हिन्दी पाठक के लिए कठिन हो सकते हैं।

## शब्दकोश में शामिल करने के मानदंड:
1. **संस्कृतनिष्ठ/तत्सम शब्द** — जैसे प्रस्फुटित, निष्पत्ति, आप्लावित, द्रवीभूत आदि
2. **बुन्देलखण्डी/स्थानीय शब्द** — जैसे सैर, कछारे, मोरा, बारे आदि  
3. **फ़ारसी/अरबी मूल के शब्द** — जैसे करिश्मा, तूफान, मसीहा आदि
4. **पौराणिक/ऐतिहासिक संदर्भ शब्द** — जैसे द्रुपदसुता, प्रहलाद, रघुवीर आदि
5. **अप्रचलित/असामान्य हिन्दी शब्द** — जो आज की बोलचाल में कम प्रयुक्त होते हैं
6. **काव्यशास्त्रीय शब्द** — छंद, अलंकार संबंधी शब्द

## प्रारूप (Format):

शब्दकोश को देवनागरी वर्णमाला के क्रम में (अ, आ, इ, ई... क, ख, ग... ) व्यवस्थित करें।

प्रत्येक अक्षर के लिए एक तालिका बनाएँ:

### [अक्षर]

| शब्द | अर्थ | मूल (संस्कृत/बुन्देलखण्डी/फ़ारसी/हिन्दी) | कविता | उदाहरण पंक्ति |
|------|------|------|---------|-------------|
| ... | ... | ... | ... | ... |

## महत्वपूर्ण निर्देश:
- कम से कम **150-200 शब्द** शामिल करें
- प्रत्येक शब्द का **सटीक अर्थ** दें
- **मूल भाषा** (संस्कृत, बुन्देलखण्डी, फ़ारसी, अरबी, अंग्रेज़ी) बताएँ
- वह **कविता का नाम** बताएँ जिसमें यह शब्द आया है
- कविता से **उदाहरण पंक्ति** उद्धृत करें (संक्षिप्त)
- सम्पूर्ण शब्दकोश **शुद्ध हिन्दी** में होना चाहिए
"""


def generate_with_retry(prompt: str, model: str) -> str:
    """Call Gemini with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(API_CALL_DELAY)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=65536
                )
            )
            if response.text:
                return response.text
            else:
                raise ValueError("Model returned empty text response.")

        except ClientError as e:
            if e.status == 429:
                delay_match = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(e))
                wait = float(delay_match.group(1)) if delay_match else (30 * attempt)
                logger.warning(f"Rate limited (429). Waiting {wait:.0f}s... (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
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
        description="Generate a comprehensive Hindi word dictionary for the poetry collection."
    )
    parser.add_argument("--model", type=str, default=DICTIONARY_MODEL,
                        help=f"Gemini model to use (default: {DICTIONARY_MODEL}).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if dictionary file already exists.")
    args = parser.parse_args()

    model = args.model
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  WORD DICTIONARY GENERATOR — शब्दकोश")
    print(f"{'='*60}")
    print(f"  Model:   {model}")
    print(f"  Output:  {OUTPUT_FILE}")
    print(f"{'='*60}\n")

    if OUTPUT_FILE.exists() and not args.force:
        logger.info(f"Dictionary already exists: {OUTPUT_FILE}")
        logger.info("Use --force to regenerate.")
        return

    # Load all poems
    logger.info("Loading all poems...")
    all_poems, titles = load_poems()

    # Build prompt and generate
    logger.info(f"Generating dictionary using {model}...")
    prompt = build_dictionary_prompt(all_poems, titles)
    dictionary_text = generate_with_retry(prompt, model)

    # Add header
    header = "# शब्दकोश — नदिया तीर कछारे मेरा गाँव रे\n\n"
    header += "*काव्य संग्रह: नदिया तीर कछारे मेरा गाँव रे*  \n"
    header += "*कवि: अवध बिहारी रावत*  \n"
    header += f"*निर्माण मॉडल: {model}*\n\n"
    header += "यह शब्दकोश काव्य संग्रह की 51 कविताओं में प्रयुक्त कठिन, संस्कृतनिष्ठ, "
    header += "बुन्देलखण्डी, फ़ारसी/अरबी मूल के, और अप्रचलित शब्दों का संकलन है।\n\n"
    header += "---\n\n"

    full_content = header + dictionary_text

    OUTPUT_FILE.write_text(full_content, encoding="utf-8")
    logger.info(f"[OK] Dictionary saved: {OUTPUT_FILE} ({len(full_content):,} chars)")

    print(f"\n{'='*60}")
    print(f"  DICTIONARY GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  File: {OUTPUT_FILE}")
    print(f"  Size: {len(full_content):,} characters")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
