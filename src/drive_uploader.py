import os
import json
import glob
import logging
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCOPES = ['https://www.googleapis.com/auth/drive']


def get_drive_service():
    """Build a Drive service from OAuth user creds (preferred) or a service account key."""
    token_json = os.environ.get('GOOGLE_DRIVE_TOKEN_JSON', '')

    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if creds.expired:
            creds.refresh(Request())
        return build('drive', 'v3', credentials=creds)

    token_path = os.environ.get('GOOGLE_DRIVE_TOKEN_PATH', '')
    if token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds.expired:
            creds.refresh(Request())
        return build('drive', 'v3', credentials=creds)

    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    creds_json = os.environ.get('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON', '')

    if creds_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json), scopes=SCOPES)
    elif creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES)
    else:
        raise Exception("Google Drive credentials not found. Set GOOGLE_DRIVE_TOKEN_JSON, GOOGLE_DRIVE_TOKEN_PATH, GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS.")

    return build('drive', 'v3', credentials=creds)


def upload_file(service, file_path, folder_id, name=None):
    """Upload a file to the given Drive folder. Overwrites an existing file with the same name."""
    name = name or os.path.basename(file_path)
    media = MediaFileUpload(file_path, mimetype='video/mp4', resumable=True)

    # Check for an existing file with the same name in the folder
    query = f"'{folder_id}' in parents and name='{name}' and trashed=false"
    items = service.files().list(q=query, fields="files(id, name)").execute().get('files', [])

    if items:
        file_id = items[0]['id']
        service.files().update(fileId=file_id, media_body=media).execute()
        logging.info(f"Updated existing file on Drive: {name} (id={file_id})")
        return file_id

    file_metadata = {'name': name, 'parents': [folder_id]}
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')
    logging.info(f"Uploaded new file to Drive: {name} (id={file_id})")
    return file_id


def run_upload():
    folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '').strip()
    if not folder_id:
        raise Exception("GOOGLE_DRIVE_FOLDER_ID is not set.")

    patterns = [
        os.environ.get('DRIVE_UPLOAD_PATTERN', 'workspace/*.mp4'),
        'output/*.mp4',
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    files = [f for f in files if not f.endswith('raw_video.mp4')]
    files = sorted(set(files))
    if not files:
        logging.warning("No edited videos found to upload.")
        return

    service = get_drive_service()
    for fp in files:
        if os.path.exists(fp):
            upload_file(service, fp, folder_id)
        else:
            logging.warning(f"Skipping missing file: {fp}")


if __name__ == "__main__":
    run_upload()
