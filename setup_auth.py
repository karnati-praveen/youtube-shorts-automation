"""
One-time YouTube OAuth2 authorization for yt-dlp.
Run once — token is cached and reused automatically by main.py.
"""
import subprocess
import sys
import shutil
from pathlib import Path

def main():
    yt_dlp = Path(sys.executable).parent / "yt-dlp.exe"
    if not yt_dlp.exists():
        yt_dlp = shutil.which("yt-dlp")

    node = Path(r"C:\Program Files\nodejs\node.exe")
    node_args = ["--js-runtimes", f"nodejs:{node}"] if node.exists() else []

    token_file = Path(__file__).parent / "oauth2_token.json"

    print("\nYouTube OAuth2 Setup")
    print("=" * 40)
    print("yt-dlp will show a URL and a short code.")
    print("Open that URL in any browser and enter the code to authorize.\n")

    cmd = (
        [str(yt_dlp)]
        + node_args
        + [
            "--username", "oauth2",
            "--password", "",
            "--dump-json",
            "--no-playlist",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # short public test video
        ]
    )

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\nAuthorization successful!")
        print("You can now run: python main.py --url <URL> --clips 2")
    else:
        print("\nAuthorization failed or was cancelled.")
        print("Try again by running: python setup_auth.py")

if __name__ == "__main__":
    main()
