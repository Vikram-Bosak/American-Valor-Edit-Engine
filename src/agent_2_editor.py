import os
import sys
from datetime import datetime

# Add the root project directory to path so we can import editor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from editor.ai_editor import process_video_with_ai

def process_video(video_data):
    print("Starting Agent 2: Video Editor (Military Style + AI Editing Skills)")
    
    raw_video_path = video_data.get('local_path', "workspace/raw_video.mp4")
    title = video_data.get('title', 'Unknown Video')
    edited_video_path = f"workspace/edited_{video_data.get('id', 'video')}.mp4"
    
    if not os.path.exists(raw_video_path):
        print(f"Raw video not found at {raw_video_path}.")
        video_data["editing_status"] = "Failed"
        return video_data
        
    print(f"Processing video: {title}")
    
    try:
        # Use AI-enhanced editing (voiceover, subtitles, sound effects, red hook circle)
        # built on top of the American-Valor branding layout
        edited_path, hook_line = process_video_with_ai(
            raw_video_path, 
            'assets/custom_logo.png', 
            edited_video_path, 
            task=video_data
        )
        
        video_data["editing_status"] = "Success"
        video_data["seo_title"] = hook_line if hook_line else title
        video_data["edited_path"] = edited_path
        video_data["edit_time"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        
        # Cleanup raw video
        if os.path.exists(raw_video_path):
            os.remove(raw_video_path)
            
        return video_data
    except Exception as e:
        print(f"Editing failed: {e}")
        video_data["editing_status"] = "Failed"
        return video_data

if __name__ == "__main__":
    pass
