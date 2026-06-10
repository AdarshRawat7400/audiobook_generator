"""
Text preprocessor for cleaning Markdown/formatting artifacts from extracted text files.
Ensures clean Hindi text is sent to the TTS and explainer models.
"""
import re
import logging

# The recurring book title footer pattern (with optional page number)
_BOOK_FOOTER_PATTERN = re.compile(
    r'^\s*\*?नदिया\s+तीर\s+कछारे\s+मेरा\s+गाँव\s+रे\s*(\[\d+\])?\s*\*?\s*$'
)

# Page number references like [1], [19], [43]
_PAGE_NUMBER_PATTERN = re.compile(r'\s*\[\d+\]\s*')

# Markdown horizontal rule
_HR_PATTERN = re.compile(r'^\s*---+\s*$')

# Markdown heading markers (## Title)
_HEADING_PATTERN = re.compile(r'^#{1,6}\s+')

# Markdown bold (**text**) — non-greedy
_BOLD_PATTERN = re.compile(r'\*\*(.+?)\*\*')

# Markdown italic (*text*) — non-greedy, but not bold
_ITALIC_PATTERN = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')

# Markdown line break (two trailing spaces)
_TRAILING_BREAK = re.compile(r'\s{2,}$')

# Markdown table rows (| col1 | col2 |)
_TABLE_PATTERN = re.compile(r'^\s*\|.*\|\s*$')

# Markdown table separator (| :--- | :---: |)
_TABLE_SEP_PATTERN = re.compile(r'^\s*\|[\s:_-]+\|\s*$')


def clean_text(raw_text: str) -> str:
    """Clean Markdown/formatting artifacts from text content.
    Returns plain Hindi text suitable for TTS narration."""
    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        # Remove book title footer lines
        if _BOOK_FOOTER_PATTERN.match(line):
            continue

        # Remove horizontal rules
        if _HR_PATTERN.match(line):
            continue

        # Remove Markdown table rows and separators
        if _TABLE_PATTERN.match(line) or _TABLE_SEP_PATTERN.match(line):
            continue

        # Strip heading markers (## Title -> Title)
        line = _HEADING_PATTERN.sub('', line)

        # Remove bold markers (**text** -> text)
        line = _BOLD_PATTERN.sub(r'\1', line)

        # Remove italic markers (*text* -> text)
        line = _ITALIC_PATTERN.sub(r'\1', line)

        # Remove page number references [NN]
        line = _PAGE_NUMBER_PATTERN.sub('', line)

        # Remove Markdown trailing line breaks (two spaces at end)
        line = _TRAILING_BREAK.sub('', line)

        # Strip trailing whitespace
        line = line.rstrip()

        cleaned_lines.append(line)

    # Join and collapse excessive blank lines (3+ -> 2)
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def preview_changes(raw_text: str) -> dict:
    """Show what would be cleaned — useful for debugging.
    Returns a dict with stats about the cleaning."""
    lines = raw_text.splitlines()
    cleaned = clean_text(raw_text)
    cleaned_lines = cleaned.splitlines()

    removed_lines = len(lines) - len(cleaned_lines)
    original_chars = len(raw_text)
    cleaned_chars = len(cleaned)

    return {
        "original_lines": len(lines),
        "cleaned_lines": len(cleaned_lines),
        "removed_lines": removed_lines,
        "original_chars": original_chars,
        "cleaned_chars": cleaned_chars,
        "chars_removed": original_chars - cleaned_chars,
        "reduction_pct": round((1 - cleaned_chars / original_chars) * 100, 1) if original_chars > 0 else 0,
    }
