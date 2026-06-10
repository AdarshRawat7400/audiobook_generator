#!/bin/bash
set -e
echo "======================================"
echo " Gemini Audiobook Generator Setup "
echo "======================================"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "❌ PLEASE EDIT the .env file and add your GEMINI_API_KEY before running again."
    exit 1
fi
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
python main.py "$@"
echo "✅ Execution completed!"