import os
import requests
import random
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure we can import existing modules
try:
    from src.facebook_uploader import upload_reel
    from src.youtube_uploader import upload_to_youtube
except ImportError:
    from facebook_uploader import upload_reel
    from youtube_uploader import upload_to_youtube

load_dotenv()

def run_upload(video_data):
    logging.info("Starting Agent 3: Facebook + YouTube Uploader")
    
    edited_video_path = video_data.get('edited_path')
    title = video_data.get('title', 'Unknown Video')
    headline = video_data.get('seo_title', '')
    source_url = video_data.get('source_url', '')
    
    if not edited_video_path or not os.path.exists(edited_video_path):
        logging.warning("No edited video found to upload.")
        return video_data
        
    if video_data.get("editing_status") != "Success":
        logging.warning(f"Editing did not succeed (Status: {video_data.get('editing_status')}). Skipping upload.")
        if os.path.exists(edited_video_path):
            os.remove(edited_video_path)
        return video_data
        
    # Construct Facebook Caption dynamically and parse YouTube SEO metadata
    yt_title = title
    yt_desc = ""
    yt_tags = []
    
    try:
        from src.common.seo_generator import generate_upload_metadata
        task_id = video_data.get("id", "default")
        state_file = f"temp/state_upload_{task_id}.json"
        
        if os.path.exists(state_file):
            import json
            with open(state_file, "r") as f:
                context = json.load(f)
        else:
            context = video_data
            
        metadata = generate_upload_metadata(context)
        fb_caption = f"{metadata.get('facebook_caption', headline)}\n\n{metadata.get('hashtags', '#USArmy #USNavy #Military')}"
        yt_title = metadata.get('title', title)
        yt_desc = metadata.get('description', '')
        yt_tags = metadata.get('tags', [])
    except Exception as e:
        logging.error(f"Error generating dynamic SEO metadata: {e}")
        fb_caption = f"{headline}\n\n#USArmy #USNavy #Military"
        yt_title = title
        yt_desc = fb_caption
        yt_tags = ["military", "usarmy", "usnavy", "tactical", "elite"]
        
    video_data["description"] = fb_caption

    delay_seconds = random.randint(0, 900) # 0 to 15 minutes
    delay_minutes = delay_seconds / 60
    logging.info(f"Waiting for {delay_seconds} seconds ({delay_minutes:.1f} minutes) before uploading to appear human...")
    
    try:
        from src.common.discord import report_upload_delay
        report_upload_delay(delay_minutes)
    except Exception as e:
        logging.warning(f"Failed to send delay report: {e}")
        
    time.sleep(delay_seconds)

    fb_success = False
    yt_success = False
    tt_success = False

    # Facebook Upload
    try:
        logging.info(f"Uploading to Facebook with caption: {fb_caption}")
        fb_url = upload_reel(edited_video_path, fb_caption)
        logging.info(f"Successfully uploaded to Facebook: {fb_url}")
        video_data["fb_url"] = fb_url
        fb_success = True
    except Exception as e:
        logging.error(f"Failed to upload to Facebook: {e}")
        video_data["fb_err"] = str(e)
        
    # YouTube Upload (runs independently of Facebook)
    try:
        logging.info("Waiting 2 seconds before uploading to YouTube Shorts...")
        time.sleep(2)
        
        yt_title_clean = yt_title[:100] # YouTube title limit is 100 chars
        if "#shorts" not in yt_desc.lower():
            yt_desc = f"{yt_desc}\n\n#shorts"
            
        logging.info(f"Starting YouTube Shorts upload: title='{yt_title_clean}', tags={yt_tags}")
        yt_url = upload_to_youtube(edited_video_path, yt_title_clean, yt_desc, tags=yt_tags)
        logging.info(f"Successfully uploaded to YouTube Shorts: {yt_url}")
        video_data["yt_url"] = yt_url
        yt_success = True
    except Exception as e:
        logging.error(f"Failed to upload to YouTube: {e}")
        video_data["yt_err"] = str(e)

    # TikTok Upload
    try:
        logging.info("Waiting 2 seconds before uploading to TikTok...")
        time.sleep(2)
        
        # TikTok Caption can use the same fb_caption (usually short and has hashtags)
        tt_caption = fb_caption
        if len(tt_caption) > 150:
            tt_caption = tt_caption[:147] + "..."
            
        logging.info("Starting TikTok upload...")
        from src.tiktok_uploader import upload_tiktok
        tt_url = upload_tiktok(edited_video_path, tt_caption)
        logging.info(f"Successfully uploaded to TikTok: {tt_url}")
        video_data["tiktok_url"] = tt_url
        tt_success = True
    except Exception as e:
        logging.error(f"Failed to upload to TikTok: {e}")
        video_data["tiktok_err"] = str(e)
        
    # Set overall status based on whether at least one upload succeeded
    if fb_success or yt_success or tt_success:
        video_data["upload_status"] = "Success"
        status_parts = []
        if fb_success:
            status_parts.append("Facebook")
        if yt_success:
            status_parts.append("YouTube")
        if tt_success:
            status_parts.append("TikTok")
        logging.info(f"Upload completed successfully to: {', '.join(status_parts)}")
    else:
        video_data["upload_status"] = "Failed"
        logging.error("Facebook, YouTube and TikTok uploads failed.")
        if video_data.get("fb_err"):
            logging.error(f"  Facebook error: {video_data['fb_err']}")
        if video_data.get("yt_err"):
            logging.error(f"  YouTube error: {video_data['yt_err']}")
        if video_data.get("tiktok_err"):
            logging.error(f"  TikTok error: {video_data['tiktok_err']}")
        
    # Cleanup — keep the edited video if no upload succeeded so it stays
    # available as a downloadable artifact; remove it only after a successful upload.
    try:
        if fb_success or yt_success or tt_success:
            if os.path.exists(edited_video_path):
                os.remove(edited_video_path)
                logging.info(f"Cleaned up video file: {edited_video_path}")
        else:
            logging.info(f"Keeping edited video for artifact: {edited_video_path}")
    except Exception as e:
        logging.warning(f"Failed to clean up video file {edited_video_path}: {e}")
        
    return video_data

if __name__ == "__main__":
    pass
