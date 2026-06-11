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
    args = parser.parse_args()

    # Ensure modules are importable from this directory
    sys.path.insert(0, str(Path(__file__).parent))

    from modules.downloader import download_video
    from modules.transcriber import transcribe_audio
    from modules.analyzer import analyze_excitement
    from modules.clipper import extract_clips
    from modules.captioner import add_captions

    print("\nYouTube Shorts Automation")
    print(f"URL: {args.url}")
    print(f"Generating {args.clips} shorts\n")

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

    print(f"\nDone! {len(final_clips)} shorts saved to {args.output}/{video_id}/")
    for p in final_clips:
        try:
            size = os.path.getsize(p) / (1024 * 1024)
            print(f"   {os.path.basename(p)} ({size:.1f} MB)")
        except OSError:
            print(f"   {os.path.basename(p)}")


if __name__ == "__main__":
    main()
