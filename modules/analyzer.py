import json
import re
from pathlib import Path


_CHUNK_SECONDS = 180   # ~3-minute chunks
_OVERLAP_SECONDS = 30  # overlap so clips near boundaries aren't missed


def _build_chunks(segments: list, total_duration: float) -> list:
    """Split segments into overlapping ~3-minute text windows with timestamps."""
    chunks = []
    chunk_start = 0.0

    while chunk_start < total_duration:
        chunk_end = chunk_start + _CHUNK_SECONDS
        chunk_segs = [s for s in segments if s["end"] >= chunk_start and s["start"] < chunk_end]
        if not chunk_segs:
            chunk_start += _CHUNK_SECONDS - _OVERLAP_SECONDS
            continue

        lines = [f"[{s['start']:.1f}s] {s['text']}" for s in chunk_segs]
        chunks.append({
            "text": "\n".join(lines),
            "start": chunk_start,
            "end": min(chunk_end, total_duration),
        })
        chunk_start += _CHUNK_SECONDS - _OVERLAP_SECONDS

    return chunks


def _query_ollama(chunk_text: str, model: str) -> list:
    """Send chunk to Ollama and return parsed clip windows. Retries once on bad JSON."""
    import ollama

    system_prompt = (
        "You are a viral content analyst. Identify the most exciting, engaging, "
        "or share-worthy moments in this transcript for social media shorts."
    )
    user_prompt = (
        f"Transcript chunk (timestamps in seconds):\n{chunk_text}\n\n"
        "Identify up to 3 windows of 30–90 seconds that would make great standalone "
        "short-form videos. Look for:\n"
        "- Emotional peaks or reactions\n"
        "- Surprising reveals or twists\n"
        "- Punchy arguments or quotable lines\n"
        "- Tension → payoff moments\n"
        "- High-energy or excited speech\n\n"
        "Return ONLY valid JSON array, no explanation:\n"
        "[\n"
        "  {\n"
        '    "start_time": <float>,\n'
        '    "end_time": <float>,\n'
        '    "score": <1-10>,\n'
        '    "reason": "<one sentence>",\n'
        '    "hook": "<opening line that makes viewer stay>"\n'
        "  }\n"
        "]"
    )

    for attempt in range(2):
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response["message"]["content"].strip()

            # Extract JSON array from response (model sometimes adds prose)
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except (json.JSONDecodeError, KeyError, Exception):
            if attempt == 1:
                break
            continue

    return []


def _overlaps(a: dict, b: dict) -> bool:
    return a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]


def _deduplicate(windows: list) -> list:
    """Keep highest-scored window when two overlap."""
    windows = sorted(windows, key=lambda w: w["score"], reverse=True)
    kept = []
    for w in windows:
        if not any(_overlaps(w, k) for k in kept):
            kept.append(w)
    return kept


def _fallback_clips(total_duration: float, n: int, min_dur: int, max_dur: int) -> list:
    """Evenly-spaced fallback clips when Ollama returns nothing usable."""
    clip_dur = min(max_dur, max(min_dur, int(total_duration / max(n, 1))))
    clips = []
    step = total_duration / (n + 1)
    for i in range(1, n + 1):
        start = round(step * i - clip_dur / 2, 1)
        start = max(0.0, min(start, total_duration - clip_dur))
        clips.append({
            "start_time": start,
            "end_time": round(start + clip_dur, 1),
            "score": 5,
            "reason": "Evenly-spaced fallback clip.",
            "hook": "",
        })
    return clips


def analyze_excitement(
    segments: list,
    total_duration: float,
    n_clips: int,
    video_id: str,
    output_base: str = "./output",
) -> list:
    """
    Analyze transcript with Ollama and return top n_clips non-overlapping windows.

    Returns: [{"start_time", "end_time", "score", "reason", "hook"}]
    """
    from config import OLLAMA_MODEL, MIN_CLIP_DURATION, MAX_CLIP_DURATION

    analysis_path = Path(output_base) / video_id / "analysis.json"
    if analysis_path.exists():
        with open(analysis_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        return cached[:n_clips]

    chunks = _build_chunks(segments, total_duration)
    all_windows = []

    for chunk in chunks:
        windows = _query_ollama(chunk["text"], OLLAMA_MODEL)
        for w in windows:
            # Clamp and validate
            try:
                start = max(0.0, float(w["start_time"]))
                end = min(total_duration, float(w["end_time"]))
                dur = end - start
                if dur < MIN_CLIP_DURATION or dur > MAX_CLIP_DURATION:
                    # Clamp duration to valid range
                    mid = (start + end) / 2
                    half = max(MIN_CLIP_DURATION, min(dur, MAX_CLIP_DURATION)) / 2
                    start = max(0.0, mid - half)
                    end = min(total_duration, mid + half)
                w["start_time"] = round(start, 2)
                w["end_time"] = round(end, 2)
                w["score"] = max(1, min(10, int(w.get("score", 5))))
                all_windows.append(w)
            except (KeyError, TypeError, ValueError):
                continue

    all_windows = _deduplicate(all_windows)
    all_windows = sorted(all_windows, key=lambda w: w["score"], reverse=True)

    if not all_windows:
        print("   ⚠ Ollama returned no usable clips — using evenly-spaced fallback.")
        all_windows = _fallback_clips(total_duration, n_clips, MIN_CLIP_DURATION, MAX_CLIP_DURATION)

    result = all_windows[:n_clips]

    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
