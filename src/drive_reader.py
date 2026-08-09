import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
try:
    from .logger import logger
except ImportError:
    from logger import logger

# Define scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not creds_path or not os.path.exists(creds_path):
        raise Exception(f"Google Drive credentials not found at {creds_path}")
        
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES)
        
    return build('drive', 'v3', credentials=creds)

def get_folder_id(service, parent_id, folder_name):
    """Finds a folder by name inside a parent folder."""
    query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        # Create it if it doesn't exist
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    return items[0]['id']

def setup_folders(service, root_folder_id):
    """Ensures Pending, Uploaded, and Failed folders exist."""
    pending_id = get_folder_id(service, root_folder_id, 'Pending')
    uploaded_id = get_folder_id(service, root_folder_id, 'Uploaded')
    failed_id = get_folder_id(service, root_folder_id, 'Failed')
    return pending_id, uploaded_id, failed_id

def get_next_media(media_type='reel'):
    """
    Finds the first media file in the 'Pending' folder, downloads it to temp/,
    and returns its file path, drive file ID, and the uploaded/failed folder IDs.
    Returns None if no media are found.
    """
    if media_type == 'reel':
        root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
        mime_query = "mimeType='video/mp4'"
    else:
        root_folder_id = os.environ.get('GOOGLE_DRIVE_PHOTO_FOLDER_ID')
        mime_query = "(mimeType='image/jpeg' or mimeType='image/png' or mimeType='image/jpg')"

    if not root_folder_id:
        raise Exception(f"Folder ID for {media_type} is missing from environment variables.")
        
    service = get_drive_service()
    pending_id, uploaded_id, failed_id = setup_folders(service, root_folder_id)
    
    # Get the oldest media in Pending folder
    query = f"'{pending_id}' in parents and {mime_query} and trashed=false"
    results = service.files().list(
        q=query, 
        orderBy="createdTime asc", 
        pageSize=1, 
        fields="files(id, name)"
    ).execute()
    
    items = results.get('files', [])
    if not items:
        return None
        
    file_id = items[0]['id']
    file_name = items[0]['name']
    
    # Download the file
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file_name)
    
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(temp_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    logger.info(f"Downloading {file_name} from Google Drive...")
    try:
        while done is False:
            status, done = downloader.next_chunk()
    except Exception as dl_err:
        # Clean up partial download on failure
        fh.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Failed to download {file_name} from Google Drive: {dl_err}")
    finally:
        try:
            fh.close()
        except Exception:
            pass
    
    logger.info(f"Downloaded {file_name} successfully.")
    
    return {
        'path': temp_path,
        'filename': file_name,
        'file_id': file_id,
        'pending_id': pending_id,
        'uploaded_id': uploaded_id,
        'failed_id': failed_id,
        'service': service
    }

def move_file(service, file_id, current_folder_id, new_folder_id):
    """Moves a file from one folder to another in Google Drive."""
    # Retrieve the existing parents to remove
    file = service.files().get(fileId=file_id, fields='parents').execute()
    previous_parents = ",".join(file.get('parents'))
    
    # Move the file to the new folder
    service.files().update(
        fileId=file_id,
        addParents=new_folder_id,
        removeParents=previous_parents,
        fields='id, parents'
    ).execute()

def count_pending_media(media_type='reel'):
    """Returns the number of remaining media files in the Pending folder."""
    try:
        if media_type == 'reel':
            root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
            mime_query = "mimeType='video/mp4'"
        else:
            root_folder_id = os.environ.get('GOOGLE_DRIVE_PHOTO_FOLDER_ID')
            mime_query = "(mimeType='image/jpeg' or mimeType='image/png' or mimeType='image/jpg')"

        if not root_folder_id:
            return 0

        service = get_drive_service()
        pending_id = get_folder_id(service, root_folder_id, 'Pending')
        
        query = f"'{pending_id}' in parents and {mime_query} and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        return len(results.get('files', []))
    except Exception as e:
        logger.error(f"Failed to count pending {media_type}s: {e}")
        return 0

def get_daily_upload_count_from_drive(service, root_folder_id):
    """
    Counts the number of files in the 'Uploaded' folder in Google Drive
    created today in US Eastern Time.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    try:
        uploaded_id = get_folder_id(service, root_folder_id, 'Uploaded')
        
        # Get start of today in US Eastern Time
        est_now = datetime.now(ZoneInfo('America/New_York'))
        est_today_start = est_now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert to UTC for Google Drive API query format
        utc_today_start = est_today_start.astimezone(timezone.utc)
        
        query = f"'{uploaded_id}' in parents and createdTime >= '{utc_today_start.isoformat()}' and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        return len(results.get('files', []))
    except Exception as e:
        logger.error(f"Failed to count daily uploads from Drive: {e}")
        return 0

def has_already_uploaded_in_slot(service, root_folder_id, est_now):
    """
    Checks if a video was already uploaded to Google Drive during the current slot hour.
    Uses timezone-aware UTC datetime instead of deprecated datetime.utcnow().
    """
    from datetime import datetime, timezone
    try:
        uploaded_id = get_folder_id(service, root_folder_id, 'Uploaded')
        
        # Use timezone-aware UTC datetime (datetime.utcnow() is deprecated in 3.12+)
        now_utc = datetime.now(timezone.utc)
        current_hour_start_utc = now_utc.replace(minute=0, second=0, microsecond=0)
        
        query = f"'{uploaded_id}' in parents and createdTime >= '{current_hour_start_utc.isoformat()}' and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        return len(results.get('files', [])) > 0
    except Exception as e:
        logger.error(f"Failed to check slot upload status: {e}")
        return True # Default to True on error to prevent double-posting

def download_db(service, root_folder_id):
    """
    Looks for reels.db in the Google Drive root folder. If found, downloads it to database/reels.db.
    Returns the file ID of the database file on Google Drive, or None if not found.
    """
    try:
        # Import dynamically to avoid circular import if database imports drive_reader
        try:
            from .database import DB_PATH, DB_DIR
        except ImportError:
            from database import DB_PATH, DB_DIR

        query = f"'{root_folder_id}' in parents and name='reels.db' and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])
        
        if not items:
            logger.info("No reels.db database found on Google Drive. Will initialize fresh.")
            return None
            
        file_id = items[0]['id']
        os.makedirs(DB_DIR, exist_ok=True)
        
        request = service.files().get_media(fileId=file_id)
        with open(DB_PATH, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
        logger.info("Successfully downloaded reels.db from Google Drive.")
        return file_id
    except Exception as e:
        logger.error(f"Failed to download database from Google Drive: {e}")
        return None

def upload_db(service, root_folder_id, db_file_id=None):
    """
    Uploads/overwrites database/reels.db to the root folder in Google Drive.
    """
    try:
        # Import dynamically to avoid circular import
        try:
            from .database import DB_PATH
        except ImportError:
            from database import DB_PATH

        if not os.path.exists(DB_PATH):
            logger.warning("Local database reels.db does not exist. Skipping upload.")
            return None

        media = MediaFileUpload(DB_PATH, mimetype='application/x-sqlite3', resumable=True)
        
        if db_file_id:
            # Update existing file
            service.files().update(
                fileId=db_file_id,
                media_body=media
            ).execute()
            logger.info("Successfully updated existing reels.db on Google Drive.")
            return db_file_id
        else:
            # Search again to prevent duplicates in case another runner or step created it
            query = f"'{root_folder_id}' in parents and name='reels.db' and trashed=false"
            results = service.files().list(q=query, fields="files(id)").execute()
            items = results.get('files', [])
            
            if items:
                db_file_id = items[0]['id']
                service.files().update(
                    fileId=db_file_id,
                    media_body=media
                ).execute()
                logger.info("Successfully updated reels.db on Google Drive (resolved dynamic match).")
                return db_file_id
            else:
                # Create new file
                file_metadata = {
                    'name': 'reels.db',
                    'parents': [root_folder_id]
                }
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                new_id = file.get('id')
                logger.info(f"Created reels.db on Google Drive with ID: {new_id}")
                return new_id
    except Exception as e:
        logger.error(f"Failed to upload database to Google Drive: {e}")
        return db_file_id

def has_uploaded_since_datetime(service, root_folder_id, start_dt_utc):
    """
    Checks if any video was uploaded to the 'Uploaded' folder in Google Drive 
    at or after the specified UTC datetime.
    """
    try:
        uploaded_id = get_folder_id(service, root_folder_id, 'Uploaded')
        query = f"'{uploaded_id}' in parents and createdTime >= '{start_dt_utc.isoformat()}' and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        return len(results.get('files', [])) > 0
    except Exception as e:
        logger.error(f"Failed to check upload status since {start_dt_utc}: {e}")
        return True # Default to True on error to prevent double-posting

