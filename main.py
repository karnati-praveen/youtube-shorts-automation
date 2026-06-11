#!/usr/bin/env python3
"""
YouTube Shorts Automation
Usage: python main.py --url URL [--clips N] [--output DIR] [--keep-temp]
"""
import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Convert YouTube videos to viral shorts")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--clips", type=int, default=3, help="Number of shorts to generate")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--keep-temp", action="store_true", help="Keep intermediate files for debugging")
    parser.add_argument("--upload", action="store_true", help="Upload finished shorts to YouTube")
    parser.add_argument(
        "--privacy",
        choices=["public", "private", "unlisted"],
        default=None,
        help="YouTube privacy for uploaded shorts (default from config: UPLOAD_PRIVACY)",
    )
    args = parser.parse_args()

    # Ensure modules are importable from this directory
    sys.path.insert(0, str(Path(__file__).parent))

    from modules.downloader import download_video
    from modules.transcriber import transcribe_audio
    from modules.analyzer import analyze_excitement
    from modules.clipper import extract_clips
    from modules.captioner import add_captions
    from modules.uploader import upload_short, is_configured as upload_configured

    from config import UPLOAD_PRIVACY

    if args.upload and not upload_configured():
        print("YouTube upload not configured. Run: python youtube_setup.py")
        sys.exit(1)

    privacy = args.privacy or UPLOAD_PRIVACY

    print("\nYouTube Shorts Automation")
    print(f"URL: {args.url}")
    print(f"Generating {args.clips} shorts", end="")
    if args.upload:
        print(f" (will upload as {privacy})", end="")
    print("\n")

    # Step 1: Download
    print("[1/5] Downloading video...")
    video_path, audio_path, video_id, title, duration = download_video(args.url, args.output)
    print(f"   OK '{title}' ({duration:.0f}s)")

    # Step 2: Transcribe
    print("[2/5] Transcribing audio (CPU — may take a few minutes)...")
    segments = transcribe_audio(audio_path, video_id, args.output)
    word_count = sum(len(s.get("words", [])) for s in segments)
    print(f"   OK {len(segments)} segments, ~{word_count} words")

    # Step 3: Analyze
    print("[3/5] Analyzing excitement with Ollama (llama3.2:3b)...")
    clip_windows = analyze_excitement(segments, duration, args.clips, video_id, args.output)
    print(f"   OK Found {len(clip_windows)} exciting moments")
    for i, w in enumerate(clip_windows):
        print(f"      [{i + 1}] {w['start_time']:.0f}s-{w['end_time']:.0f}s | score {w['score']}/10 | {w['reason']}")

    # Step 4: Cut clips
    print("[4/5] Extracting and cropping clips (9:16)...")
    raw_clips = extract_clips(video_path, clip_windows, video_id, args.output)
    print(f"   OK {len(raw_clips)} clips extracted")

    # Step 5: Add captions
    print("[5/5] Burning captions...")
    final_clips = []
    for i, (clip_path, window) in enumerate(zip(raw_clips, clip_windows)):
        clip_segments = [
            s for s in segments
            if s["end"] >= window["start_time"] and s["start"] <= window["end_time"]
        ]
        out = add_captions(
            clip_path,
            clip_segments,
            window["start_time"],
            i + 1,
            video_id,
            args.output,
            keep_temp=args.keep_temp,
        )
        final_clips.append(out)
        print(f"   OK short_{i + 1}.mp4")

    # Cleanup raw clips unless --keep-temp
    if not args.keep_temp:
        clips_dir = Path(args.output) / video_id / "clips"
        for clip_path in raw_clips:
            try:
                os.remove(clip_path)
            except OSError:
                pass
        try:
            clips_dir.rmdir()
        except OSError:
            pass

    # Step 6: Upload to YouTube (optional)
    uploaded_urls = []
    if args.upload:
        total_steps = 6
        print(f"[6/{total_steps}] Uploading to YouTube ({privacy})...")
        for i, (clip_path, window) in enumerate(zip(final_clips, clip_windows)):
            # Use AI-generated hook as title; fall back to source title
            hook = (window.get("hook") or "").strip()
            short_title = (hook or f"{title} — Short #{i + 1}")[:100]
            short_desc = window.get("reason", "").strip()

            try:
                vid_id = upload_short(
                    clip_path,
                    title=short_title,
                    description=short_desc,
                    privacy=privacy,
                    tags=[w for w in title.split() if len(w) > 3],
                )
                url = f"https://www.youtube.com/shorts/{vid_id}"
                uploaded_urls.append(url)
                print(f"   [{i + 1}] {url}")
            except Exception as e:
                print(f"   [{i + 1}] Upload failed: {e}")

    steps_done = 6 if args.upload else 5
    print(f"\nDone! {len(final_clips)} shorts saved to {args.output}/{video_id}/")
    for p in final_clips:
        try:
            size = os.path.getsize(p) / (1024 * 1024)
            print(f"   {os.path.basename(p)} ({size:.1f} MB)")
        except OSError:
            print(f"   {os.path.basename(p)}")

    if uploaded_urls:
        print(f"\nUploaded {len(uploaded_urls)} short(s) to YouTube:")
        for url in uploaded_urls:
            print(f"   {url}")


if __name__ == "__main__":
    main()
