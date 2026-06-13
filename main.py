import argparse
import re
import sys
import os
import concurrent.futures
from pathlib import Path
from tqdm import tqdm
import logging

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from text_preprocessor import clean_text
from tts_generator import generate_narration
from explainer_generator import generate_explainer_audio
from manifest_generator import init_manifest, update_manifest
from gemini_client import get_api_call_counts

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
class ProcessResult:
    """Tracks the outcome of processing a single file."""
    def __init__(self, filename: str, status: str, detail: str = ""):
        self.filename = filename
        self.status = status      # "success", "failed", "skipped"
        self.detail = detail

# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------
def process_file(file_path: Path, dry_run: bool = False) -> ProcessResult:
    """Process a single text file: generate narration + explainer audio.
    Returns a ProcessResult indicating success/failure/skip."""
    try:
        match = re.match(r'^(\d+)[_-](.+)\.md$', file_path.name)
        if match:
            file_id = int(match.group(1))
            title = match.group(2).strip()
        else:
            file_id = 999
            title = file_path.stem

        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read().strip()

        if not raw_text:
            logging.warning(f"Skipping empty file: {file_path.name}")
            return ProcessResult(file_path.name, "skipped", "Empty file")

        # Clean Markdown/formatting artifacts before sending to AI
        text = clean_text(raw_text)
        if not text:
            logging.warning(f"Skipping file (empty after cleaning): {file_path.name}")
            return ProcessResult(file_path.name, "skipped", "Empty after cleaning")

        if dry_run:
            logging.info(f"[DRY RUN] Would process: {file_path.name} (id={file_id}, title={title}, {len(raw_text)} raw -> {len(text)} cleaned chars)")
            return ProcessResult(file_path.name, "skipped", "Dry run")

        logging.info(f"Processing [{file_id:03d}]: {title}")

        male_audio, female_audio = generate_narration(file_id, title, text)
        male_exp_audio, female_exp_audio = generate_explainer_audio(file_id, title, text)

        manifest_entry = {
            "id": file_id,
            "title": title,
            "maleAudio": male_audio,
            "femaleAudio": female_audio
        }
        if male_exp_audio and female_exp_audio:
            manifest_entry["maleExplainer"] = male_exp_audio
            manifest_entry["femaleExplainer"] = female_exp_audio

        update_manifest(manifest_entry)
        logging.info(f"[OK] Completed [{file_id:03d}]: {title}")
        return ProcessResult(file_path.name, "success")

    except Exception as e:
        logging.error(f"[FAIL] {file_path.name}: {e}")
        return ProcessResult(file_path.name, "failed", str(e))

# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def print_summary(results: list[ProcessResult]):
    """Print a colored summary of the processing run."""
    success = [r for r in results if r.status == "success"]
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]

    print("\n" + "=" * 60)
    print("  PROCESSING SUMMARY")
    print("=" * 60)
    print(f"  \033[32m[OK]      Succeeded: {len(success)}\033[0m")
    print(f"  \033[31m[FAIL]    Failed:    {len(failed)}\033[0m")
    print(f"  \033[33m[SKIP]    Skipped:   {len(skipped)}\033[0m")
    print(f"  [TOTAL]   Total:     {len(results)}")

    if failed:
        print("\n  Failed files:")
        for r in failed:
            print(f"    \033[31m- {r.filename}: {r.detail[:80]}\033[0m")

    # API call stats
    api_counts = get_api_call_counts()
    if api_counts:
        print("\n  API calls made:")
        for model, count in sorted(api_counts.items()):
            print(f"    - {model}: {count} calls")

    print("=" * 60 + "\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate audiobooks from Hindi text files using Gemini AI."
    )
    parser.add_argument("--input-dir", type=str, default=str(config.DEFAULT_INPUT_DIR),
                        help="Path to folder containing .md files.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate input files without making API calls.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"[ERROR] Input directory not found: {input_dir}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  GEMINI AUDIOBOOK GENERATOR")
    print("=" * 60)
    print(f"  Input:       {input_dir}")
    print(f"  Text Model:  {config.TEXT_MODEL}")
    print(f"  Audio Model: {config.AUDIO_MODEL}")
    print(f"  Workers:     {config.MAX_CONCURRENT_WORKERS}")
    print(f"  API Delay:   {config.API_CALL_DELAY}s")
    print(f"  Audio Style: All India Radio (Akashvani)")
    if args.dry_run:
        print("  Mode:        DRY RUN (no API calls)")
    print("=" * 60 + "\n")

    init_manifest()

    md_files = sorted(
        list(input_dir.glob("*.md")),
        key=lambda x: x.name
    )
    if not md_files:
        print("[!] No MD files found in the input directory.")
        return

    print(f"[*] Found {len(md_files)} files. Starting generation...\n")

    results: list[ProcessResult] = []

    if config.MAX_CONCURRENT_WORKERS <= 1:
        # Sequential processing — simpler for rate-limited APIs
        for p in tqdm(md_files, desc="Processing", unit="file"):
            result = process_file(p, dry_run=args.dry_run)
            results.append(result)
    else:
        # Concurrent processing
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.MAX_CONCURRENT_WORKERS
        ) as executor:
            futures = {
                executor.submit(process_file, p, args.dry_run): p
                for p in md_files
            }
            for future in tqdm(
                concurrent.futures.as_completed(futures),
                total=len(md_files),
                desc="Processing",
                unit="file"
            ):
                result = future.result()
                results.append(result)

    print_summary(results)

    # Exit with error code if any files failed
    failed_count = sum(1 for r in results if r.status == "failed")
    if failed_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()