import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_message(content: str, embeds: list = None) -> bool:
    """
    Sends a message (with optional embeds) to the Discord Webhook.
    """
    if not DISCORD_WEBHOOK_URL:
        print("Discord configuration is missing (DISCORD_WEBHOOK_URL). Skipping notification.")
        print(f"Content: {content}")
        return False

    # Discord handles Markdown perfectly, convert basic HTML tags to Markdown
    # since Discord doesn't support HTML
    formatted_content = content
    html_to_md = {
        "<b>": "**", "</b>": "**",
        "<i>": "*", "</i>": "*",
        "🔴": "🔴", "🟢": "🟢", "🟡": "🟡", "✅": "✅", "❌": "❌", "⏳": "⏳", "🆔": "🆔"
    }
    for html_tag, md_tag in html_to_md.items():
        formatted_content = formatted_content.replace(html_tag, md_tag)

    payload = {
        "content": formatted_content if not embeds else None
    }
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        return False

def get_run_details() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "Unknown")
    workflow = os.environ.get("GITHUB_WORKFLOW", "Unknown")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"**Run ID:** {run_id} | **Workflow:** {workflow} | **Time:** {current_time}"

def report_download_start():
    embed = {
        "title": "🟢 USA Military Download Started",
        "description": get_run_details(),
        "color": 3066993 # Greenish
    }
    send_discord_message("", embeds=[embed])

def report_download_complete(source_url: str):
    embed = {
        "title": "✅ USA Military Download Completed",
        "description": f"**Source:** {source_url}\n{get_run_details()}",
        "color": 3066993
    }
    send_discord_message("", embeds=[embed])

def report_edit_start():
    embed = {
        "title": "🟡 Video Editing Started",
        "description": get_run_details(),
        "color": 16776960 # Yellow
    }
    send_discord_message("", embeds=[embed])

def report_edit_complete():
    embed = {
        "title": "✅ Video Editing Completed",
        "description": get_run_details(),
        "color": 3066993
    }
    send_discord_message("", embeds=[embed])

def report_upload_delay(delay_minutes: float):
    embed = {
        "title": "⏳ Simulation Delay Initiated",
        "description": f"Waiting for **{delay_minutes:.1f} minutes** before upload to simulate human behavior...\n{get_run_details()}",
        "color": 16776960
    }
    send_discord_message("", embeds=[embed])

def send_video(video_path: str, caption: str = ""):
    if not DISCORD_WEBHOOK_URL:
        print("Discord configuration is missing. Cannot send video.")
        return None, None
        
    if not os.path.exists(video_path):
        print(f"Video file {video_path} not found.")
        return None, None

    # Check file size (Discord free tier limit is 25MB)
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if file_size_mb > 25:
        print(f"Video {video_path} is {file_size_mb:.2f}MB, which exceeds Discord's 25MB limit. Sending text only.")
        send_discord_message(f"{caption}\n\n*Video too large for Discord webhook ({file_size_mb:.2f}MB)*")
        return None, None

    try:
        with open(video_path, 'rb') as video_file:
            files = {'file': (os.path.basename(video_path), video_file, 'video/mp4')}
            data = {'content': caption}
            response = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files, timeout=60)
            response.raise_for_status()
            print("Video sent to Discord successfully!")
            return True, None
    except Exception as e:
        print(f"Failed to send Discord video: {e}")
    return None, None

def report_final_summary(summary_data: dict, stats: dict = None):
    stats = stats or {}
    profiles_scanned = stats.get('profiles_scanned', 0)
    new_videos = stats.get('new_videos_found', 0)
    skipped = stats.get('videos_skipped', 0)
    downloaded = stats.get('videos_downloaded', 0)
    edited = stats.get('videos_edited', 0)
    uploaded = stats.get('videos_uploaded', 0)
    errors = stats.get('errors', [])
    
    error_text = "\n".join([f"❌ {e}" for e in errors]) if errors else "None"
    
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "Vikram-Bosak/American-Valor-Edit-Engine")
    workflow_url = f"https://github.com/{repo_name}/actions/runs/{run_id}" if run_id else f"https://github.com/{repo_name}/actions"
    
    if not summary_data:
        # Just send the stats report if no video was fully processed
        msg = (
            f"ℹ️ **Pipeline Scan Report**\n\n"
            f"🔍 **Profiles Scanned:** {profiles_scanned}\n"
            f"🆕 **New Videos Found (Last 24 hours):** {new_videos}\n"
            f"⏭️ **Videos Skipped (Already Processed):** {skipped}\n"
            f"📥 **Videos Downloaded:** {downloaded}\n\n"
            f"⚠️ **Errors:**\n{error_text}\n\n"
            f"📄 **Workflow Run:**\n{workflow_url}"
        )
        send_discord_message(msg)
        return

    # Determine success status
    fb_url = str(summary_data.get('fb_url', 'N/A'))
    yt_url = str(summary_data.get('yt_url', 'N/A'))
    tiktok_url = str(summary_data.get('tiktok_url', 'N/A'))
    
    fb_err = str(summary_data.get('fb_err', 'Unknown Error'))
    yt_err = str(summary_data.get('yt_err', 'Unknown Error'))
    tiktok_err = str(summary_data.get('tiktok_err', 'Unknown Error'))
    
    fb_status = "Success" if fb_url not in ["Failed", "N/A", "None", None] else f"Failed ({fb_err})"
    yt_status = "Success" if yt_url not in ["Failed", "N/A", "None", None] else f"Failed ({yt_err})"
    tiktok_status = "Success" if tiktok_url not in ["Failed", "N/A", "None", None] else f"Failed ({tiktok_err})"
    
    title = str(summary_data.get('title', 'N/A'))
    video_name = str(summary_data.get('video_name', 'N/A'))
    description = str(summary_data.get('description', 'N/A'))
    original_file = str(summary_data.get('original_file', 'raw_video.mp4'))
    
    msg = (
        f"✅ **Pipeline Run Completed**\n\n"
        f"🎬 **Video Name:**\n{video_name}\n\n"
        f"📤 **Facebook Upload Status:** {fb_status}\n"
        f"📤 **YouTube Upload Status:** {yt_status}\n"
        f"📤 **TikTok Upload Status:** {tiktok_status}\n\n"
        f"🏷️ **SEO Title:**\n{title}\n\n"
        f"📝 **Description:**\n{description}\n\n"
        f"Original File: {original_file}\n\n"
        f"🔗 **Facebook Reel URL:**\n{fb_url}\n\n"
        f"▶️ **YouTube Video URL:**\n{yt_url}\n\n"
        f"🎵 **TikTok Video URL:**\n{tiktok_url}\n\n"
        f"📦 **GitHub Repository:**\nhttps://github.com/{repo_name}\n\n"
        f"📄 **Workflow Run:**\n{workflow_url}"
    )
    send_discord_message(msg)

def report_success(message: str):
    send_discord_message(f"✅ **Success:** {message}")

def report_failure(message: str):
    send_discord_message(f"❌ **Failure:** {message}")
