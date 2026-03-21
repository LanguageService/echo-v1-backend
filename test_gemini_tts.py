import os
import django
from google import genai
from google.genai import types

# Setup django to get settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

def test_tts(model_id, text="Hello, this is a test."):
    if not model_id.startswith("models/"):
        model_id = f"models/{model_id}"
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    print(f"Testing TTS with model: {model_id}")
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Aoede"
                        )
                    )
                )
            )
        )
        print(f"Success with {model_id}!")
        return True
    except Exception as e:
        print(f"Error with {model_id}: {e}")
        return False

if __name__ == "__main__":
    test_tts("gemini-2.5-flash-preview-tts", text="Please synthesize the following text into audio, no text response: This is a test.")
