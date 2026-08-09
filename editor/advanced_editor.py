import os
import sys
import subprocess
import json
import textwrap
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_video_dimensions(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data['streams'][0]
        return int(stream['width']), int(stream['height'])
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, KeyError, Exception) as e:
        print(f"Error getting video dimensions: {e}")
        return 1920, 1080  # fallback to horizontal

def edit_3_4_custom_layout_template(input_path: str, logo_path: str, output_path: str, headline: str = "VIRAL NEWS!", story: str = "", source_credit: str = "", safety_actions: list = None):
    print("Applying Custom Native Facebook Layout Template...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    from src.common.ui_frame_generator import generate_ui_frame
    frame_path = "temp/ui_frame.png"
    generate_ui_frame(frame_path, source_credit, headline, story, width=1080, height=1920)
    
    safety_actions = safety_actions or []
    
    # Check if horizontal flip is needed to avoid visual copyright checks
    flip_filter = "hflip," if "flip_horizontal" in safety_actions else ""
    
    # 1080x1920 Canvas (9:16). Video takes 1070x1680 at x=5, y=230.
    # We apply the original zoom, speed, and color grading effects.
    filter_complex = (
        f"[0:v]{flip_filter}setpts=PTS/1.05,scale=1070:1680:force_original_aspect_ratio=increase,crop=1070:1680,eq=contrast=1.05:brightness=0.02:saturation=1.15:gamma=1.0,unsharp=5:5:0.5[vid_processed];"
        "[vid_processed]pad=1080:1920:5:230:color=white[bg];"
        "[bg][1:v]overlay=0:0[outv]"
    )
    
    has_audio = False
    try:
        out = subprocess.check_output(
            ["ffprobe", "-i", input_path, "-show_streams", "-select_streams", "a", "-loglevel", "error"],
            timeout=30
        ).decode()
        if out.strip(): has_audio = True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Audio stream detection failed (assuming no audio): {e}")

    cmd = ["ffmpeg", "-y", "-i", input_path, "-i", frame_path]

    # Audio volume boost logic (no BGM) - respect mute_audio action
    if has_audio and "mute_audio" not in safety_actions:
        filter_complex += ";[0:a]volume=1.5,loudnorm=I=-16:TP=-1.5:LRA=11[outa]"
        cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]"])
    else:
        cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]"])

    cmd.extend([
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-t", "59",
        output_path
    ])
    subprocess.run(cmd, check=True, timeout=120)
    return "9:16 Custom Layout Template"

def process_video_dynamically(input_path: str, logo_path: str, output_path: str, task: dict = None):
    from src.common.seo_generator import analyze_video_for_editing
    
    task = task or {}
    print(f"Analyzing {input_path}...")
    width, height = get_video_dimensions(input_path)
    print(f"Detected Dimensions: {width}x{height}")
    
    # Stage 1: AI Contextual Analysis
    import datetime
    edit_start_time = datetime.datetime.utcnow()
    
    print("Requesting metadata from Context-Aware LLM Stage 1...")
    analysis = analyze_video_for_editing(task)
    print(f"Analysis Output: {json.dumps(analysis)}")
    
    headline = analysis.get("short_headline", "VIRAL NEWS!")
    story = analysis.get("story", analysis.get("hook_line", ""))
    source_credit = task.get("source", "")
    
    # Save full analysis state for Uploader Phase
    os.makedirs("temp", exist_ok=True)
    task_id = task.get("id", "default")
    with open(f"temp/state_upload_{task_id}.json", "w") as f:
        full_context = dict(task)
        full_context.update(analysis)
        json.dump(full_context, f, indent=4)
        
    safety_actions = analysis.get("safety_actions", [])
    print(f"Applying safety actions: {safety_actions}")
    
    # We pass safety actions to modify parameters
    template_used = edit_3_4_custom_layout_template(
        input_path, 
        logo_path, 
        output_path, 
        headline, 
        story, 
        source_credit,
        safety_actions=safety_actions
    )
        
    print("Video editing completed!")
    
    edit_complete_time = datetime.datetime.utcnow()
    file_name = os.path.basename(output_path)
    
    message_text = (
        f"🎬 **EDITING REPORT**\n\n"
        f"**Workflow Name:** American Valor Pipeline\n"
        f"**Edit Start Time:** {edit_start_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**Edit Complete Time:** {edit_complete_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**File Name:** {file_name}\n"
        f"**Applied Template:** {template_used}\n"
        f"**Safety Actions Applied:** {', '.join(safety_actions) if safety_actions else 'None'}\n"
        f"**Editing Status:** SUCCESS"
    )
    
    from src.common.discord import send_discord_message
    print("Sending Editing Status Report to Discord...")
    send_discord_message(message_text)
    
    print("Process finished. Returning local path for sequential processing.")
    
    return output_path, headline

if __name__ == "__main__":
    dummy_task = {"id": "test_123", "title": "US Army Paratrooper Jump", "source": "USArmy"}
    process_video_dynamically("assets/vertical_dummy.mp4", "assets/custom_logo.png", "temp/dynamic_edit.mp4", dummy_task)
