import subprocess
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import requests

_COOKIES_FILE = Path(__file__).parent.parent / "cookies.txt"

# Public Cobalt instances to try in order (official requires JWT auth)
_COBALT_INSTANCES = [
    "https://cobalt.api.timelessnesses.me/",
    "https://api.cobalt.tools/",
]
_COBALT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "youtube-shorts-bot/1.0",
}


# ---------------------------------------------------------------------------
# yt-dlp helpers
# ---------------------------------------------------------------------------

def _yt_dlp_exe() -> str:
    for candidate in [
        Path(sys.executable).parent / "yt-dlp.exe",
        Path(sys.executable).parent / "yt-dlp",
    ]:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("yt-dlp")
    if found:
        return found
    raise RuntimeError("yt-dlp not found.")


def _node_exe() -> str | None:
    for d in [r"C:\Program Files\nodejs", r"C:\Program Files (x86)\nodejs"]:
        p = Path(d) / "node.exe"
        if p.exists():
            return str(p)
    return shutil.which("node")


def _ytdlp_base_cmd() -> list:
    """Build base yt-dlp command with Node.js and EJS challenge solver."""
    cmd = [_yt_dlp_exe()]
    node = _node_exe()
    if node:
        cmd += ["--js-runtimes", f"node:{node}"]
    # EJS: download challenge solver scripts from GitHub (cached locally after first run)
    cmd += ["--remote-components", "ejs:github"]
    if _COOKIES_FILE.exists():
        cmd += ["--cookies", str(_COOKIES_FILE)]
    return cmd


def _ytdlp_cmd(client: str = None) -> list:
    cmd = _ytdlp_base_cmd()
    if client:
        cmd += ["--extractor-args", f"youtube:player_client={client}"]
    return cmd


def _ytdlp_run(extra: list, client: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(_ytdlp_cmd(client) + extra, capture_output=True, text=True)


def _ytdlp_probe(url: str) -> dict | None:
    """Try yt-dlp probe. With cookies, web client is used; without, tries mobile clients."""
    args = ["--dump-json", "--no-playlist", url]
    clients = ("web", None) if _COOKIES_FILE.exists() else ("ios", "android", "web", None)
    for client in clients:
        r = _ytdlp_run(args, client=client)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                continue
    return None


def _ytdlp_download(url: str, out: Path) -> bool:
    """Try yt-dlp download. With cookies, web client is used; without, tries mobile clients."""
    args = [
        "--no-playlist",
        "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", str(out),
        url,
    ]
    clients = ("web", None) if _COOKIES_FILE.exists() else ("ios", "android", "web", None)
    for client in clients:
        r = _ytdlp_run(args, client=client)
        if r.returncode == 0 and out.exists():
            return True
    return False


# ---------------------------------------------------------------------------
# pytubefix helpers
# ---------------------------------------------------------------------------

def _pytubefix_probe(url: str) -> dict | None:
    """Get metadata via pytubefix. Returns partial meta dict or None."""
    try:
        from pytubefix import YouTube
        yt = YouTube(url)
        return {
            "id": yt.video_id,
            "title": yt.title,
            "duration": yt.length or 0,
        }
    except Exception:
        return None


def _pytubefix_download(url: str, out: Path) -> bool:
    """Download via pytubefix. Returns True on success."""
    try:
        from pytubefix import YouTube
        yt = YouTube(url)
        # Try progressive (merged) stream first, then adaptive
        stream = (
            yt.streams.filter(progressive=True, file_extension="mp4")
              .order_by("resolution").desc().first()
            or
            yt.streams.filter(file_extension="mp4", only_video=False)
              .order_by("resolution").desc().first()
        )
        if not stream:
            return False
        out.parent.mkdir(parents=True, exist_ok=True)
        stream.download(output_path=str(out.parent), filename=out.name)
        return out.exists()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cobalt helpers
# ---------------------------------------------------------------------------

def _oembed_meta(url: str) -> dict:
    """Get title via YouTube oEmbed (always public, no auth). Duration = 0."""
    vid_match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', url)
    video_id = vid_match.group(1) if vid_match else "unknown"
    try:
        r = requests.get(
            f"https://www.youtube.com/oembed?url={url}&format=json", timeout=10
        )
        title = r.json().get("title", "Untitled") if r.ok else "Untitled"
    except Exception:
        title = "Untitled"
    return {"id": video_id, "title": title, "duration": 0}


def _cobalt_download(url: str, out: Path) -> bool:
    """
    Try each public Cobalt instance. Handles redirect/tunnel and picker responses.
    Returns True on success.
    """
    payload = {"url": url, "videoQuality": "1080", "youtubeVideoCodec": "h264"}

    for instance in _COBALT_INSTANCES:
        try:
            resp = requests.post(
                instance, json=payload, headers=_COBALT_HEADERS,
                timeout=30, verify=False,  # some instances use self-signed certs
            )
            if not resp.ok:
                continue
            data = resp.json()
        except Exception:
            continue

        status = data.get("status")

        if status in ("redirect", "tunnel"):
            try:
                _stream_to_file(data["url"], out)
                return True
            except Exception:
                continue

        if status == "picker":
            try:
                video_streams = [p for p in data.get("picker", []) if p.get("type") == "video"]
                audio_url = data.get("audio")
                if not video_streams:
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    tv = Path(tmp) / "v.mp4"
                    ta = Path(tmp) / "a.m4a"
                    _stream_to_file(video_streams[0]["url"], tv)
                    if audio_url:
                        _stream_to_file(audio_url, ta)
                        _merge(tv, ta, out)
                    else:
                        shutil.copy2(tv, out)
                return True
            except Exception:
                continue

    return False


def _stream_to_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120, verify=False) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)


def _merge(video: Path, audio: Path, out: Path) -> None:
    r = subprocess.run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", str(out),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg merge failed: {r.stderr.strip()}")


def _ffprobe_duration(path: Path) -> float:
    r = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_video(url: str, output_base: str = "./output") -> tuple:
    """
    Download a YouTube video and extract audio for transcription.

    Download strategy (tries each in order until one succeeds):
      1. yt-dlp with iOS/Android/Web player clients
      2. pytubefix (different YouTube API path)
      3. Cobalt API (external proxy — bypasses IP blocks)

    Returns: (video_path, audio_path, video_id, title, duration_seconds)
    """
    # --- probe metadata ---
    meta = _ytdlp_probe(url) or _pytubefix_probe(url) or _oembed_meta(url)

    video_id = meta.get("id", "unknown")
    title    = meta.get("title", "Untitled")
    duration = float(meta.get("duration") or 0)

    out_dir = Path(output_base) / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / "video.mp4"
    audio_path = out_dir / "audio.wav"

    # --- download video ---
    if not video_path.exists():
        if _ytdlp_download(url, video_path):
            print("   (downloaded via yt-dlp)")
        elif _pytubefix_download(url, video_path):
            print("   (downloaded via pytubefix)")
        elif _cobalt_download(url, video_path):
            print("   (downloaded via Cobalt)")
        else:
            raise RuntimeError(
                "All download methods failed for this video.\n"
                "This video likely requires a YouTube login (age-restricted or member-only).\n"
                "Try a different public YouTube video."
            )

    if not video_path.exists():
        raise RuntimeError("Download reported success but output file is missing.")

    if duration == 0:
        duration = _ffprobe_duration(video_path)

    # --- extract audio for Whisper ---
    if not audio_path.exists():
        r = subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path),
        ], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"Audio extraction failed: {r.stderr.strip()}")

    return str(video_path), str(audio_path), video_id, title, duration
