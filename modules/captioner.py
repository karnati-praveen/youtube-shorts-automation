import subprocess
import os
from pathlib import Path


def _filter_words(segments: list, clip_start: float, clip_end: float) -> list:
    """
    Return word entries that fall within [clip_start, clip_end],
    with timestamps re-zeroed to clip-relative time.
    """
    words = []
    for seg in segments:
        for w in seg.get("words", []):
            ws = w["start"]
            we = w["end"]
            if we < clip_start or ws > clip_end:
                continue
            words.append({
                "word": w["word"].strip(),
                "start": round(ws - clip_start, 3),
                "end": round(we - clip_start, 3),
            })
    return words


def _seconds_to_ass_time(s: float) -> str:
    """Convert float seconds to ASS timestamp format H:MM:SS.cs"""
    s = max(0.0, s)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    cs = int((sec % 1) * 100)
    return f"{h}:{m:02d}:{int(sec):02d}.{cs:02d}"


def _write_ass(words: list, ass_path: str, font: str = "Arial", font_size: int = 20) -> None:
    """
    Write an ASS subtitle file with word-by-word highlighting.

    Current word = bold + yellow; surrounding words in the same segment = white.
    Each word gets its own timed event so highlighting advances word-by-word.
    """
    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Group words into display lines of ~6 words for readability
    LINE_SIZE = 4
    lines_of_words = [words[i:i + LINE_SIZE] for i in range(0, max(1, len(words)), LINE_SIZE)]

    events = []
    for line_words in lines_of_words:
        if not line_words:
            continue
        line_start = line_words[0]["start"]
        line_end = line_words[-1]["end"]

        # For each word in the line, emit one event where that word is highlighted
        for wi, active_word in enumerate(line_words):
            ev_start = active_word["start"]
            ev_end = active_word["end"]
            if ev_end <= ev_start:
                ev_end = ev_start + 0.1

            parts = []
            for j, w in enumerate(line_words):
                text = w["word"].replace("\\", "\\\\").replace("{", "\\{")
                if j == wi:
                    # Bold yellow highlight for the current word
                    parts.append(r"{\b1\c&H00FFFF&}" + text + r"{\r}")
                else:
                    parts.append(r"{\b0\c&H00FFFFFF&}" + text + r"{\r}")

            dialogue_text = " ".join(parts)
            events.append(
                f"Dialogue: 0,{_seconds_to_ass_time(ev_start)},{_seconds_to_ass_time(ev_end)},"
                f"Default,,0,0,0,,{dialogue_text}"
            )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")


def add_captions(
    raw_clip_path: str,
    segments: list,
    clip_start: float,
    clip_index: int,
    video_id: str,
    output_base: str = "./output",
    keep_temp: bool = False,
) -> str:
    """
    Burn word-highlighted ASS captions into a clip.

    Returns path to the final short mp4.
    """
    from config import CAPTION_FONT, CAPTION_FONT_SIZE

    out_dir = Path(output_base) / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine clip end from the raw clip's actual duration
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        raw_clip_path,
    ]
    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        clip_duration = float(probe_result.stdout.strip())
    except Exception:
        clip_duration = 90.0  # fallback

    clip_end = clip_start + clip_duration
    words = _filter_words(segments, clip_start, clip_end)

    ass_path = str(out_dir / f"clip_{clip_index}_captions.ass")
    out_path = str(out_dir / f"short_{clip_index}.mp4")

    _write_ass(words, ass_path, font=CAPTION_FONT, font_size=CAPTION_FONT_SIZE)

    # On Windows, backslashes in the ASS path must be escaped for ffmpeg's -vf
    escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", raw_clip_path,
        "-vf", f"ass={escaped_ass}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Caption burn failed for clip {clip_index}: {e.stderr.strip()}")

    if not keep_temp:
        try:
            os.remove(ass_path)
        except OSError:
            pass

    return out_path
