import os
import json
import requests
import shutil
from dotenv import load_dotenv

load_dotenv()

def send_discord_report(embed):
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Discord Webhook URL is missing. Skipping Discord notification.")
        return False
        
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        response.raise_for_status()
        print("Successfully sent unified Discord report.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord message: {e}")
        return False

def main():
    print("Starting Agent 4: Unified Reporter")
    report_path = "workspace/report.json"
    
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            try:
                report = json.load(f)
            except json.JSONDecodeError:
                report = {}
    else:
        report = {}
        
    # Default values in case keys are missing, forced to be valid strings
    video_name = str(report.get('video_name') or 'N/A').strip() or 'N/A'
    download_status = str(report.get('download_status') or 'Failed / Unknown').strip() or 'Failed / Unknown'
    editing_status = str(report.get('editing_status') or 'N/A').strip() or 'N/A'
    upload_status = str(report.get('upload_status') or 'N/A').strip() or 'N/A'
    seo_title = str(report.get('seo_title') or 'N/A').strip() or 'N/A'
    description = str(report.get('description') or 'N/A').strip() or 'N/A'
    fb_url = str(report.get('facebook_url') or 'N/A').strip() or 'N/A'
    
    # Search for safety flags/actions in state json files
    safety_info = "Clean (No risks flagged)"
    try:
        temp_files = os.listdir("temp")
        state_files = [f for f in temp_files if f.startswith("state_upload_") and f.endswith(".json")]
        if state_files:
            state_path = os.path.join("temp", state_files[0])
            with open(state_path, 'r') as sf:
                state_data = json.load(sf)
                flags = state_data.get("safety_flags", [])
                actions = state_data.get("safety_actions", [])
                if flags:
                    safety_info = f"⚠️ Flags: {', '.join(flags)} | Applied Mod: {', '.join(actions) if actions else 'None'}"
    except Exception as e:
        print(f"Could not load safety state info: {e}")

    safety_info = str(safety_info or 'Clean (No risks flagged)').strip() or 'Clean (No risks flagged)'

    # Determine YouTube Status
    yt_url = str(report.get('youtube_url') or 'N/A').strip() or 'N/A'
    yt_status = "Success" if "youtube.com" in yt_url or "youtu.be" in yt_url else "Failed / N/A"
    
    # Determine TikTok Status
    tiktok_url = str(report.get('tiktok_url') or 'N/A').strip() or 'N/A'
    tiktok_status = "Success" if "tiktok.com" in tiktok_url else "Failed / N/A"
    
    # GitHub Action Variables
    repo = os.environ.get('GITHUB_REPOSITORY', 'Vikram-Bosak/American-Valor-Edit-Engine')
    run_id = os.environ.get('GITHUB_RUN_ID', 'UNKNOWN')
    repo_url = f"https://github.com/{repo}"
    run_url = f"{repo_url}/actions/runs/{run_id}"
    
    is_success = upload_status == "Success"
    color = 3066993 if is_success else 15158332
    
    embed = {
        "title": "✅ Pipeline Run Completed Successfully" if is_success else "❌ Pipeline Run Failed",
        "color": color,
        "fields": [
            {"name": "🎬 Video Name", "value": video_name, "inline": False},
            {"name": "🛡️ Copyright & Safety Check", "value": safety_info, "inline": False},
            {"name": "📥 Download Status", "value": download_status, "inline": True},
            {"name": "✂️ Editing Status", "value": editing_status, "inline": True},
            {"name": "📤 Facebook Upload", "value": upload_status, "inline": True},
            {"name": "📤 YouTube Upload", "value": yt_status, "inline": True},
            {"name": "📤 TikTok Upload", "value": tiktok_status, "inline": True},
            {"name": "🏷️ SEO Title", "value": seo_title, "inline": False},
            {"name": "🔗 Facebook Reel URL", "value": fb_url, "inline": False},
            {"name": "▶️ YouTube Video URL", "value": yt_url, "inline": False},
            {"name": "🎵 TikTok Video URL", "value": tiktok_url, "inline": False},
            {"name": "📄 Workflow Run", "value": f"[View Run]({run_url})", "inline": False}
        ],
        "footer": {
            "text": f"Repository: {repo} | Run ID: {run_id}"
        }
    }
    
    if "No new video" in download_status:
        print("No new video to process. Skipping Discord notification to avoid spam.")
    else:
        send_discord_report(embed)
    
    # Cleanup workspace completely (skip when workflow needs the edited video)
    if os.environ.get("SKIP_WORKSPACE_CLEANUP") != "1":
        if os.path.exists("workspace"):
            shutil.rmtree("workspace")
            print("Cleaned up workspace directory.")
        
    # Also clean up temp state uploads
    try:
        for f in os.listdir("temp"):
            if f.startswith("state_upload_") and f.endswith(".json"):
                os.remove(os.path.join("temp", f))
    except Exception:
        pass

if __name__ == "__main__":
    main()
