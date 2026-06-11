import subprocess
import json
from pathlib import Path


def _probe_dimensions(video_path: str) -> tuple:
    """Return (width, height) of the video using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    raise RuntimeError(f"No video stream found in {video_path}")


def _build_crop_filter(src_w: int, src_h: int, target_w: int = 1080, target_h: int = 1920) -> str:
    """
    Return an ffmpeg -vf filter string that crops/scales to target_w x target_h (9:16).

    Landscape source: center-crop to 9:16 aspect ratio first, then scale.
    Portrait source: just scale.
    """
    target_ratio = target_w / target_h  # 9/16 = 0.5625
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Landscape: crop width, keep full height
        crop_w = int(src_h * target_ratio)
        crop_h = src_h
        x_offset = (src_w - crop_w) // 2
        y_offset = 0
        return f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset},scale={target_w}:{target_h}"
    else:
        # Portrait or square: crop height if needed, scale
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
        if crop_h > src_h:
            # Source is narrower than 9:16 — pillarbox isn't ideal; scale with pad instead
            return (
                f"scale={target_w}:-2,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
            )
        y_offset = (src_h - crop_h) // 2
        return f"crop={crop_w}:{crop_h}:0:{y_offset},scale={target_w}:{target_h}"


def extract_clips(
    video_path: str,
    clip_windows: list,
    video_id: str,
    output_base: str = "./output",
) -> list:
    """
    Cut and reformat clip windows from the source video to 9:16 vertical format.

    Returns list of output clip paths.
    """
    out_dir = Path(output_base) / video_id / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)

    src_w, src_h = _probe_dimensions(video_path)
    vf = _build_crop_filter(src_w, src_h)

    raw_clips = []
    for i, window in enumerate(clip_windows):
        start = window["start_time"]
        end = window["end_time"]
        duration = end - start
        out_path = out_dir / f"clip_{i + 1}_raw.mp4"

        if out_path.exists():
            raw_clips.append(str(out_path))
            continue

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg clip extraction failed for clip {i + 1}: {e.stderr.strip()}")

        raw_clips.append(str(out_path))

    return raw_clips
