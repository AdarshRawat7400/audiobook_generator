#!/usr/bin/env python3
"""
Convert all .txt files in Nadiya_Teer_Kachare_Mera_Gaon_Re/ to nicely formatted .md files.

Handles:
- Source/, Preface/, Poems/, Postface/ subfolders
- Removes page markers like "*नदिया तीर कछारे मेरा गाँव रे       [19]*"
- Cleans trailing "---" separators
- Promotes ## to # for main title
- Adds metadata header (book name, author, section)
- Preserves poem formatting (line breaks, stanzas)
- Removes old .txt files after successful conversion
"""

import re
import sys
import os
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BOOK_ROOT = Path("Nadiya_Teer_Kachare_Mera_Gaon_Re")
BOOK_NAME = "नदिया तीर कछारे मेरा गाँव रे"
AUTHOR = "अवध बिहारी रावत"

# Page marker pattern: *नदिया तीर कछारे मेरा गाँव रे       [19]*
# Also catches standalone *नदिया तीर कछारे मेरा गाँव रे*
PAGE_MARKER_RE = re.compile(
    r'^\s*\*?\s*नदिया\s+तीर\s+कछारे\s+मेरा\s+गा[ँव]+\s+रे\s*(\[\d+\])?\s*\*?\s*$'
)

# Trailing horizontal rule
TRAILING_HR_RE = re.compile(r'^\s*-{3,}\s*$')

SECTION_LABELS = {
    "Source": "मूल पाठ",
    "Preface": "प्राक्कथन",
    "Poems": "कविता",
    "Postface": "परिशिष्ट",
}


def clean_content(text: str, title: str, section: str) -> str:
    """Clean and format the text content into proper markdown."""
    lines = text.split('\n')
    cleaned = []
    
    for line in lines:
        # Skip page markers
        if PAGE_MARKER_RE.match(line):
            continue
        cleaned.append(line)
    
    # Remove trailing blank lines and horizontal rules
    while cleaned and (not cleaned[-1].strip() or TRAILING_HR_RE.match(cleaned[-1])):
        cleaned.pop()
    
    # Remove leading blank lines
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    
    # Process the content
    content_lines = []
    title_found = False
    
    for line in cleaned:
        # Promote ## title to # (main heading)
        if not title_found and line.startswith('## '):
            content_lines.append('# ' + line[3:])
            title_found = True
        else:
            content_lines.append(line)
    
    # Build final markdown
    section_label = SECTION_LABELS.get(section, section)
    
    md_parts = []
    
    # Metadata block
    md_parts.append(f'---')
    md_parts.append(f'काव्य संग्रह: {BOOK_NAME}')
    md_parts.append(f'कवि: {AUTHOR}')
    md_parts.append(f'खंड: {section_label}')
    md_parts.append(f'---')
    md_parts.append('')
    
    # Content
    md_parts.extend(content_lines)
    md_parts.append('')  # trailing newline
    
    return '\n'.join(md_parts)


def convert_folder(folder: Path, section: str, dry_run: bool = False):
    """Convert all .txt files in a folder to .md"""
    txt_files = sorted(folder.glob('*.txt'))
    
    if not txt_files:
        print(f"  [SKIP] No .txt files in {folder}")
        return 0
    
    converted = 0
    for txt_file in txt_files:
        md_file = txt_file.with_suffix('.md')
        title = txt_file.stem
        
        # Remove sequence prefix for title (e.g., "01_सरस्वती-वंदना" -> "सरस्वती-वंदना")
        display_title = re.sub(r'^\d+_', '', title)
        
        # Read content
        content = txt_file.read_text(encoding='utf-8')
        
        # Clean and format
        md_content = clean_content(content, display_title, section)
        
        if dry_run:
            print(f"  [DRY] {txt_file.name} -> {md_file.name} ({len(md_content)} chars)")
        else:
            # Write .md file
            md_file.write_text(md_content, encoding='utf-8')
            
            # Remove old .txt file
            txt_file.unlink()
            
            print(f"  [OK] {txt_file.name} -> {md_file.name} ({len(md_content)} chars)")
        
        converted += 1
    
    return converted


def main():
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("=== DRY RUN MODE (no files will be changed) ===\n")
    
    print("=" * 60)
    print("  TXT → MD CONVERTER")
    print(f"  Book: {BOOK_NAME}")
    print("=" * 60)
    
    total = 0
    
    for section in ["Source", "Preface", "Poems", "Postface"]:
        folder = BOOK_ROOT / section
        if not folder.exists():
            print(f"\n[SKIP] {folder} does not exist")
            continue
        
        print(f"\n--- {section} ---")
        count = convert_folder(folder, section, dry_run)
        total += count
    
    print(f"\n{'=' * 60}")
    print(f"  CONVERSION COMPLETE: {total} files converted")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
