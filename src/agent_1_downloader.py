import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import yt_dlp
from dotenv import load_dotenv

load_dotenv()
HISTORY_FILE = 'downloaded_history.txt'

ydl_opts_download = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': 'workspace/raw_video.mp4',
    'quiet': False
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def search_and_download_latest_video():
    print("Searching Twitter (via Nitter RSS) for new videos posted in the last 24 hours...")
    
    stats = {
        "profiles_scanned": 0,
        "new_videos_found": 0,
        "videos_downloaded": 0,
        "videos_skipped": 0,
        "errors": []
    }
    
    # Default military profiles (used only when no profiles are provided via env vars)
    default_profiles = [
        "https://x.com/USArmy",
        "https://x.com/USNavy",
        "https://x.com/USMC",
        "https://x.com/USAirForce",
        "https://x.com/DeptofDefense",
        "https://x.com/NationalGuard",
        "https://x.com/USArmyReserve",
        "https://x.com/US_SpaceForce",
        "https://x.com/USCoastGuard",
        "https://x.com/Centcom",
        "https://x.com/USPacificFleet",
        "https://x.com/PacificMarines",
        "https://x.com/AirForceReserve"
    ]

    # Profiles come from input via env vars (X_PROFILES or TWITTER_PROFILES).
    # Accept comma-separated usernames, full x.com URLs, or twitter.com URLs.
    # If none provided, fall back to the default military list.
    env_profiles = os.environ.get("X_PROFILES") or os.environ.get("TWITTER_PROFILES")
    if env_profiles:
        profiles = [p.strip() for p in env_profiles.split(",") if p.strip()]
        print(f"Using profiles from env input ({len(profiles)}): {profiles}")
    else:
        profiles = default_profiles
        print("No X_PROFILES/TWITTER_PROFILES env input found. Using default military profiles.")

    # Clean profiles to just usernames if they are full URLs
    usernames = []
    for p in profiles:
        if "x.com/" in p:
            usernames.append(p.split("x.com/")[-1].strip("/"))
        elif "twitter.com/" in p:
            usernames.append(p.split("twitter.com/")[-1].strip("/"))
        else:
            usernames.append(p)
            
    history = load_history()
    
    time_limit = datetime.now(timezone.utc) - timedelta(hours=24)
    print(f"Time limit is set to: {time_limit.isoformat()}")
    
    # Only nitter.net works reliably (privacydev.net dead, poast.org 403)
    nitter_instances = [
        "https://nitter.net"
    ]
    
    valid_videos = []
    
    for username in usernames:
        stats["profiles_scanned"] += 1
        print(f"--------------------------------------------------")
        print(f"Checking profile: {username}")
        
        rss_fetched = False
        items = []
        for instance in nitter_instances:
            url = f"{instance}/{username}/rss"
            try:
                # Add full realistic Chrome User-Agent to prevent Cloudflare/Caddy block on Nitter
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)
                    items = root.findall('.//item')
                    rss_fetched = True
                    break
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                
        if not rss_fetched:
            print(f"Could not fetch RSS for {username} on any Nitter instance.")
            stats["errors"].append(f"RSS Fetch Error for {username}")
            continue
            
        for item in items:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            pubDate_str = item.find('pubDate').text if item.find('pubDate') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            
            if not link or not pubDate_str:
                continue
                
            # 1. Check if it's a video
            if ">Video<" not in desc and "Video" not in desc:
                continue
                
            # 2. Extract tweet ID and check history
            try:
                # Link is usually https://nitter.net/username/status/123456789#m
                tweet_id = link.split("/status/")[1].split("#")[0].split("?")[0]
            except Exception:
                continue
                
            # 3. Check exact post time
            try:
                post_time = parsedate_to_datetime(pubDate_str)
                if post_time.tzinfo is None:
                    post_time = post_time.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"Error parsing date {pubDate_str}: {e}")
                continue
                
            if post_time < time_limit:
                # Since RSS is chronological, if we hit an old one, we can stop checking this profile.
                print(f"Post {tweet_id} is older than 24 hours. Moving to next profile.")
                break
                
            # It is a recent video
            stats["new_videos_found"] += 1
            
            if tweet_id in history:
                print(f"Video {tweet_id} already in history, skipping...")
                stats["videos_skipped"] += 1
                continue
                
            original_tweet_url = f"https://x.com/{username}/status/{tweet_id}"
            valid_videos.append({
                "tweet_id": tweet_id,
                "url": original_tweet_url,
                "post_time": post_time
            })
            
    print("--------------------------------------------------")
    if not valid_videos:
        print("No new valid videos found across all profiles within the last 24 hours.")
        return None, None, None, None, None, stats
        
    # Sort valid videos by post_time (oldest first) to ensure chronological uploading
    valid_videos.sort(key=lambda x: x["post_time"])
    
    for video in valid_videos:
        tweet_id = video["tweet_id"]
        original_tweet_url = video["url"]
        
        print(f"Selected valid NEW video: {original_tweet_url}")
        
        # Log Aspect Ratio details
        try:
            print(f"Checking aspect ratio for {original_tweet_url}...")
            ydl_opts_meta = {
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(original_tweet_url, download=False)
            
            width = info.get('width')
            height = info.get('height')
            
            if not width or not height:
                formats = info.get('formats', [])
                for f in formats:
                    if f.get('width') and f.get('height'):
                        width = f.get('width')
                        height = f.get('height')
                        break
            
            if width and height:
                aspect_ratio = width / height
                print(f"Metadata - Resolution: {width}x{height}, Aspect Ratio: {aspect_ratio:.4f}")
                print("Proceeding to download. Layout will be formatted to 9:16 by the editor.")
            else:
                print("Could not determine aspect ratio. Proceeding to download anyway.")
        except Exception as e:
            print(f"Error checking aspect ratio: {e}")
            stats["errors"].append(f"Aspect Ratio check error: {str(e)}")
            
        # Use yt-dlp to download it
        try:
            os.makedirs('workspace', exist_ok=True)
            filename = "workspace/raw_video.mp4"
            if os.path.exists(filename):
                os.remove(filename)
                
            print(f"Downloading with yt-dlp...")
            with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                info = ydl.extract_info(original_tweet_url, download=True)
                clean_title = info.get('title', f"Twitter Video {tweet_id}")
                
            meta = {
                "title": clean_title,
                "source_url": original_tweet_url,
                "video_id": tweet_id
            }
            with open("workspace/meta.json", "w") as f:
                json.dump(meta, f)
                
            save_to_history(tweet_id)
            stats["videos_downloaded"] += 1
            return filename, clean_title, tweet_id, original_tweet_url, original_tweet_url, stats
            
        except Exception as e:
            print(f"Error downloading {original_tweet_url}: {e}")
            stats["errors"].append(f"Download Error for {original_tweet_url}: {str(e)}")
            # If download fails, try the next video in the queue
            continue

    print("Failed to download any of the found videos.")
    return None, None, None, None, None, stats

def run_downloader():
    print("Starting Agent 1: X (Twitter) Downloader")
    os.makedirs('workspace', exist_ok=True)

    # Optional forced video: if X_FORCE_VIDEO_URL is set, download that exact
    # video (bypassing history and the 24h freshness window) so any specific
    # tweet can be re-edited.
    force_url = os.environ.get("X_FORCE_VIDEO_URL", "").strip()
    if force_url:
        print(f"Forced video URL provided: {force_url}")
        try:
            import re
            m = re.search(r"status/(\d+)", force_url)
            tweet_id = m.group(1) if m else None
        except Exception:
            tweet_id = None

        filename = "workspace/raw_video.mp4"
        if os.path.exists(filename):
            os.remove(filename)
        try:
            with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                info = ydl.extract_info(force_url, download=True)
                clean_title = info.get('title', f"Twitter Video {tweet_id}")
                resolved_id = str(info.get('id') or tweet_id)
            meta = {
                "title": clean_title,
                "source_url": force_url,
                "video_id": resolved_id
            }
            with open("workspace/meta.json", "w") as f:
                json.dump(meta, f)
            if resolved_id:
                save_to_history(resolved_id)
            stats = {
                "profiles_scanned": 0,
                "new_videos_found": 1,
                "videos_downloaded": 1,
                "videos_skipped": 0,
                "errors": []
            }
            video_data = {
                "id": resolved_id,
                "tweet_id": resolved_id,
                "title": clean_title,
                "source_url": force_url,
                "local_path": filename,
                "status": "DOWNLOADED"
            }
            print("Agent 1 completed successfully (forced video).")
            return video_data, stats
        except Exception as e:
            print(f"Error downloading forced video {force_url}: {e}")
            stats = {"profiles_scanned": 0, "new_videos_found": 0, "videos_downloaded": 0, "videos_skipped": 0, "errors": [f"Forced download error: {str(e)}"]}
            return None, stats

    result = search_and_download_latest_video()
    if result and len(result) == 6:
        video_path, title, tweet_id, source_url, video_url, stats = result
    else:
        video_path, title, tweet_id, source_url, video_url, stats = None, None, None, None, None, {}
        
    if video_path and os.path.exists(video_path):
        video_data = {
            "id": tweet_id,
            "tweet_id": tweet_id,
            "title": title,
            "source_url": source_url,
            "local_path": video_path,
            "status": "DOWNLOADED"
        }
        print("Agent 1 completed successfully.")
        return video_data, stats
    
    print("No video downloaded.")
    return None, stats

if __name__ == "__main__":
    run_downloader()
