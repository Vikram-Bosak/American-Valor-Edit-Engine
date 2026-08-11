import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_1_downloader import run_downloader, save_to_history
from src.agent_2_editor import process_video
from src.agent_3_uploader import run_upload
from src.common.limits import can_download, can_upload, increment_download, increment_edit, increment_upload
from src.common.discord import (
    report_download_start, 
    report_download_complete, 
    report_edit_start, 
    report_edit_complete, 
    send_discord_message
)

import json


def write_report(report_data):
    os.makedirs("workspace", exist_ok=True)
    try:
        with open("workspace/report.json", "w") as f:
            json.dump(report_data, f, indent=4)
        print("Report written to workspace/report.json")
    except Exception as e:
        print(f"Warning: Failed to write report: {e}")

def run_single_sequence():
    print("\n--- STARTING SEQUENTIAL PIPELINE (SINGLE RUN) ---")
    
    report_data = {
        "video_name": "N/A",
        "download_status": "Failed / Unknown",
        "editing_status": "N/A",
        "upload_status": "N/A",
        "seo_title": "N/A",
        "description": "N/A",
        "facebook_url": "N/A",
        "youtube_url": "N/A",
        "tiktok_url": "N/A"
    }
    
    if not can_download() or not can_upload():
        print("Daily upload limit reached. Exiting.")
        report_data["download_status"] = "Skipped (Daily limit reached)"
        write_report(report_data)
        return False

    # 1. Download
    report_download_start()
    video_data, stats = run_downloader()
    if not video_data:
        print("No video found.")
        report_data["download_status"] = "No new video found"
        write_report(report_data)
        return False
            
    # Ensure stats always has required keys for downstream code
    stats.setdefault("errors", [])
    stats.setdefault("videos_edited", 0)
    stats.setdefault("videos_uploaded", 0)

    task_id = video_data['id']
    title = video_data.get('title', '')
    source_url = video_data.get('source_url', '')
    
    report_data["video_name"] = title if title else task_id
    report_data["download_status"] = "Success"
    write_report(report_data)
    
    # Pre-screening text metadata safety check
    from src.common.safety_filter import check_metadata_safety
    safety_check = check_metadata_safety(title, source_url)
    if not safety_check["is_safe"]:
        reasons = ", ".join(safety_check["reasons"])
        print(f"Video {task_id} rejected by safety filter: {reasons}")
        send_discord_message(f"⚠️ **Video {task_id} Rejected by Safety Filter:**\n{reasons}")
        report_data["download_status"] = f"Rejected (Safety: {reasons})"
        write_report(report_data)
        # Save to history to prevent picking this unsafe video again
        save_to_history(task_id)
        return False
        
    print(f"Downloaded Video: {task_id}")
    report_download_complete(source_url)
    send_discord_message(f"🆔 **Unique ID generated:** {task_id}")
    increment_download()
    
    # Save to history immediately to prevent infinite retry loops if edit/upload fails
    save_to_history(task_id)
    
    # IMMEDIATELY push to GitHub so if the user triggers another run during the 15-minute sleep, it won't duplicate!
    print("Pushing history to GitHub immediately to prevent race conditions...")
    try:
        import subprocess
        subprocess.run("git config --global user.name 'github-actions[bot]'", shell=True)
        subprocess.run("git config --global user.email 'github-actions[bot]@users.noreply.github.com'", shell=True)
        subprocess.run("git add downloaded_history.txt daily_limits.json", shell=True, check=True)
        subprocess.run("git commit -m 'Update history (mid-run) [skip ci]'", shell=True, check=True)
        subprocess.run("git pull origin master --rebase --strategy-option=ours", shell=True, check=True)
        subprocess.run("git push origin HEAD:master", shell=True, check=True)
        print("History pushed successfully.")
    except Exception as e:
        print(f"Warning: Mid-run history push failed: {e}")
    
    # 2. Edit
    report_edit_start()
    report_data["editing_status"] = "Pending"
    write_report(report_data)
    try:
        print(f"Editing Video {task_id}...")
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            report_edit_complete()
            increment_edit()
            stats["videos_edited"] = 1
            report_data["editing_status"] = "Success"
            write_report(report_data)
        else:
            send_discord_message(f"❌ **Editing Failed for {task_id}**")
            stats["errors"].append(f"Editing Failed for {task_id}")
            report_data["editing_status"] = "Failed"
            write_report(report_data)
            return False
    except Exception as e:
        print(f"Editing failed: {e}")
        send_discord_message(f"❌ **Editing Failed for {task_id}:**\n{e}")
        stats["errors"].append(f"Editing Exception: {str(e)}")
        report_data["editing_status"] = f"Failed ({str(e)})"
        write_report(report_data)
        return False
        
    # 3. Upload
    print(f"Uploading Video {task_id}...")
    report_data["upload_status"] = "Pending"
    write_report(report_data)
    
    video_data = run_upload(video_data)
    
    if video_data.get('upload_status') == 'Success':
        increment_upload()
        stats["videos_uploaded"] = 1
    
    report_data["upload_status"] = video_data.get('upload_status', 'Failed')
    report_data["facebook_url"] = video_data.get('fb_url', 'N/A')
    report_data["youtube_url"] = video_data.get('yt_url', 'N/A')
    report_data["tiktok_url"] = video_data.get('tiktok_url', 'N/A')
    report_data["seo_title"] = video_data.get('title', 'N/A')
    report_data["description"] = video_data.get('description', 'N/A')
    report_data["video_file_name"] = video_data.get('video_file_name', 'N/A')
    write_report(report_data)
    
    # Send final summary to Discord
    summary_data = {
        "video_name": title,  # Original Twitter tweet text/name
        "fb_url": video_data.get('fb_url', 'N/A'),
        "yt_url": video_data.get('yt_url', 'N/A'),
        "tiktok_url": video_data.get('tiktok_url', 'N/A'),
        "fb_err": video_data.get('fb_err', 'N/A'),
        "yt_err": video_data.get('yt_err', 'N/A'),
        "tiktok_err": video_data.get('tiktok_err', 'N/A'),
        "title": video_data.get('title', 'N/A'),  # SEO Title
        "description": video_data.get('description', 'N/A'),
        "original_file": f"Twitter Link: {source_url}"  # Original Twitter Post URL
    }
    
    from src.common.discord import report_final_summary
    report_final_summary(summary_data, stats)
    
    print("Pipeline run completed.")
    return True

if __name__ == "__main__":
    run_single_sequence()
