# Setup Instructions (Windows)

## Prerequisites

### 1. Install Python 3.11+
Download from https://www.python.org/downloads/
- During install: check "Add Python to PATH"
- Verify: `python --version`

### 2. Install ffmpeg
Download a Windows build from https://www.gyan.dev/ffmpeg/builds/
- Download "ffmpeg-release-essentials.zip"
- Extract, e.g. to C:\ffmpeg\
- Add C:\ffmpeg\bin to your system PATH
- Verify: `ffmpeg -version`

### 3. Install Ollama
Download from https://ollama.com/download
- Run the installer
- Pull the model: `ollama pull llama3.2:3b`
- Verify it's running: `curl http://localhost:11434/api/tags`

---

## Project Setup

```powershell
cd C:\Users\biopro\youtube_shorts

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Run

```powershell
# Activate venv first if not already active
.\venv\Scripts\activate

# Run with a YouTube URL
python main.py --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --clips 3

# Keep intermediate files for debugging
python main.py --url "https://..." --clips 2 --keep-temp
```

## Output

Results are saved to `output/<video_id>/`:
- `short_1.mp4`, `short_2.mp4`, etc. — final vertical shorts with captions
- `transcript.json` — full transcript with word timestamps
- `analysis.json` — Ollama's clip selections with scores

## Notes

- First transcription run downloads the Whisper `base.en` model (~150 MB).
- CPU transcription takes roughly 1× real-time (5-min video ≈ 5 min to transcribe).
- FFmpeg re-encoding takes ~2–3 min per clip on CPU.
- Ollama must be running (`ollama serve`) before you run the script.
