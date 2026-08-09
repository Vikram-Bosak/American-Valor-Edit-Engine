import os
import re

# Words indicating high risk of violations (injury, fights, non-military sensitive content, broadcasters)
RISK_KEYWORDS = [
    "injury", "broken leg", "blood", "fight", "brawl", "clash", 
    "police", "arrest", "protest", "death", 
    "die", "killed", "disaster", "tragedy",
    "bein sports", "sky sports", "espn", "nbc sports", "canal+", "super sport"
]

def check_metadata_safety(title: str, description: str) -> dict:
    """
    Scans textual metadata against high-risk blacklisted phrases.
    """
    text_to_scan = f"{title} {description}".lower()
    found_flags = []
    
    for kw in RISK_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_to_scan):
            found_flags.append(kw)
            
    if found_flags:
        return {
            "is_safe": False,
            "action": "reject",
            "reasons": [f"Blacklisted keyword detected: '{flag}'" for flag in found_flags]
        }
        
    return {
        "is_safe": True,
        "action": "allow",
        "reasons": []
    }

def evaluate_ai_safety_analysis(analysis_result: dict) -> dict:
    """
    Evaluates Stage 1 LLM output for safety recommendations.
    """
    # If the AI explicitly marked copyright, violence, or sensitive issues:
    safety_flags = analysis_result.get("safety_flags", [])
    suggested_actions = analysis_result.get("safety_actions", [])
    
    if "violence" in safety_flags or "sensitive_meme" in safety_flags:
        return {
            "is_safe": False,
            "action": "reject",
            "reasons": [f"AI flag raised: {flag}" for flag in safety_flags],
            "modifications": []
        }
        
    if "copyright_audio" in safety_flags or "broadcaster_watermark" in safety_flags:
        return {
            "is_safe": True,
            "action": "modify",
            "reasons": [f"AI flagged modifiable risks: {safety_flags}"],
            "modifications": suggested_actions or ["mute_audio", "flip_horizontal"]
        }
        
    return {
        "is_safe": True,
        "action": "allow",
        "reasons": [],
        "modifications": []
    }
