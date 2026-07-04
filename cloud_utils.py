"""
cloud_utils.py
Cloud save integrations for Google Drive and Dropbox.

Google Drive uses OAuth 2.0 (installed-app flow). On first run it opens a
browser window for the user to grant access, then caches a token.json
locally so future saves don't re-prompt.

Dropbox uses a simple access token (generate one at
https://www.dropbox.com/developers/apps -> your app -> "Generate access token",
or implement the refresh-token flow for long-lived access).
"""

import io
import os

TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

def get_drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, DRIVE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret_file = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "client_secret.json")
            if not os.path.exists(client_secret_file):
                raise FileNotFoundError(
                    f"Google OAuth client secret file not found at '{client_secret_file}'. "
                    "Create OAuth credentials (Desktop app) in Google Cloud Console and download the JSON."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, DRIVE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def upload_to_drive(file_bytes: bytes, filename: str, mime_type: str, folder_id: str = None) -> str:
    """Uploads bytes to Google Drive, returns the shareable webViewLink."""
    from googleapiclient.http import MediaIoBaseUpload

    service = get_drive_service()
    file_metadata = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    created = service.files().create(
        body=file_metadata, media_body=media, fields="id, webViewLink"
    ).execute()

    # Make it viewable by anyone with the link (adjust if you want stricter sharing)
    service.permissions().create(
        fileId=created["id"], body={"role": "reader", "type": "anyone"}
    ).execute()

    return created.get("webViewLink", "")


# ---------------------------------------------------------------------------
# Dropbox
# ---------------------------------------------------------------------------

def upload_to_dropbox(file_bytes: bytes, filename: str, dest_folder: str = "/OCR Exports") -> str:
    """Uploads bytes to Dropbox, returns a shared link."""
    import dropbox
    from dropbox.files import WriteMode

    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("Missing DROPBOX_ACCESS_TOKEN. Add it in the sidebar or your .env file.")

    dbx = dropbox.Dropbox(token)
    path = f"{dest_folder.rstrip('/')}/{filename}"
    dbx.files_upload(file_bytes, path, mode=WriteMode("overwrite"))

    try:
        link = dbx.sharing_create_shared_link_with_settings(path)
        return link.url
    except dropbox.exceptions.ApiError:
        # Link may already exist
        links = dbx.sharing_list_shared_links(path=path).links
        return links[0].url if links else path
