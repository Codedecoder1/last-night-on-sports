"""Voice test: turns a short two-host dialogue into a WAV with Gemini TTS."""
import base64, json, os, sys, urllib.request, wave

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.8-flash-tts"
OUT = sys.argv[2] if len(sys.argv) > 2 else "voice_test.wav"

# Read keys from .env
for line in open(os.path.join(os.path.dirname(__file__), ".env")):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

DIALOGUE = """Read this as a relaxed, upbeat morning sports show between two friends in New York. Natural, warm, with real reactions and light laughs.

Marcus: Good morning, New York! It's Marcus...
Elena: ...and Elena. And Marcus, I have to say, you look like someone who did NOT sleep last night.
Marcus: Elena, I stayed up for that whole game. All four quarters. Every single timeout.
Elena: (laughs) Of course you did. Was it worth it?
Marcus: Honestly? Worth every minute. That last shot, I literally jumped off my couch.
Elena: My kids heard you from Brooklyn, I'm pretty sure.
Marcus: (laughs) Okay, okay. Let's get into it. Here's everything you missed yesterday in sports."""

body = {
    "contents": [{"parts": [{"text": DIALOGUE}]}],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
            {"speaker": "Marcus", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Puck"}}},
            {"speaker": "Elena", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
        ]}},
    },
}
req = urllib.request.Request(
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
)
try:
    resp = json.load(urllib.request.urlopen(req, timeout=180))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode()[:500]}")

pcm = base64.b64decode(resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
with wave.open(OUT, "wb") as w:  # Gemini returns 24 kHz, 16-bit mono PCM
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
print(f"Saved {OUT} ({len(pcm) / 48000:.1f} seconds) using {MODEL}")
