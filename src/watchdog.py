import os
import json
from datetime import datetime
try:
    from .logger import logger
except ImportError:
    from logger import logger

HEARTBEAT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'heartbeat.json')

def update_heartbeat(status, details=None):
    """
    Updates the watchdog heartbeat file with the current timestamp, status, and details.
    """
    try:
        os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
        heartbeat_data = {
            "last_heartbeat": datetime.now().isoformat(),
            "status": status,
            "details": details or {}
        }
        with open(HEARTBEAT_PATH, 'w') as f:
            json.dump(heartbeat_data, f, indent=4)
        logger.info(f"Watchdog heartbeat updated: {status}")
    except Exception as e:
        logger.error(f"Failed to update watchdog heartbeat: {e}")

def check_heartbeat_max_age(max_age_seconds=3600):
    """
    Checks if the watchdog heartbeat is fresh or stale.
    Returns (is_alive, message).
    """
    if not os.path.exists(HEARTBEAT_PATH):
        return False, "Heartbeat file does not exist."
    try:
        with open(HEARTBEAT_PATH, 'r') as f:
            data = json.load(f)
        last_heartbeat_str = data.get("last_heartbeat")
        if not last_heartbeat_str:
            return False, "Invalid heartbeat data."
        last_heartbeat = datetime.fromisoformat(last_heartbeat_str)
        age = (datetime.now() - last_heartbeat).total_seconds()
        if age > max_age_seconds:
            return False, f"Heartbeat is stale: {age} seconds old (limit: {max_age_seconds}s)"
        return True, f"Heartbeat is fresh: {age} seconds old."
    except Exception as e:
        return False, f"Failed to read/parse heartbeat file: {e}"
