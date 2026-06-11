"""
One-time setup to authorize this app to upload to your YouTube channel.

Steps:
  1. Go to https://console.cloud.google.com/
  2. Create a new project (or select an existing one)
  3. Go to "APIs & Services" > "Library"
     Search for and ENABLE "YouTube Data API v3"
  4. Go to "APIs & Services" > "Credentials"
     Click "Create Credentials" > "OAuth client ID"
     Application type: Desktop app
     Name it anything (e.g. "YouTube Shorts Bot")
     Click CREATE, then "Download JSON"
  5. Rename the downloaded file to client_secret.json
     and place it in this folder:
       C:\\Users\\biopro\\youtube_shorts\\client_secret.json
  6. Run this script:  python youtube_setup.py
     A browser window opens — sign in with the YouTube account you want to post to.
     This saves token.json locally (never shared, never committed to git).
     Future uploads reuse this token silently.

After setup, run:
  python main.py --url <URL> --clips 2 --upload
  python main.py --url <URL> --clips 2 --upload --privacy public
"""
import sys
from pathlib import Path

CLIENT_SECRETS = Path(__file__).parent / "client_secret.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

print("YouTube Upload Setup")
print("=" * 50)

if not CLIENT_SECRETS.exists():
    print("\nclient_secret.json not found.")
    print("\nSetup steps:")
    print("  1. https://console.cloud.google.com/")
    print("  2. Enable: YouTube Data API v3")
    print("  3. Create OAuth2 credentials (Desktop app)")
    print("  4. Download JSON → rename to client_secret.json")
    print(f"  5. Place it at: {CLIENT_SECRETS}")
    print("  6. Re-run this script")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("\nMissing libraries. Run:")
    print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

print("\nOpening browser for authorization...")
print("Sign in with the YouTube account you want to upload to.\n")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print(f"\nSetup complete! Token saved to: {TOKEN_FILE}")
print("\nUsage:")
print("  python main.py --url <URL> --clips 2 --upload")
print("  python main.py --url <URL> --clips 2 --upload --privacy public")
print("  python main.py --url <URL> --clips 2 --upload --privacy unlisted")
