import os
import sys
import time
import random
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path so we can import common
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.telegram import report_edit_start, report_edit_complete

def edit_video(input_path: str, output_path: str):
    import os
    import shutil
    
    report_edit_start()
    print("EDITING DISABLED BY USER. Copying raw video directly...")
    
    # Ensure temp directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        shutil.copy(input_path, output_path)
        print("Raw video copied successfully without editing.")
    except Exception as e:
        print(f"Failed to copy video: {e}")
        with open(output_path, 'w') as f:
            f.write("Failed to copy raw video\n")
    
    report_edit_complete()

if __name__ == "__main__":
    INPUT_FILE = "temp/raw_video.mp4"
    OUTPUT_FILE = "temp/edited_video.mp4"
    edit_video(INPUT_FILE, OUTPUT_FILE)
