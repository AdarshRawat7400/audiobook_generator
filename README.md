# Gemini Audiobook Generator

A fully automated Python tool to generate an audiobook from a ZIP file of Hindi TXT files using Google's Gemini models. Produces male and female narrations plus educational explainer audio for each poem.

## Features
- 🎧 Male & female narration in natural voices (Algieba / Aoede)
- 📝 AI-generated educational explainers for each poem
- 🔄 Smart retry with rate-limit awareness (parses 429 retryDelay)
- ✅ Resume support — skips already-generated audio files
- 📊 Processing summary with success/fail/skip counts and API usage stats
- 🔍 Dry-run mode to validate input without making API calls

## Setup
1. Install Python 3.10+
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your Gemini API Key.
4. Place your ZIP file in the root directory (default expects `input.zip`).

## Usage (Windows)
Double-click `run.bat`

## Usage (Linux/Mac)
Run: `./run.sh`

## Command Line Options
```bash
python main.py                        # Process input.zip
python main.py --zip mybook.zip       # Process a specific ZIP file
python main.py --dry-run              # Validate ZIP contents without API calls
python main.py --dry-run --zip x.zip  # Combine flags
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Google AI Studio API key |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash` | Model for explainer text generation |
| `GEMINI_AUDIO_MODEL` | `gemini-3.5-flash` | Model for audio narration |
| `API_CALL_DELAY` | `1` | Seconds to wait between API calls |
| `MAX_RETRIES_TEXT` | `5` | Max retry attempts for text generation |
| `MAX_RETRIES_AUDIO` | `5` | Max retry attempts for audio generation |
| `RETRY_MAX_WAIT` | `120` | Max seconds between retries |
| `MAX_WORKERS` | `2` | Concurrent processing workers |

## Output Structure
```
output/
├── audio/
│   ├── male/              # Male narration WAV files
│   ├── female/            # Female narration WAV files
│   ├── male_explainer/    # Male explainer WAV files
│   └── female_explainer/  # Female explainer WAV files
├── explainer_texts/       # Generated explainer text files (for review)
├── manifests/
│   └── manifest.json      # Processing manifest
├── logs/
│   └── generation.log     # Detailed generation log
└── temp_txt/              # Extracted text files from ZIP
```

## Diagnostics
Run the model diagnostics script to check which models are available:
```bash
python test_quotas.py
```

## Troubleshooting

### 429 Rate Limit Errors
If you're on the free tier, the daily quota is very limited (~20 requests/day for `gemini-3.5-flash`). Options:
- Increase `API_CALL_DELAY` to slow down requests
- Use a paid plan for higher throughput
- Set `MAX_WORKERS=1` for sequential processing

### Empty Audio / AttributeError
Some models occasionally return empty audio responses. The enhanced client automatically retries these. If persistent, try a different audio model:
```bash
set GEMINI_AUDIO_MODEL=gemini-3.1-flash-tts-preview
```
