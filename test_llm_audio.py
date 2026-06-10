import os
import wave
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Test if an LLM can use system_instruction and AUDIO modality
model = "gemini-3.5-flash"
voice_name = "Algieba"
text = "Testing audio generation with system instructions."

system_instruction = (
    "You are a professional Indian literary narrator. "
    "Your ONLY task is to read the provided text EXACTLY as written. "
    "Do NOT summarize, explain, add greetings, or skip any content. "
    "Read it warmly, clearly, and with dignity."
)

try:
    response = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            )
        )
    )
    print("Success! Audio generated.")
except Exception as e:
    print("Error:", e)
