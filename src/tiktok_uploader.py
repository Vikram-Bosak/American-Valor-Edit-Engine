import os
import json
import time
import base64
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TikTokUploadAgent:
    def __init__(self):
        # Determine cookies path (look for env variable first)
        self.state_file = os.path.join(os.path.dirname(__file__), "tiktok_auth_state.json")
        
        raw_secret = os.environ.get("TIKTOK_AUTH_STATE")
        b64_secret = os.environ.get("TIKTOK_AUTH_STATE_B64")
        
        if b64_secret:
            try:
                decoded = base64.b64decode(b64_secret).decode("utf-8")
                parsed = json.loads(decoded)
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"TikTok Uploader: TIKTOK_AUTH_STATE_B64 contains invalid base64/JSON: {e}")
        elif raw_secret:
            try:
                parsed = json.loads(raw_secret)
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"TikTok Uploader: TIKTOK_AUTH_STATE contains invalid JSON: {e}")
        else:
            # Fall back to local file if no env var is set
            local_state = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tiktok_auth_state.json")
            if os.path.exists(local_state):
                self.state_file = local_state
            else:
                logging.warning("TikTok Uploader: Missing TIKTOK_AUTH_STATE/TIKTOK_AUTH_STATE_B64 env vars, and local state file not found.")

    def dismiss_overlays(self, page, suffix=""):
        logging.info(f"TikTok Uploader: Checking for overlays/modals to dismiss ({suffix})...")
        
        # 1. Target "Turn on" button specifically
        try:
            turn_on = page.locator('button:has-text("Turn on")')
            if turn_on.count() > 0:
                logging.info("TikTok Uploader: Found 'Turn on' modal button. Clicking...")
                turn_on.first.click(force=True)
                time.sleep(2)
        except Exception as e:
            logging.warning(f"TikTok Uploader: Error clicking 'Turn on': {e}")
            
        # 2. Target "Cancel" button specifically
        try:
            cancel = page.locator('button:has-text("Cancel")')
            if cancel.count() > 0:
                logging.info("TikTok Uploader: Found 'Cancel' modal button. Clicking...")
                cancel.first.click(force=True)
                time.sleep(2)
        except Exception as e:
            logging.warning(f"TikTok Uploader: Error clicking 'Cancel': {e}")

        # 3. Target "Got it" tooltips
        try:
            got_it_buttons = page.locator('button:has-text("Got it")')
            count = got_it_buttons.count()
            for idx in range(count):
                logging.info(f"TikTok Uploader: Found 'Got it' tooltip button {idx+1}/{count}. Clicking...")
                got_it_buttons.nth(idx).click(force=True)
                time.sleep(1.5)
        except Exception as e:
            logging.warning(f"TikTok Uploader: Error clicking 'Got it': {e}")

    def upload_to_tiktok(self, video_path, caption):
        logging.info("TikTok Uploader: Starting Playwright uploader...")
        if not os.path.exists(self.state_file):
            raise Exception(f"Auth state file not found: {self.state_file}. Please configure TIKTOK_AUTH_STATE secret.")
        
        abs_video_path = os.path.abspath(video_path)
        if not os.path.exists(abs_video_path):
            raise Exception(f"Video file not found: {abs_video_path}")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(storage_state=self.state_file)
                page = context.new_page()
                
                logging.info("TikTok Uploader: Navigating to upload page...")
                page.goto("https://www.tiktok.com/creator-center/upload")
                
                logging.info("TikTok Uploader: Waiting for file input...")
                file_input = page.locator('input[type="file"][accept*="video"]')
                file_input.wait_for(state="attached", timeout=60000)
                file_input.set_input_files(abs_video_path)
                
                logging.info("TikTok Uploader: Waiting for video file upload to reach 100%...")
                try:
                    uploaded_locator = page.locator('text="Uploaded"')
                    uploaded_locator.wait_for(state="visible", timeout=120000)
                    logging.info("TikTok Uploader: Video file upload completed successfully!")
                except Exception as upload_err:
                    logging.warning(f"TikTok Uploader: Warning - upload completion indicator not found: {upload_err}")
                
                logging.info("TikTok Uploader: Waiting for caption editor...")
                caption_editor = page.locator('.public-DraftEditor-content')
                caption_editor.wait_for(state="visible", timeout=90000)
                
                # Dismiss overlays before typing
                self.dismiss_overlays(page, "before_typing")

                logging.info("TikTok Uploader: Typing caption/metadata...")
                try:
                    caption_editor.click(timeout=10000)
                except Exception:
                    caption_editor.click(force=True)
                
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(caption, delay=50)
                time.sleep(3)
                
                # Dismiss overlays after typing / before posting
                self.dismiss_overlays(page, "before_posting")

                logging.info("TikTok Uploader: Clicking Post...")
                post_button = page.locator('button[data-e2e="post_video_button"]')
                try:
                    post_button.click(timeout=10000)
                except Exception:
                    post_button.click(force=True)
                
                time.sleep(3)

                # Handle the "Continue to post?" copyright check modal
                try:
                    post_now_btn = page.locator('button:has-text("Post now"), button.Button__root:has-text("Post now")')
                    if post_now_btn.count() > 0:
                        logging.info("TikTok Uploader: Found 'Continue to post?' warning. Clicking 'Post now'...")
                        post_now_btn.first.click(force=True)
                        time.sleep(2)
                except Exception as e:
                    logging.warning(f"TikTok Uploader: Error clicking 'Post now': {e}")

                logging.info("TikTok Uploader: Waiting for upload to complete and redirect to content manager...")
                video_url = "https://www.tiktok.com/@AmericanValorTV" # Default fallback
                try:
                    page.wait_for_url(lambda url: "creator-center" in url or "tiktokstudio" in url, timeout=55000)
                    logging.info(f"TikTok Uploader: Successfully redirected to content manager ({page.url}).")
                except Exception:
                    logging.warning(f"TikTok Uploader: Did not detect redirect URL pattern (current URL: {page.url})")
                
                # Attempt to extract video URL if we are on creator center or tiktok studio page
                if "creator-center" in page.url or "tiktokstudio" in page.url:
                    if "upload" in page.url:
                        posts_url = page.url.replace("/upload", "/posts") if "tiktokstudio" in page.url else page.url.replace("/upload", "/content")
                        logging.info(f"TikTok Uploader: Navigating to posts page: {posts_url}")
                        page.goto(posts_url)
                    time.sleep(8)
                    try:
                        links = page.locator("a").all()
                        logging.info(f"TikTok Uploader: Total 'a' links found on page: {len(links)}")
                        for idx, link in enumerate(links[:50]):
                            href = link.get_attribute("href")
                            text = link.inner_text()
                            logging.info(f"Link {idx}: text='{text}', href='{href}'")
                    except Exception as list_err:
                        logging.warning(f"TikTok Uploader: Error listing page links: {list_err}")

                    try:
                        video_link_selector = 'a[href*="/video/"]'
                        page.wait_for_selector(video_link_selector, timeout=15000)
                        extracted_url = page.locator(video_link_selector).first.get_attribute("href")
                        if extracted_url:
                            if not extracted_url.startswith("http"):
                                video_url = "https://www.tiktok.com" + extracted_url
                            else:
                                video_url = extracted_url
                            logging.info(f"TikTok Uploader: Extracted uploaded video URL: {video_url}")
                    except Exception as extract_err:
                        logging.warning(f"TikTok Uploader: Could not extract video URL, using profile fallback: {extract_err}")
                        try:
                            page.screenshot(path="tiktok_error.png")
                            logging.info("TikTok Uploader: Saved debug screenshot to tiktok_error.png")
                        except Exception as ss_err:
                            logging.error(f"TikTok Uploader: Failed to save screenshot: {ss_err}")
                
                browser.close()

            logging.info("TikTok Uploader: Video successfully posted via Playwright!")
            return video_url
            
        except Exception as e:
            logging.error(f"TikTok Uploader: Playwright upload error: {e}")
            raise e

def upload_tiktok(video_path, caption):
    agent = TikTokUploadAgent()
    return agent.upload_to_tiktok(video_path, caption)
