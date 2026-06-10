import json
import threading
from pathlib import Path
import config

manifest_lock = threading.Lock()
manifest_path = config.MANIFEST_DIR / "manifest.json"

def init_manifest():
    if not manifest_path.exists():
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def update_manifest(entry: dict):
    with manifest_lock:
        data = []
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        
        updated = False
        for i, existing in enumerate(data):
            if existing.get("id") == entry["id"]:
                data[i] = entry
                updated = True
                break
        
        if not updated:
            data.append(entry)
            
        data = sorted(data, key=lambda x: x["id"])

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)