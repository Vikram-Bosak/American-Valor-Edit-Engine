import os
import re
from openai import OpenAI
import json
try:
    from .logger import logger
except ImportError:
    from logger import logger

# ──────────────────────────────────────────────────────────────────────────────
# Trending Military Keywords and Hashtags
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
    "competitions": [
        "USA Military", "Department of Defense", "Pentagon", "Armed Forces", "Patriotism",
    ],
}

MILITARY_HASHTAGS = [
    "#USArmy", "#USNavy", "#USMC", "#USAirForce", "#Military", "#Army",
    "#Marines", "#NavySEALs", "#SpecialForces", "#Tactical", "#Aviation",
    "#FighterJet", "#Navy", "#AirForce", "#Veterans", "#MilitaryLife",
]

def clean_filename(filename):
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', name_without_ext)
    # Remove Twitter handles
    cleaned = re.sub(r'\.?@\w+', '', cleaned)
    # Remove hashtag terms
    cleaned = re.sub(r'#\w+', '', cleaned)
    # Replace hyphens/underscores/special chars with spaces
    cleaned = re.sub(r'[-_]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def generate_seo_metadata(filename, media_type='reel'):
    """
    Generates SEO title, description, and hashtags based on the video filename.
    Returns a dictionary with 'title', 'description', and 'hashtags'.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not found. Using fallback metadata generator.")
        return generate_fallback_metadata(filename)
        
    base_url = os.environ.get('OPENAI_API_BASE_URL')
    model = os.environ.get('OPENAI_API_MODEL', 'gpt-3.5-turbo')
    
    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)
        
    topic = clean_filename(filename)
    
    content_type_str = "Facebook Reel" if media_type == 'reel' else "Facebook Photo Post"
    video_str = "short vertical video (Facebook Reel)" if media_type == 'reel' else "stunning photo/image"
    hashtag_str = "#Reels #USArmy #Military" if media_type == 'reel' else "#USArmy #USNavy"
    
    system_prompt = (
        f"You are an expert Social Media Manager and SEO specialist for {content_type_str}s targeting USA military and army enthusiasts. "
        "Your goal is to maximize engagement, click-through rate, search visibility, and organic reach."
    )
    
    user_prompt = f"""
    Generate viral, SEO-optimized military metadata for a {video_str} about: "{topic}".
    
    Requirements:
    1. Title: Short, catchy, uses power words (e.g. UNBELIEVABLE, POWER, ELITE, PRIDE), includes relevant emojis. Max 60 characters.
    2. Description: 1-2 short, engaging sentences that create curiosity. Do NOT include any Twitter/X usernames, source URLs, or links.
    3. Hashtags: 5-8 highly relevant and trending military hashtags (include {hashtag_str}).
    
    Format the output exactly as JSON:
    {{
        "title": "...",
        "description": "...",
        "hashtags": "#tag1 #tag2 ..."
    }}
    """
    
    try:
        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        if "gpt-" in model:
            params["response_format"] = {"type": "json_object"}
            
        response = client.chat.completions.create(**params)
        
        result_json = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks if present
        if result_json.startswith("```"):
            result_json = re.sub(r'^```(?:json)?\n', '', result_json)
            result_json = re.sub(r'\n```$', '', result_json)
            result_json = result_json.strip()
            
        data = json.loads(result_json)
        
        return {
            'title': data.get('title', topic.title()),
            'description': data.get('description', f"Incredible military moment featuring {topic}! Watch till the end! 🇺🇸🦅"),
            'hashtags': data.get('hashtags', "#USArmy #USNavy #Military #Reels")
        }
        
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return generate_fallback_metadata(filename)

def generate_fallback_metadata(filename):
    import hashlib
    
    def get_deterministic_choice(fn, lst):
        h = int(hashlib.md5(fn.encode('utf-8')).hexdigest(), 16)
        return lst[h % len(lst)]
        
    topic = clean_filename(filename)
    topic_title = topic.title() if topic else "Unmissable Military Moment"
    
    # Pre-saved Military SEO Patterns (Titles & Descriptions)
    titles = [
        "Incredible {topic} action! 🇺🇸🦅",
        "The raw power of {topic} is unreal! 🙌",
        "POV: Witnessing {topic} strength. 🤯",
        "Is this the best of {topic} ever? 👀",
        "This {topic} clip will give you goosebumps! 🚨"
    ]
    descriptions = [
        "Witness one of the most incredible military moments featuring {topic}. Our armed forces never fail to amaze! 🇺🇸🦅",
        "Up close and personal with {topic}! An extraordinary glimpse into elite military operations. Share this with a friend! 📲🎖️",
        "Just when you think you've seen it all, this happens. Absolute military power! What are your thoughts on this? 👇"
    ]
    
    # Get deterministic choices based on filename to keep output consistent per video
    title_template = get_deterministic_choice(filename, titles)
    desc_template = get_deterministic_choice(filename, descriptions)
    
    # Generate Title & Base Description
    title = title_template.format(topic=topic_title)
    if len(title) > 60:
        title = title[:57] + "..."
        
    description = desc_template.format(topic=topic_title)
    
    # Build Hashtags list
    hash_tags_set = {'#military', '#usarmy', '#usnavy', '#reels'}
    
    # Add matches from trending keywords to specific hashtags
    kw = MILITARY_KEYWORDS
    context_lower = topic.lower()
    for b in kw["branches"]:
        if b.lower() in context_lower:
            hash_tags_set.add(f"#{b.replace(' ', '').lower()}")
    for e in kw["equipment"]:
        if e.lower() in context_lower:
            hash_tags_set.add(f"#{e.replace(' ', '').lower()}")
    for c in kw["competitions"]:
        if c.lower() in context_lower:
            hash_tags_set.add(f"#{c.replace(' ', '').lower()}")
            
    # Convert set back to list, ensure we don't have duplicates, and limit to ~8 tags
    ordered_tags = ['#military', '#usarmy', '#usnavy', '#reels']
    for tag in sorted(hash_tags_set):
        if tag not in ordered_tags:
            ordered_tags.append(tag)
            
    final_tags = ordered_tags[:8]
    hashtags_str = " ".join([t.title() for t in final_tags])
    # Capitalize tags properly (e.g. #USArmy, #NavySEALs)
    hashtags_str = re.sub(r'#([a-z])', lambda m: '#' + m.group(1).upper(), hashtags_str)
    
    return {
        'title': title,
        'description': description,
        'hashtags': hashtags_str
    }

def format_caption(seo_metadata):
    """
    Combines the title, description, and hashtags into the final Facebook caption format.
    """
    return f"{seo_metadata['title']}\n\n{seo_metadata['description']}\n\n{seo_metadata['hashtags']}"
