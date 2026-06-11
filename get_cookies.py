"""
Extract YouTube/Google cookies from Edge using rookiepy (supports v20 App-Bound Encryption).
Saves cookies.txt in Netscape format for use with yt-dlp.
"""
import sys
from pathlib import Path

try:
    import rookiepy
except ImportError:
    raise SystemExit("Missing dependency. Run: pip install rookiepy")

OUTPUT = Path(__file__).parent / "cookies.txt"
TARGET_DOMAINS = ["youtube.com", "google.com"]


def main():
    print("Extracting Edge cookies via rookiepy (v20 App-Bound Encryption supported)...")
    try:
        cookies = rookiepy.edge(TARGET_DOMAINS)
    except Exception as e:
        raise SystemExit(f"Failed to extract cookies: {e}")

    if not cookies:
        raise SystemExit(
            "No YouTube/Google cookies found.\n"
            "Make sure you are logged into youtube.com in Edge, then re-run."
        )

    print(f"Got {len(cookies)} cookies")

    lines = ["# Netscape HTTP Cookie File", "# Exported by get_cookies.py", ""]
    for c in cookies:
        host     = c.get("host", c.get("domain", ""))
        path     = c.get("path", "/")
        secure   = c.get("secure", False)
        expires  = int(c.get("expires", 0) or 0)
        name     = c.get("name", "")
        value    = c.get("value", "")

        if not name or not value:
            continue

        include_subs = "TRUE" if host.startswith(".") else "FALSE"
        secure_str   = "TRUE" if secure else "FALSE"
        lines.append(f"{host}\t{include_subs}\t{path}\t{secure_str}\t{expires}\t{name}\t{value}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    count = len(lines) - 3  # subtract header lines
    print(f"Saved {count} cookies to: {OUTPUT}")
    if count > 0:
        print("Ready! Run: python main.py --url <URL> --clips 2")
    else:
        print("WARNING: No valid cookies written.")


if __name__ == "__main__":
    main()
