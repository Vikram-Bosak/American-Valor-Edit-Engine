import os
import sys
import json
import math
import wave
import struct
import random
import subprocess
import urllib.request
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


def _get_client():
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return None
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)


# ──────────────────────────────────────────────────────────────
# ASS Subtitle helpers (ported from funny-video-eddit-agent)
# ──────────────────────────────────────────────────────────────
def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int(round((secs - int(secs)) * 100))
    if centiseconds == 100:
        centiseconds = 99
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def generate_ass_subtitles(voiceover_path: str, ass_path: str):
    from faster_whisper import WhisperModel
    print("Transcribing voiceover with word-level timestamps using Whisper (tiny/cpu)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(voiceover_path, word_timestamps=True)

    words = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                words.append({
                    "start": w.start,
                    "end": w.end,
                    "text": w.word.strip().upper()  # ALL CAPS style
                })

    if not words:
        print("No words detected in voiceover to generate subtitles.")
        return False

    # Group words into short 2-word phrases or 1.0 second max duration
    phrases = []
    current_phrase = []
    phrase_start = 0.0

    for w in words:
        if not current_phrase:
            phrase_start = w["start"]
        current_phrase.append(w)

        duration = w["end"] - phrase_start
        if len(current_phrase) >= 2 or duration >= 1.0:
            phrases.append(current_phrase)
            current_phrase = []

    if current_phrase:
        phrases.append(current_phrase)

    # Write ASS file with Shorts formatting
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("PlayResX: 720\n")
        f.write("PlayResY: 1280\n\n")

        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial Black,64,&H00FFFFFF,&H00000000,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,1,2,10,10,580,1\n\n")

        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        for phrase in phrases:
            start_str = format_time(phrase[0]["start"])
            end_str = format_time(phrase[-1]["end"])
            phrase_text = " ".join([w["text"] for w in phrase])
            f.write(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{phrase_text}\n")

    print(f"ASS subtitles generated at: {ass_path}")
    return True


# ──────────────────────────────────────────────────────────────
# Red Hook Circle (ported from funny-video-eddit-agent)
# ──────────────────────────────────────────────────────────────
def draw_hook_circle(video_path: str, output_path: str) -> bool:
    import cv2
    import numpy as np
    import ffmpeg
    from ultralytics import YOLO

    print("Detecting subject head to draw red hook circle...")

    try:
        probe = ffmpeg.probe(video_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if not video_stream:
            print("No video stream found in temp video.")
            return False
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        r_frame_rate = video_stream.get('r_frame_rate', '30/1')
        num, den = map(int, r_frame_rate.split('/'))
        fps = num / den if den != 0 else 30.0
    except Exception as e:
        print(f"Failed to probe temp video: {e}")
        return False

    ffmpeg_read_cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-f", "image2pipe",
        "-pix_fmt", "bgr24",
        "-vcodec", "rawvideo",
        "-"
    ]
    read_process = subprocess.Popen(ffmpeg_read_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    circle_duration_frames = int(fps * 1.5)  # 1.5 seconds

    try:
        yolo_model = YOLO('yolov8n.pt')
    except Exception as e:
        print(f"Could not load YOLO for tracking: {e}")
        yolo_model = None

    last_known_circle = None
    frame_idx = 0
    frame_size = width * height * 3

    while True:
        in_bytes = read_process.stdout.read(frame_size)
        if not in_bytes or len(in_bytes) < frame_size:
            break

        frame = np.frombuffer(in_bytes, np.uint8).reshape((height, width, 3))
        frame = frame.copy()

        if frame_idx < circle_duration_frames:
            cx, cy, r = None, None, None
            if yolo_model:
                try:
                    results = yolo_model(frame, verbose=False)
                    best_person = None
                    max_area = 0

                    for r_item in results:
                        boxes = r_item.boxes
                        for box in boxes:
                            if int(box.cls[0]) == 0:  # person
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                area = (x2 - x1) * (y2 - y1)
                                if area > max_area:
                                    max_area = area
                                    best_person = (x1, y1, x2, y2)

                    if best_person:
                        x1, y1, x2, y2 = best_person
                        cx = int((x1 + x2) / 2)
                        cy = int(y1 + (y2 - y1) * 0.15)
                        r = int((x2 - x1) * 0.28)
                        last_known_circle = (cx, cy, r)
                except Exception:
                    pass

            if cx is None and last_known_circle is not None:
                cx, cy, r = last_known_circle

            if cx is None:
                cx = int(width / 2)
                cy = int(height * 0.35)
                r = int(width * 0.18)

            cv2.circle(frame, (cx, cy), r, (0, 0, 255), 4)

        process.stdin.write(frame.tobytes())
        frame_idx += 1

    read_process.stdout.close()
    read_process.wait()
    process.stdin.close()
    process.wait()

    print(f"Successfully processed {frame_idx} frames and added red hook circle to video start.")
    return True


# ──────────────────────────────────────────────────────────────
# Sound Effect synthesis (ported from funny-video-eddit-agent)
# ──────────────────────────────────────────────────────────────
def generate_sfx(sfx_type, filepath):
    sample_rate = 44100

    if sfx_type == "ding":
        duration = 0.5
        num_samples = int(duration * sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            freq = 1000.0
            val = math.sin(2 * math.pi * freq * t) * math.exp(-6 * t)
            val = int(val * 32767)
            data.extend(struct.pack('<h', val))

    elif sfx_type == "boing":
        duration = 0.8
        num_samples = int(duration * sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            freq = 200 + 300 * abs(math.sin(2 * math.pi * 3 * t))
            val = math.sin(2 * math.pi * freq * t) * (1.0 - t / duration)
            val = int(val * 32767)
            data.extend(struct.pack('<h', val))

    elif sfx_type == "whoosh":
        duration = 0.6
        num_samples = int(duration * sample_rate)
        data = bytearray()
        random.seed(42)
        for i in range(num_samples):
            t = i / sample_rate
            env = math.sin(math.pi * t / duration)
            val = (random.random() * 2.0 - 1.0) * env * 0.5
            val = int(val * 32767)
            data.extend(struct.pack('<h', val))

    elif sfx_type == "alert":
        duration = 0.4
        num_samples = int(duration * sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            if t < 0.15 or (t > 0.22 and t < 0.37):
                freq = 1200.0
                val = math.sin(2 * math.pi * freq * t)
            else:
                val = 0
            val = int(val * 32767 * 0.7)
            data.extend(struct.pack('<h', val))

    elif sfx_type == "fail":
        duration = 1.0
        num_samples = int(duration * sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            freq = 300.0 - 150.0 * (t / duration)
            val = math.sin(2 * math.pi * freq * t) * (1.0 - t / duration)
            val = int(val * 32767 * 0.8)
            data.extend(struct.pack('<h', val))

    else:  # "laugh"
        duration = 1.2
        num_samples = int(duration * sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            pulse = abs(math.sin(2 * math.pi * 5 * t))
            freq = 180.0 + 40.0 * pulse
            val = math.sin(2 * math.pi * freq * t) * pulse * (1.0 - t / duration)
            val = int(val * 32767 * 0.6)
            data.extend(struct.pack('<h', val))

    with wave.open(filepath, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(data)

    return filepath


# ──────────────────────────────────────────────────────────────
# Video Analysis (ported from funny-video-eddit-agent video_analysis_agent)
# ──────────────────────────────────────────────────────────────
def analyze_video_content(video_path: str) -> dict:
    result = {
        "transcript": "",
        "translation": "",
        "duration": 0.0,
        "crop_start": 0.0,
        "crop_duration": 59.0,
        "sound_effects": [],
        "summary": "No visual summary available.",
        "ocr_text": "",
        "scene_analysis": [],
    }

    if not os.path.exists(video_path):
        print(f"Video path {video_path} not found.")
        return result

    print(f"Starting Local AI Video Analysis for {video_path}...")

    try:
        import cv2
        # Duration
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps if fps > 0 else 0
        cap.release()
        result["duration"] = video_duration
        print(f"Video duration: {video_duration:.2f} seconds")

        # Scene detection
        try:
            from scenedetect import detect, ContentDetector
            scene_list = detect(video_path, ContentDetector())
            scenes = []
            for i, scene in enumerate(scene_list):
                scenes.append({
                    "scene_num": i + 1,
                    "start_time": scene[0].get_seconds(),
                    "end_time": scene[1].get_seconds()
                })
            result["scene_analysis"] = scenes[:20]
            print(f"Detected {len(scenes)} scenes.")
        except Exception as e:
            print(f"Scene detection skipped: {e}")

        # Transcription
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, info = model.transcribe(video_path, beam_size=5)
            transcript = ""
            for segment in segments:
                transcript += f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}\n"
            result["transcript"] = transcript.strip() or "No dialogue detected."
        except Exception as e:
            print(f"Transcription skipped: {e}")
            result["transcript"] = "No dialogue detected."

        client = _get_client()

        # Determine crop window (max 59 seconds)
        crop_start = 0.0
        crop_duration = min(59.0, video_duration)

        if video_duration > 59.0 and client:
            select_prompt = f"""
            You are an expert social media editor. Analyze this video timeline data and select the single most engaging, action-packed continuous portion of the video.
            The selected portion MUST be at most 59 seconds long.

            Total Video Duration: {video_duration:.2f} seconds

            Timeline and Scene Analysis:
            {json.dumps(result['scene_analysis'], indent=2)}

            Transcript with Timestamps:
            {result['transcript'][:2000]}

            Identify the start time and duration of the best engaging segment to crop.
            Return ONLY a valid JSON object with keys "start_time" and "duration" (in seconds as floats/integers). Example response:
            {{"start_time": 15.2, "duration": 45.0}}
            Do not output any explanation or extra text.
            """
            try:
                completion = client.chat.completions.create(
                    model="meta/llama-3.1-70b-instruct",
                    messages=[{"role": "user", "content": select_prompt}],
                    temperature=0.5,
                    max_tokens=1024,
                    stream=False
                )
                llm_response = completion.choices[0].message.content.strip()
                clean_json = llm_response.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                crop_start = float(data.get("start_time", 0.0))
                crop_duration = float(data.get("duration", 59.0))
                if crop_start < 0 or crop_start >= video_duration:
                    crop_start = 0.0
                if crop_duration <= 0 or crop_duration > 59.0 or (crop_start + crop_duration) > video_duration:
                    crop_duration = min(59.0, video_duration - crop_start)
            except Exception as e:
                print(f"Failed to parse AI crop selection, defaulting to first 59s: {e}")
                crop_start = 0.0
                crop_duration = min(59.0, video_duration)

        result["crop_start"] = crop_start
        result["crop_duration"] = crop_duration
        print(f"Selected crop window: start={crop_start:.2f}s, duration={crop_duration:.2f}s")

        # Plan sound effects
        if client:
            sfx_prompt = f"""
            You are an expert video editor. Analyze this video timeline data and plan exactly 2 to 4 appropriate sound effects to add to the video to make it engaging and energetic.

            Selected Crop Window: start={crop_start:.2f}s, duration={crop_duration:.2f}s (all sound effect timestamps MUST be between 0.0 and {crop_duration:.2f}s relative to the start of the crop window).

            Timeline and Scene Analysis:
            {json.dumps(result['scene_analysis'], indent=2)}

            Transcript with Timestamps:
            {result['transcript'][:2000]}

            Available sound effect types:
            - "boing" (funny bounce/action/surprise)
            - "whoosh" (fast movement/scene change)
            - "ding" (success/bright idea/ding)
            - "alert" (warning/alarm/shock)
            - "fail" (funny failure/falling/slip)
            - "laugh" (man chuckling/giggling)

            Identify 2 to 4 key moments in the cropped video where these sound effects would fit best.
            Return ONLY a valid JSON list of sound effect objects, where each object has "time_offset" (seconds from crop start as float) and "type" (one of the available types). Example response:
            [
              {{"time_offset": 3.5, "type": "whoosh"}},
              {{"time_offset": 12.0, "type": "ding"}}
            ]
            Do not output any explanation or extra text.
            """
            sound_effects = []
            try:
                sfx_response = client.chat.completions.create(
                    model="meta/llama-3.1-70b-instruct",
                    messages=[{"role": "user", "content": sfx_prompt}],
                    temperature=0.5,
                    max_tokens=1024,
                    stream=False
                ).choices[0].message.content.strip()
                clean_sfx_json = sfx_response.replace("```json", "").replace("```", "").strip()
                sound_effects = json.loads(clean_sfx_json)
                valid_types = {"boing", "whoosh", "ding", "alert", "fail", "laugh"}
                sound_effects = [
                    sfx for sfx in sound_effects
                    if isinstance(sfx, dict)
                    and 0.0 <= float(sfx.get("time_offset", -1)) <= crop_duration
                    and sfx.get("type") in valid_types
                ]
            except Exception as e:
                print(f"Failed to plan sound effects with AI: {e}")
                sound_effects = [
                    {"time_offset": float(f"{crop_duration * 0.3:.2f}"), "type": "whoosh"},
                    {"time_offset": float(f"{crop_duration * 0.7:.2f}"), "type": "ding"}
                ]
            result["sound_effects"] = sound_effects
            print(f"Planned sound effects: {sound_effects}")

        # Summary via LLM
        if client:
            summary_prompt = f"""
            You are an AI video summarizer.
            Analyze this video content and write a short, clear, and comprehensive summary (2-3 sentences) in English describing the actual events, actions, and settings shown in the video.

            Dialogue Transcript: {result['transcript'][:2000]}
            """
            try:
                completion = client.chat.completions.create(
                    model="meta/llama-3.1-70b-instruct",
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.5,
                    max_tokens=1024,
                    stream=False
                )
                result["summary"] = completion.choices[0].message.content.strip()
            except Exception as e:
                print(f"Summarization failed: {e}")

    except Exception as e:
        print(f"Error during video analysis: {e}")

    return result


# ──────────────────────────────────────────────────────────────
# Script writing (ported from funny-video-eddit-agent script_writer_agent)
# ──────────────────────────────────────────────────────────────
def write_voiceover_script(analysis: dict, task: dict = None) -> str:
    client = _get_client()
    task = task or {}
    title = task.get("title", "")
    transcript = analysis.get("transcript", "No spoken words detected.")
    summary = analysis.get("summary", "No visual summary available.")

    if not client:
        print("NVIDIA_API_KEY not found. Generating fallback script.")
        return "Witness the power and precision of the United States Armed Forces. Watch until the end for an incredible display of strength and dedication."

    has_voice = transcript and transcript != "No dialogue detected."

    prompt = f"""
    You are an expert, highly engaging social media storyteller for a USA Military and Army fan page.
    Your task is to write a short, epic, and energetic voiceover script for a military video.

    CRITICAL RULE: DO NOT write a dry description of the video (e.g. do not say "In this video we see soldiers doing X"). Instead, write an engaging STORY, commentary, or narrative that hypes up the viewer with patriotism, power, and respect.

    SCRIPT WRITING RULES based on Audio:
    """

    if has_voice:
        prompt += f"""
    - The original video CONTAINS Spoken Content / Voiceover.
    - Here is the Transcript of the original voice: "{transcript}"
    - You MUST base your new script on this original voice content. Retain its core message or information, but rewrite it to be far more engaging, punchy, and structured for viral retention.
        """
    else:
        prompt += f"""
    - The original video DOES NOT contain any spoken content (it is silent or has only background music).
    - Here is the Visual Summary of the video: "{summary}"
    - You MUST write an engaging story based entirely on these visual actions, detected objects, and events shown in the video.
        """

    prompt += f"""
    Use the following narrative structure:
    1. Setup/Context: Introduce the unit, the mission, or the starting situation.
    2. Build-up/Suspense: Describe the action or the demonstration of power.
    3. The Climax/Moment: Focus on the most impressive, jaw-dropping moment.
    4. Emotional Reaction: Pride, respect, and patriotism for our armed forces.

    Here is the analysis of the video content:
    - Video Title: {title}
    - Visual Scene Summary: {summary}
    - Spoken Words / Original Dialogue: {transcript}

    STORYTELLING GUIDELINES:
    1. The story MUST align tightly with the actual visual content. Do NOT hallucinate unrelated characters or battles.
    2. Write only the spoken voiceover in English. Do NOT include stage directions, bracketed instructions, speaker names, or video descriptions. Only output the exact words to be read.
    3. Keep the script under 59 seconds (between 40 and 100 words maximum).
    4. Never mention this is AI-generated. Never output refusal messages.
    """

    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            top_p=0.95,
            max_tokens=1024,
            stream=False
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during script generation: {e}")
        return "Witness the power and precision of the United States Armed Forces. Watch until the end for an incredible display of strength and dedication."


# ──────────────────────────────────────────────────────────────
# Voiceover generation (ported from funny-video-eddit-agent voice_generation_agent)
# ──────────────────────────────────────────────────────────────
def generate_voiceover(script: str, video_id: str) -> str:
    print("Generating voiceover using Kokoro TTS...")

    os.makedirs("audio", exist_ok=True)
    voiceover_path = f"audio/{video_id}_voice.wav"

    try:
        model_file = "kokoro-v1.0.onnx"
        voices_file = "voices-v1.0.bin"

        if not os.path.exists(model_file):
            print(f"Downloading {model_file} (approx. 82MB)...")
            url = f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{model_file}"
            urllib.request.urlretrieve(url, model_file)

        if not os.path.exists(voices_file):
            print(f"Downloading {voices_file} (approx. 20MB)...")
            url = f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{voices_file}"
            urllib.request.urlretrieve(url, voices_file)

        from kokoro_onnx import Kokoro
        import soundfile as sf

        print("Initializing Kokoro TTS model...")
        kokoro = Kokoro(model_file, voices_file)

        selected_voice = "af_sarah"
        lang_code = "en-us"

        print(f"Synthesizing speech using flagship realistic female voice: {selected_voice}")
        samples, sample_rate = kokoro.create(script, voice=selected_voice, speed=1.0, lang=lang_code)

        sf.write(voiceover_path, samples, sample_rate)
        print(f"Voice generation complete: {voiceover_path}")
        return voiceover_path

    except Exception as e:
        print(f"Error during voice generation: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Main AI Editing Pipeline
# ──────────────────────────────────────────────────────────────
def process_video_with_ai(input_path: str, logo_path: str, output_path: str, task: dict = None) -> tuple:
    """
    Combines American-Valor branding frame with funny-video-eddit-agent AI editing skills:
    voiceover, ALL-CAPS subtitles, sound effects, and red hook circle.
    Returns (edited_path, hook_line).
    """
    task = task or {}
    video_id = task.get("id", "video")
    print(f"Starting AI-enhanced editing for {input_path}...")

    os.makedirs("workspace", exist_ok=True)
    os.makedirs("temp", exist_ok=True)

    temp_cropped = f"workspace/{video_id}_cropped.mp4"
    temp_circle = f"workspace/{video_id}_circle.mp4"
    temp_branded = f"workspace/{video_id}_branded.mp4"
    ass_path = f"temp/{video_id}_subs.ass"
    voiceover_path = None

    try:
        # 1. Analyze video content
        analysis = analyze_video_content(input_path)
        crop_start = analysis.get("crop_start", 0.0)
        crop_duration = analysis.get("crop_duration", 59.0)

        # 2. Crop to 9:16 within selected window
        print(f"Cropping video starting at {crop_start:.2f}s for {crop_duration:.2f}s...")
        has_audio = False
        try:
            import ffmpeg
            probe = ffmpeg.probe(input_path)
            has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
        except Exception as e:
            print(f"Failed to probe video audio: {e}")

        crop_command = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ss", str(crop_start),
            "-t", str(crop_duration),
            "-vf", "crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0,setpts=PTS-STARTPTS",
            "-c:v", "libx264"
        ]
        if has_audio:
            crop_command.extend(["-c:a", "aac"])
        else:
            crop_command.extend(["-an"])
        crop_command.append(temp_cropped)
        subprocess.run(crop_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Draw red hook circle
        circle_done = draw_hook_circle(temp_cropped, temp_circle)
        if not circle_done or not os.path.exists(temp_circle):
            if os.path.exists(temp_circle):
                os.remove(temp_circle)
            os.rename(temp_cropped, temp_circle)

        # 4. Write script + generate voiceover (best-effort)
        script = write_voiceover_script(analysis, task)
        voiceover_path = generate_voiceover(script, video_id)

        # 5. Apply American-Valor branding layout (logo + headline + story)
        from editor.advanced_editor import edit_3_4_custom_layout_template
        headline = task.get("title", "AMERICAN VALOR")
        story = analysis.get("summary", "")
        source_credit = task.get("source", "")
        template_used = edit_3_4_custom_layout_template(
            temp_circle,
            logo_path,
            temp_branded,
            headline,
            story,
            source_credit,
            safety_actions=[]
        )

        # 6. Generate subtitles from voiceover
        subs_success = False
        if voiceover_path and os.path.exists(voiceover_path):
            subs_success = generate_ass_subtitles(voiceover_path, ass_path)

        # 7. Generate sound effect files
        sfx_files = []
        sound_effects = analysis.get("sound_effects", [])
        for i, sfx in enumerate(sound_effects):
            sfx_path = f"temp/{video_id}_sfx_{i}.wav"
            try:
                generate_sfx(sfx.get("type", "ding"), sfx_path)
                sfx_files.append({"path": sfx_path, "offset": float(sfx.get("time_offset", 0))})
            except Exception as e:
                print(f"Failed to generate SFX {i}: {e}")

        # 8. Final mix: subtitles + voiceover + original audio swap + sound effects
        T = crop_duration
        command = ["ffmpeg", "-y"]

        inputs = ["-stream_loop", "-1", "-i", temp_branded]
        has_voice_input = False
        if voiceover_path and os.path.exists(voiceover_path):
            inputs.extend(["-i", voiceover_path])
            has_voice_input = True
        for s in sfx_files:
            inputs.extend(["-i", s["path"]])
        command.extend(inputs)

        filter_parts = []
        video_output_label = "0:v:0"
        if subs_success:
            escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(f"[0:v:0]subtitles='{escaped_ass}'[v_subbed]")
            video_output_label = "[v_subbed]"

        audio_parts = []
        voice_idx = 1
        if has_voice_input:
            if has_audio and T >= 5.0:
                S_orig = (T - 5.0) / 2.0
                E_orig = S_orig + 5.0
                S_orig_ms = int(S_orig * 1000)
                E_orig_ms = int(E_orig * 1000)

                filter_parts.append(f"[{voice_idx}:a]atrim=end={S_orig:.2f},asetpts=PTS-STARTPTS[tts1]")
                filter_parts.append(f"[{voice_idx}:a]atrim=start={S_orig:.2f},asetpts=PTS-STARTPTS,adelay={E_orig_ms}|{E_orig_ms}[tts2]")
                filter_parts.append(f"[0:a]atrim=start={S_orig:.2f}:end={E_orig:.2f},asetpts=PTS-STARTPTS,adelay={S_orig_ms}|{S_orig_ms}[orig_mid]")
                audio_parts = ["[tts1]", "[orig_mid]", "[tts2]"]
            else:
                filter_parts.append(f"[{voice_idx}:a]asetpts=PTS-STARTPTS[tts_main]")
                audio_parts = ["[tts_main]"]

        sfx_idx = voice_idx + (1 if has_voice_input else 0)
        for i, s in enumerate(sfx_files):
            offset_ms = int(s["offset"] * 1000)
            filter_parts.append(f"[{sfx_idx + i}:a]asetpts=PTS-STARTPTS,adelay={offset_ms}|{offset_ms}[sfx{i}]")
            audio_parts.append(f"[sfx{i}]")

        if audio_parts:
            filter_parts.append("".join(audio_parts) + f"amix=inputs={len(audio_parts)}:normalize=0[final_audio]")
            command.extend(["-filter_complex", ";".join(filter_parts)])
            command.extend(["-map", video_output_label, "-map", "[final_audio]"])
        else:
            if filter_parts:
                command.extend(["-filter_complex", ";".join(filter_parts)])
            command.extend(["-map", video_output_label])

        command.extend([
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-t", str(T),
            output_path
        ])

        res = subprocess.run(command, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FFmpeg failed with exit code {res.returncode}")
            print(f"FFmpeg stderr: {res.stderr[-2000:]}")
            # Fallback: just copy the branded video
            import shutil
            if os.path.exists(temp_branded):
                shutil.copy(temp_branded, output_path)
        else:
            print(f"Final video created: {output_path}")

        # Cleanup temp files
        for f in [temp_cropped, temp_circle, temp_branded]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        return output_path, headline

    except Exception as e:
        print(f"AI editing failed: {e}")
        import shutil
        if os.path.exists(input_path) and not os.path.exists(output_path):
            shutil.copy(input_path, output_path)
            print("Fell back to copying raw video.")
        return output_path, task.get("title", "AMERICAN VALOR")


if __name__ == "__main__":
    dummy_task = {"id": "test_123", "title": "US Army Paratrooper Jump", "source": "USArmy"}
    process_video_with_ai("assets/vertical_dummy.mp4", "assets/custom_logo.png", "temp/ai_edit.mp4", dummy_task)
