import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# Try to import Google GenAI
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Trending Military Keywords for SEO
# ──────────────────────────────────────────────────────────────────────────────
MILITARY_KEYWORDS = {
    "branches": [
        "US Army", "US Navy", "US Marine Corps", "USMC", "US Air Force", "US Coast Guard",
        "Space Force", "National Guard", "Special Forces", "Navy SEALs", "Green Berets", "Army Rangers",
    ],
    "equipment": [
        "F-35 Lightning", "M1 Abrams Tank", "A-10 Warthog", "Aircraft Carrier", "F-22 Raptor",
        "Apache Helicopter", "Black Hawk", "Destroyer", "Submarine", "Humvee", "CH-47 Chinook",
    ],
    "topics": [
        "military training", "tactical operations", "military drill", "basic training",
        "air show", "naval exercises", "combat simulation", "paratrooper jump",
        "weapons training", "military technology", "soldier tribute", "honor guard",
    ],
    "military_terms": [
        "military power", "operational readiness", "active duty", "special ops",
        "tactical maneuver", "precision strike", "military exercise", "force protection",
        "joint operations", "elite forces", "rapid deployment", "combat readiness",
    ],
    "emotional_hooks": [
        "incredible strength", "elite precision", "pure dedication", "inspiring tribute",
        "unmatched power", "military pride", "service and sacrifice", "jaw-dropping power",
        "patriotism", "heroic moments", "must watch military",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Trending Military Hashtags
# ──────────────────────────────────────────────────────────────────────────────
MILITARY_HASHTAGS = [
    "#USArmy", "#USNavy", "#USMC", "#USAirForce", "#Military", "#Army",
    "#Marines", "#NavySEALs", "#SpecialForces", "#Tactical", "#Aviation",
    "#FighterJet", "#Navy", "#AirForce", "#Veterans", "#MilitaryLife",
    "#USArmyReserve", "#NationalGuard", "#Patriot", "#USA", "#Soldiers",
    "#MilitaryPower", "#EliteForces", "#CoastGuard", "#SpaceForce",
    "#Tank", "#Helicopter", "#F35", "#Warthog", "#Raptor",
]


# ──────────────────────────────────────────────────────────────────────────────
# Client & Gemini helpers (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def _get_client():
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )

def _extract_gemini_video_context(video_path: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not HAS_GEMINI or not gemini_key or not video_path or not os.path.exists(video_path):
        return ""
        
    print(f"Deep Video Analysis: Uploading {video_path} to Gemini 1.5 Flash...")
    try:
        client = genai.Client(api_key=gemini_key)
        video_file = client.files.upload(file=video_path)
        
        # Wait for video processing
        while video_file.state.name == "PROCESSING":
            print("Waiting for video processing...")
            time.sleep(5)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            print("Gemini Video processing failed.")
            return ""
            
        prompt = "Analyze this video completely. 1) Describe exactly what is happening visually. 2) If it is a meme, edit, or specific historical event (e.g., a war edit masked as a military video), explicitly state what the true hidden subject is. 3) Read any on-screen text (OCR). 4) Transcribe any spoken words. Be extremely accurate."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )
        
        # Cleanup file from Gemini servers
        client.files.delete(name=video_file.name)
        
        print("Gemini Context Extraction Successful.")
        return response.text
    except Exception as e:
        print(f"Error extracting deep video context: {e}")
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 – Analyze video for editing (improved prompts)
# ──────────────────────────────────────────────────────────────────────────────
def analyze_video_for_editing(context: dict) -> dict:
    """
    Stage 1: Analyzes video context and generates Hook Line, Short Headline, Overlay Text, and Category.
    """
    client = _get_client()
    original_title = context.get('title', '')
    fallback = {
        "category": "Highlight",
        "short_headline": (
            original_title[:35] + "..."
            if len(original_title) > 35
            else (original_title if original_title else "ELITE MILITARY MOMENT 🇺🇸🦅")
        ),
        "story": (
            original_title
            if original_title
            else "An incredible look at the dedication, power, and precision of our armed forces. Watch till the end to see the full strength in action! 🇺🇸"
        ),
        "overlay_text": "🇺🇸 MUST-SEE MILITARY MOMENT",
        "safety_flags": [],
        "safety_actions": []
    }
    
    if not client:
        print("Warning: NVIDIA_API_KEY not found. Using fallback analysis.")
        return fallback
        
    # Check if we should extract deep context via Gemini
    deep_context = ""
    local_path = context.get('local_path')
    if local_path and os.getenv("GEMINI_API_KEY"):
        deep_context = _extract_gemini_video_context(local_path)
        if deep_context:
            context['deep_context'] = deep_context  # Save for stage 2
            
    # Build context snippet for trending keywords injection
    trending_snippet = (
        f"\nTrending keyword pools to weave in naturally: "
        f"Branches: {', '.join(MILITARY_KEYWORDS['branches'][:6])}; "
        f"Equipment: {', '.join(MILITARY_KEYWORDS['equipment'][:6])}; "
        f"Terms: {', '.join(MILITARY_KEYWORDS['military_terms'][:6])}; "
        f"Hooks: {', '.join(MILITARY_KEYWORDS['emotional_hooks'][:5])}."
    )

    prompt = f"""You are a world-class USA Military and Army social media strategist and content safety auditor.
Analyze the video context and metadata carefully to ensure absolute compliance with Facebook's Community Standards and Copyright/Rights Manager policies.

=== SOURCE OF TRUTH ===
Original Title/Text: {context.get('title', 'Unknown')}
Source Profile: {context.get('source', 'Unknown')}
{f"Deep AI Video Context: {context.get('deep_context', '')[:800]}" if context.get('deep_context') else ""}
{trending_snippet}

=== YOUR TASK ===
Analyze the "Original Title/Text" and any visual context. Identify:
1. Exact branches of military, equipment type, or operation/tribute.
2. The emotional hook (e.g., patriotism, power, precision, dedication).
3. The content safety risks:
   - Does this show graphic real-world violence, injuries, or non-sanctioned active warfare casualties?
   - Is it a non-military meme containing sensitive geopolitical issues?
   - Does it use copy-protected audio or official network broadcaster footage that might trigger Rights Manager?

Then generate:
1. **short_headline** – 3-6 words max, ALL CAPS, punchy, in ENGLISH. Include 1 relevant emoji.
2. **story** – A 2-3 sentence conversational paragraph hyping the video.
3. **category** – "Training", "Operations", "Tribute", "Aviation", "Navy", "Vehicles/Tech", "Meme/Humor", "Documentary".
4. **safety_flags** – List containing flags if present: "violence" (casualties/blood/severe injuries), "sensitive_meme" (non-military topics), "copyright_audio" (heavy commentary), "broadcaster_watermark" (visible tv logos). Empty list if clean.
5. **safety_actions** – Actions required to make the video safe: "mute_audio" (if audio risk), "flip_horizontal" (to avoid visual match), "trim_video" (if too long or ends in unsafe content). Empty list if clean.

Return ONLY a valid JSON object with these exact keys:
{{
  "category": "...",
  "short_headline": "...",
  "story": "...",
  "safety_flags": [],
  "safety_actions": []
}}"""
    
    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
            timeout=45,
        )
        content = completion.choices[0].message.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        data = json.loads(content.strip())
        
        for key in fallback.keys():
            if key not in data:
                data[key] = fallback[key]
                
        return data
    except Exception as e:
        print(f"Error calling NVIDIA LLM API for editing analysis: {e}")
        return fallback


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 – Generate upload metadata (improved, platform-specific)
# ──────────────────────────────────────────────────────────────────────────────
import re

def clean_input_title(title: str) -> str:
    if not title:
        return ""
    # Remove URLs
    title = re.sub(r'https?://\S+', '', title)
    # Remove Twitter handles (e.g. .@username or @username)
    title = re.sub(r'\.?@\w+', '', title)
    # Remove hashtag terms (e.g. #USArmy)
    title = re.sub(r'#\w+', '', title)
    # Replace hyphens/underscores with spaces
    title = re.sub(r'[-_]', ' ', title)
    # Clean up extra spacing
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def generate_upload_metadata(context: dict) -> dict:
    """
    Stage 2: Generates SEO metadata based on the full editing context.
    Platform-specific: YouTube (title <60 chars, description, tags) + Facebook (caption, hashtags).
    """
    client = _get_client()
    if not client:
        print("Warning: NVIDIA_API_KEY not found. Using fallback SEO data.")
        return _get_fallback_metadata(context)
    
    # Clean the input context strings to remove noisy handles, URLs, and hashtags
    title_clean = clean_input_title(context.get('title', 'Unknown'))
    headline_clean = clean_input_title(context.get('short_headline', ''))
    story_clean = clean_input_title(context.get('story', ''))

    # Build a compact keyword reference for the prompt
    sample_keywords = ', '.join(
        MILITARY_KEYWORDS['branches'][:4]
        + MILITARY_KEYWORDS['equipment'][:4]
        + MILITARY_KEYWORDS['topics'][:3]
    )
    sample_hashtags = ' '.join(MILITARY_HASHTAGS[:15])

    prompt = f"""You are a top-tier USA Military and Army social media SEO specialist. Generate platform-specific upload metadata for a viral military video.

=== FULL VIDEO CONTEXT ===
Original Title/Text: {title_clean}
Source Profile: {context.get('source', 'Unknown')}
Determined Category: {context.get('category', 'Tribute')}
Headline Used in Video: {headline_clean}
Story Used in Video: {story_clean}

=== TRENDING MILITARY REFERENCE DATA ===
Keyword pool (use naturally): {sample_keywords}
Trending hashtag pool: {sample_hashtags}

=== YOUR TASK ===
Generate SEO metadata tailored for YouTube AND Facebook. Each platform has different best practices.

**1. "title" (YouTube SEO Title)**
• STRICTLY under 60 characters.
• Include the most relevant branch/equipment name.
• Use a power word (UNBELIEVABLE, POWER, ELITE, PRIDE, HEROIC, EPIC).
• Example: "US Navy SEALs Training 🇺🇸 Elite Precision"

**2. "description" (YouTube Description)**
• 2-3 sentences. First sentence must hook the viewer.
• Naturally include 3-5 military keywords (branches, equipment, topic).
• End with a call to action (Like, Subscribe, Comment with support).
• Include relevant hashtags at the end.
• DO NOT append or request any Source URLs. Keep it clean.

**3. "facebook_caption" (Facebook Reels Caption)**
• Short, punchy, MAX 2 sentences. Do NOT include hashtags here.
• Must include a clear call-to-action (e.g., "Drop a 🇺🇸 if you support our troops!", "Who did this better?", "Watch till the end!").
• Conversational tone, like texting a friend.

**4. "hashtags" (Facebook Hashtags – string)**
• A single string of 7-8 highly relevant hashtags.
• MUST include at least 2 military-specific hashtags from the context.
• Mix broad (#Military, #USA) with specific (#NavySEALs, #USArmy).
• Never use non-military hashtags.

**5. "tags" (YouTube Tags – list of strings)**
• A list of 8-10 SEO tags for YouTube.
• Include: branch names (2-3), equipment names (1-2), topic names (1-2), generic military terms (2-3).
• Tags should be what fans would actually search on YouTube.

=== RULES ===
• Everything must be strictly USA military/army/navy/airforce. No unrelated politics, no general news.
• Write only in English.
• Match the emotional tone of the video (epic show → excited, tribute → proud/respectful, training → amazed).
• If you can identify the specific branches/equipment from the title, USE their exact names.
• Do NOT output any source URLs or Twitter usernames/handles.

Return ONLY a valid JSON object with these exact keys:
{{
  "title": "...",
  "description": "...",
  "facebook_caption": "...",
  "hashtags": "...",
  "tags": ["...", "...", "..."]
}}"""
    
    try:
        completion = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            top_p=0.95,
            max_tokens=1024,
        )
        
        content = completion.choices[0].message.content
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
            
        data = json.loads(content.strip())
        
        # Enforce YouTube title length
        if "title" in data and len(data["title"]) > 60:
            data["title"] = data["title"][:57] + "..."
        
        required_keys = ["title", "description", "facebook_caption", "hashtags", "tags"]
        for key in required_keys:
            if key not in data:
                data[key] = _get_fallback_metadata(context)[key]
                
        return data

    except Exception as e:
        print(f"Error calling NVIDIA LLM API for SEO: {e}")
        return _get_fallback_metadata(context)


# ──────────────────────────────────────────────────────────────────────────────
# Military-specific fallbacks
# ──────────────────────────────────────────────────────────────────────────────
def _get_fallback_metadata(context=None):
    if not context:
        context = {}
    
    raw_title = context.get('title', 'Incredible USA Military Power! 🇺🇸🦅')
    original_title = clean_input_title(raw_title)
    if not original_title:
        original_title = "Incredible USA Military Power! 🇺🇸🦅"
        
    category = context.get('category', 'Tribute')

    # Smart truncation for YouTube title
    yt_title = original_title[:57] + "..." if len(original_title) > 57 else original_title

    # Build description with trending keywords
    kw = MILITARY_KEYWORDS
    branch_hint = ""
    for b in kw["branches"]:
        if b.lower() in original_title.lower():
            branch_hint = f" featuring the {b}"
            break

    description = (
        f"{original_title}\n\n"
        f"An incredible demonstration of strength, coordination, and elite technology from our armed forces.{branch_hint}.\n"
        f"👉 LIKE this video, SUBSCRIBE for daily military videos, and COMMENT to show your support! 🇺🇸🦅"
    )

    # Pick the most relevant hashtags from the trending list
    context_lower = original_title.lower()
    specific_hashtags = []
    for ht in MILITARY_HASHTAGS:
        name = ht[1:].lower()  # strip #
        if name in context_lower or any(name in b.lower() for b in kw["branches"]) or any(name in e.lower() for e in kw["equipment"]):
            specific_hashtags.append(ht)
    # Always include broad ones
    base_hashtags = ["#Military", "#USA", "#Soldiers", "#MilitaryPower"]
    all_hashtags = list(dict.fromkeys(specific_hashtags + base_hashtags))[:8]
    hashtag_string = " ".join(all_hashtags)

    # Build tags
    tags = []
    # Add matched branches
    for b in kw["branches"]:
        if b.lower() in context_lower:
            tags.append(b)
    # Add matched equipment
    for e in kw["equipment"]:
        if e.lower() in context_lower:
            tags.append(e)
    # Add matched topics
    for t in kw["topics"]:
        if t.lower() in context_lower:
            tags.append(t)
    # Fill with generic military tags
    generic = ["Military", "Army", "Navy", "AirForce", "Marines", "Special Forces", "American Soldiers"]
    for g in generic:
        if len(tags) < 10 and g not in tags:
            tags.append(g)
    tags = tags[:10]

    return {
        "title": yt_title,
        "description": description,
        "facebook_caption": (
            f"{original_title}\n\n"
            f"{'🇺🇸 Show your support for our brave soldiers!' if 'tribute' in category.lower() else '🔥 An amazing showcase of military power!'}"
            f" Drop a comment and tag a friend who needs to see this! 👇"
        ),
        "hashtags": hashtag_string,
        "tags": tags,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dummy_context = {
        "title": "US Navy SEALs incredible training exercise .@USNavy https://t.co/xyz",
        "source": "USNavy",
        "source_url": "https://x.com/USNavy/status/1234567890"
    }
    analysis = analyze_video_for_editing(dummy_context)
    print("Editing Analysis:")
    print(json.dumps(analysis, indent=4))
    
    # Merge for Stage 2
    dummy_context.update(analysis)
    
    print("\nGenerated Metadata:")
    print(json.dumps(generate_upload_metadata(dummy_context), indent=4))

