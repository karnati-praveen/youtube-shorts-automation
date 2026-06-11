"""
Upload generated shorts to YouTube via the YouTube Data API v3.

First-time setup: run  python youtube_setup.py
"""
from pathlib import Path

_TOKEN_FILE = Path(__file__).parent.parent / "token.json"
_CLIENT_SECRETS = Path(__file__).parent.parent / "client_secret.json"
_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


def is_configured() -> bool:
    """True if OAuth credentials or saved token exist."""
    return _CLIENT_SECRETS.exists() or _TOKEN_FILE.exists()


def _get_credentials():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        raise SystemExit(
            "Missing Google API libraries.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CLIENT_SECRETS.exists():
                raise FileNotFoundError(
                    "client_secret.json not found.\n"
                    "Run: python youtube_setup.py"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(_CLIENT_SECRETS), _SCOPES)
            creds = flow.run_local_server(port=0)

        with open(_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def upload_short(
    video_path: str,
    title: str,
    description: str = "",
    privacy: str = "private",
    tags: list = None,
) -> str:
    """
    Upload a video to YouTube. Returns the YouTube video ID.

    privacy: 'public', 'private', or 'unlisted'
    Vertical 9:16 videos <= 3 min are auto-classified as Shorts by YouTube.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
    except ImportError:
        raise SystemExit(
            "Missing Google API libraries.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # #Shorts in description ensures recommendation algorithm treats it as a Short
    body_desc = description.strip()
    if "#Shorts" not in body_desc and "#shorts" not in body_desc:
        body_desc = (body_desc + "\n\n#Shorts").strip()

    tag_list = list(set((tags or []) + ["shorts", "YouTube Shorts"]))

    body = {
        "snippet": {
            "title": title[:100],
            "description": body_desc[:5000],
            "tags": tag_list,
            "categoryId": "24",  # Entertainment
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=_CHUNK_SIZE,
        resumable=True,
        mimetype="video/mp4",
    )

    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"   Uploading... {pct}%", end="\r", flush=True)
        except HttpError as e:
            raise RuntimeError(f"YouTube upload failed: {e.reason}") from e

    print()
    return response["id"]
