import json
from pathlib import Path


def transcribe_audio(audio_path: str, video_id: str, output_base: str = "./output") -> list:
    """
    Transcribe audio using faster-whisper with word-level timestamps.

    Returns list of segments: [{"start", "end", "text", "words": [{"word", "start", "end"}]}]
    """
    transcript_path = Path(output_base) / video_id / "transcript.json"

    # Return cached transcript if it exists
    if transcript_path.exists():
        with open(transcript_path, "r", encoding="utf-8") as f:
            return json.load(f)

    from faster_whisper import WhisperModel

    model = WhisperModel("base.en", device="cpu", compute_type="int8")

    raw_segments, _ = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
    )

    segments = []
    for seg in raw_segments:
        words = []
        if seg.words:
            for w in seg.words:
                words.append({
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                })
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
        })

    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    return segments
