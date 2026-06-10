"""
organize_book.py
Organizes 'Nadiya Teer Kachare Mera Gaon Re' source files into a structured folder layout.

Folder Structure:
  Nadiya_Teer_Kachare_Mera_Gaon_Re/
  ├── Source/          — Original raw text files (full copy)
  ├── Preface/         — Front matter (001–004)
  ├── Poems/           — The 51 poems (005–055), renumbered 01–51
  ├── Postface/        — Back matter (056)
  ├── Explainers/      — (empty, populated by generate_explainers.py)
  └── Word_Dictionary/ — (empty, populated by generate_dictionary.py)
"""

import re
import shutil
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOURCE_DIR = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re_Sections")
OUTPUT_ROOT = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re")

# Classification ranges (by original file number prefix)
PREFACE_RANGE = range(1, 5)      # 001–004: समर्पण, मंगल कामना, आमुख, दो-शब्द
POEM_RANGE = range(5, 56)        # 005–055: the 51 poems
POSTFACE_RANGE = range(56, 57)   # 056: रचनाकार परिचय

# Subfolders to create
SUBFOLDERS = ["Source", "Preface", "Poems", "Postface", "Explainers", "Word_Dictionary"]


def parse_file_id(filename: str) -> int | None:
    """Extract the numeric prefix from a filename like '005_सरस्वती-वंदना.md'."""
    match = re.match(r'^(\d+)', filename)
    return int(match.group(1)) if match else None


def clean_title(filename: str) -> str:
    """Extract the title portion from a filename, stripping the numeric prefix."""
    match = re.match(r'^\d+[_\-\s]*(.+)$', filename)
    return match.group(1) if match else filename


def organize():
    """Main organization logic."""
    if not SOURCE_DIR.exists():
        print(f"[ERROR] Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

    # Gather all .md files, sorted
    txt_files = sorted(SOURCE_DIR.glob("*.md"), key=lambda p: p.name)
    if not txt_files:
        print("[ERROR] No .md files found in source directory.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  BOOK ORGANIZER — नदिया तीर कछारे मेरा गाँव रे")
    print(f"{'='*60}")
    print(f"  Source:  {SOURCE_DIR} ({len(txt_files)} files)")
    print(f"  Output:  {OUTPUT_ROOT}")
    print(f"{'='*60}\n")

    # Create folder structure
    for folder in SUBFOLDERS:
        (OUTPUT_ROOT / folder).mkdir(parents=True, exist_ok=True)
        print(f"  [DIR] Created: {OUTPUT_ROOT / folder}")

    # Counters
    stats = {"source": 0, "preface": 0, "poems": 0, "postface": 0, "unknown": 0}

    # Process each file
    for src_file in txt_files:
        file_id = parse_file_id(src_file.name)
        title = clean_title(src_file.stem)

        # 1) Always copy to Source/
        dst_source = OUTPUT_ROOT / "Source" / src_file.name
        shutil.copy2(src_file, dst_source)
        stats["source"] += 1

        # 2) Classify and copy to appropriate subfolder
        if file_id is not None and file_id in PREFACE_RANGE:
            seq = file_id  # Keep 1-4
            dst = OUTPUT_ROOT / "Preface" / f"{seq:02d}_{title}.md"
            shutil.copy2(src_file, dst)
            stats["preface"] += 1
            print(f"  [PREFACE]  {src_file.name}  →  Preface/{dst.name}")

        elif file_id is not None and file_id in POEM_RANGE:
            seq = file_id - 4  # 005→01, 006→02, ... 055→51
            dst = OUTPUT_ROOT / "Poems" / f"{seq:02d}_{title}.md"
            shutil.copy2(src_file, dst)
            stats["poems"] += 1
            print(f"  [POEM]     {src_file.name}  →  Poems/{dst.name}")

        elif file_id is not None and file_id in POSTFACE_RANGE:
            seq = file_id - 55  # 056→01
            dst = OUTPUT_ROOT / "Postface" / f"{seq:02d}_{title}.md"
            shutil.copy2(src_file, dst)
            stats["postface"] += 1
            print(f"  [POSTFACE] {src_file.name}  →  Postface/{dst.name}")

        else:
            stats["unknown"] += 1
            print(f"  [???]      {src_file.name}  — unclassified (copied to Source only)")

    # Summary
    print(f"\n{'='*60}")
    print(f"  ORGANIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Source copies:  {stats['source']}")
    print(f"  Preface files:  {stats['preface']}")
    print(f"  Poem files:     {stats['poems']}")
    print(f"  Postface files: {stats['postface']}")
    if stats['unknown']:
        print(f"  Unclassified:   {stats['unknown']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    organize()
