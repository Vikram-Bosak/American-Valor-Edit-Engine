import os
import sys
import argparse
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta

# Add src to Python path so we can run this file directly
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from logger import logger
from queue_manager import process_next_media
from drive_reader import get_drive_service, get_daily_upload_count_from_drive, count_pending_media, has_uploaded_since_datetime
from health_checker import run_all_health_checks
from watchdog import update_heartbeat

def get_latest_scheduled_slot_time(est_now):
    """
    Computes the start datetime of the latest scheduled slot that should have run.
    Returns (datetime, media_type).
    """
    SLOTS = [
        {'hour': 8, 'minute': 0, 'type': 'reel'},
        {'hour': 10, 'minute': 30, 'type': 'photo'},
        {'hour': 12, 'minute': 30, 'type': 'reel'},
        {'hour': 15, 'minute': 0, 'type': 'photo'},
        {'hour': 17, 'minute': 0, 'type': 'reel'},
        {'hour': 19, 'minute': 0, 'type': 'photo'},
        {'hour': 20, 'minute': 30, 'type': 'reel'},
        {'hour': 22, 'minute': 30, 'type': 'photo'},
        {'hour': 23, 'minute': 45, 'type': 'reel'}
    ]
    
    latest_slot = None
    for s in SLOTS:
        slot_dt = est_now.replace(hour=s['hour'], minute=s['minute'], second=0, microsecond=0)
        if est_now >= slot_dt:
            latest_slot = (slot_dt, s['type'])
            
    if latest_slot is not None:
        return latest_slot
    else:
        # Fallback to the last slot of the previous day
        prev_day = est_now - timedelta(days=1)
        last_s = SLOTS[-1]
        return (prev_day.replace(hour=last_s['hour'], minute=last_s['minute'], second=0, microsecond=0), last_s['type'])

def validate_env():
    """Validates that all required environment variables are present and correct."""
    required = {
        'FB_ACCESS_TOKEN': "Facebook Page Access Token is required to post Reels.",
        'FB_PAGE_ID': "Facebook Page ID is required to target the correct page.",
        'GOOGLE_DRIVE_FOLDER_ID': "Google Drive Folder ID is required to read/write videos and database.",
    }
    
    # Check credentials path
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is missing.")
        return False
        
    if not os.path.exists(creds_path):
        logger.error(f"Google Drive credentials file not found at: {creds_path}")
        return False
        
    missing = []
    for var, desc in required.items():
        if not os.environ.get(var):
            logger.error(f"Missing environment variable: {var} - {desc}")
            missing.append(var)
            
    if missing:
        return False
        
    return True

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AI Facebook Reel Automation Agent Scheduler")
    parser.add_argument('--force', action='store_true', help='Force upload bypassing time slot locks')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    
    update_heartbeat("starting")
    
    logger.info("Initializing AI Facebook Reel Automation Agent...")
    
    if not validate_env():
        logger.error("Environment validation failed. Exiting.")
        update_heartbeat("failed_env_validation")
        sys.exit(1)
        
    # Initialize Drive service
    service = None
    root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
    
    try:
        service = get_drive_service()
        logger.info("Successfully connected to Google Drive API.")
    except Exception as e:
        logger.error(f"Failed to connect to Google Drive: {e}")
        update_heartbeat("unhealthy", {"error": f"Failed to connect to Google Drive: {e}"})
        sys.exit(1)

    # Run active health checks before checking files or scheduling
    access_token = os.environ.get('FB_ACCESS_TOKEN')
    page_id = os.environ.get('FB_PAGE_ID')
    is_healthy, health_results = run_all_health_checks(access_token, page_id)
    if not is_healthy:
        logger.error(f"System health check failed. Aborting cycle. Results: {health_results}")
        update_heartbeat("unhealthy", health_results)
        try:
            from src.common.discord import report_failure
            report_failure(f"System Health Check: Critical Health Check Failure:\n{health_results}")
        except Exception as tel_err:
            logger.error(f"Failed to send health failure notification to Discord: {tel_err}")
        return

    # Check if we have pending videos
    pending_reels = count_pending_media('reel')
    pending_photos = count_pending_media('photo')
    logger.info(f"Pending in Google Drive -> Reels: {pending_reels}, Photos: {pending_photos}")

    # Determine force upload status
    force_upload = args.force or os.environ.get('FORCE_UPLOAD') == 'true'

    if force_upload:
        logger.info("Force upload enabled. Bypassing US time slot check.")
        media_to_upload = 'reel' if pending_reels > 0 else ('photo' if pending_photos > 0 else None)
        if not media_to_upload:
            logger.info("No media available to force upload.")
            return
    else:
        # Time slot logic (US Eastern Time)
        est_now = datetime.now(ZoneInfo('America/New_York'))
        logger.info(f"Current time in US Eastern Time: {est_now.strftime('%Y-%m-%d %I:%M %p %Z')}")

        latest_slot_dt, target_media_type = get_latest_scheduled_slot_time(est_now)
        latest_slot_dt_utc = latest_slot_dt.astimezone(timezone.utc)
        
        # We need the root folder ID for the target media to check if it was already uploaded
        check_folder_id = root_folder_id if target_media_type == 'reel' else os.environ.get('GOOGLE_DRIVE_PHOTO_FOLDER_ID')

        # Check if an upload has already occurred in/since the latest slot
        if not check_folder_id:
            logger.warning(
                f"No folder ID configured for '{target_media_type}' type. "
                "Skipping duplicate-upload check. Set GOOGLE_DRIVE_PHOTO_FOLDER_ID if needed."
            )
        elif has_uploaded_since_datetime(service, check_folder_id, latest_slot_dt_utc):
            logger.info(f"Already uploaded for latest slot ({latest_slot_dt.strftime('%I:%M %p %Z')} - {target_media_type}). Skipping.")
            update_heartbeat("idle", {"message": f"Already uploaded in slot {latest_slot_dt.strftime('%I:%M %p %Z')}"})
            return

        logger.info(f"No upload detected for latest slot ({latest_slot_dt.strftime('%I:%M %p %Z')} - {target_media_type}). Triggering!")
        
        media_to_upload = target_media_type
        
        # Fallback logic
        if target_media_type == 'reel' and pending_reels == 0:
            logger.warning("Slot requires a Reel, but 0 pending. Falling back to Photo if available.")
            if pending_photos > 0:
                media_to_upload = 'photo'
            else:
                logger.info("No photos available for fallback either.")
                return
        elif target_media_type == 'photo' and pending_photos == 0:
            logger.warning("Slot requires a Photo, but 0 pending. Falling back to Reel if available.")
            if pending_reels > 0:
                media_to_upload = 'reel'
            else:
                logger.info("No reels available for fallback either.")
                return
                
        # Jitter implementation
        import random
        import time
        jitter_seconds = random.randint(0, 15 * 60)
        logger.info(f"Applying human-like jitter. Sleeping for {jitter_seconds} seconds ({jitter_seconds//60} mins)...")
        time.sleep(jitter_seconds)

    # Process the next media in the queue
    update_heartbeat("processing")
    try:
        success = process_next_media(media_to_upload)
        if success:
            update_heartbeat("healthy", {"message": "Cycle completed successfully"})
        else:
            update_heartbeat("idle", {"message": "Checked queue, no upload was performed"})
    except Exception as e:
        logger.error(f"Critical error in queue manager: {e}", exc_info=True)
        update_heartbeat("error", {"error": str(e)})
        try:
            from src.common.discord import report_failure
            report_failure(f"Queue Manager Process: Critical Queue Manager failure: {e}")
        except Exception as tel_err:
            logger.error(f"Failed to report crash to Discord: {tel_err}")

if __name__ == "__main__":
    main()
