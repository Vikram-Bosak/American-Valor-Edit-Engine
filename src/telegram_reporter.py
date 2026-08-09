"""
Discord reporter for the production queue-based pipeline (scheduler.py).
Sends success/failure notifications via Discord Webhooks.
"""
import os
try:
    from .common.discord import send_discord_message, get_run_details
except ImportError:
    from common.discord import send_discord_message, get_run_details

try:
    from .logger import logger
except ImportError:
    from logger import logger

def report_success(filename, title, fb_url, remaining_queue, media_type='reel'):
    """
    Reports a successful upload to Discord.
    """
    media_emoji = "🎬" if media_type == 'reel' else "📷"
    embed = {
        "title": f"✅ {media_type.title()} Upload Successful",
        "color": 3066993, # Green
        "fields": [
            {"name": f"{media_emoji} File", "value": filename, "inline": False},
            {"name": "📝 Title", "value": title, "inline": False},
            {"name": "🔗 Facebook URL", "value": fb_url, "inline": False},
            {"name": "📦 Queue Remaining", "value": str(remaining_queue), "inline": True}
        ],
        "footer": {
            "text": get_run_details().replace("**", "")
        }
    }
    try:
        send_discord_message("", embeds=[embed])
    except Exception as e:
        logger.error(f"Failed to send success report to Discord: {e}")

def report_failure(filename, error_message, remaining_queue, media_type='reel'):
    """
    Reports a failure to Discord.
    """
    media_emoji = "🎬" if media_type == 'reel' else "📷"
    embed = {
        "title": f"❌ {media_type.title()} Upload Failed",
        "color": 15158332, # Red
        "fields": [
            {"name": f"{media_emoji} File", "value": filename, "inline": False},
            {"name": "⚠️ Error", "value": error_message, "inline": False},
            {"name": "📦 Queue Remaining", "value": str(remaining_queue), "inline": True}
        ],
        "footer": {
            "text": get_run_details().replace("**", "")
        }
    }
    try:
        send_discord_message("", embeds=[embed])
    except Exception as e:
        logger.error(f"Failed to send failure report to Discord: {e}")
