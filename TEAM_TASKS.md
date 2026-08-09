# TEAM_TASKS.md — FIFA World Cup Agent 1: Division of Labor

**Created:** 2026-07-02  
**Project:** Fifa_world_cup_agent_1  
**Pipeline:** Download → Edit → Upload (Twitter → Facebook Reels + YouTube Shorts)

---

## Orchestrator (Agent 0) — Files Owned

| File | Status | Changes Made |
|------|--------|-------------|
| `src/seo_generator.py` | ✅ Fixed | Replaced wildlife/nature fallback categories with football/FIFA categories. Updated AI prompt to generate football-specific headlines. Added football keyword database (messi, ronaldo, mbappe, etc.). All fallback titles, descriptions, and hashtags now match FIFA World Cup content. |
| `main_agent.py` | ✅ Fixed | Added `stats.setdefault()` for `errors`, `videos_edited`, `videos_uploaded` to prevent KeyError if downloader returns unexpected format. Added `check=True` to all git subprocess calls so push failures are caught and logged instead of silently ignored. |
| `editor/advanced_editor.py` | ✅ Fixed | Added `timeout=30` to ffprobe audio detection, `timeout=120` to ffmpeg encoding. Replaced bare `except: pass` with specific exception types (`TimeoutExpired`, `CalledProcessError`, `FileNotFoundError`) with logging. |

### Orchestrator Review Findings

**src/seo_generator.py:**
- **Critical:** Fallback metadata used wildlife/nature categories (tiger, lion, elephant) instead of football content. This would produce nonsensical captions like "Wait for it... Messi Free Kick World Cup in full action! 😱" with hashtags like #wildlife #safari.
- **Fixed:** All fallback templates, keyword classifications, and hashtag databases now produce football-appropriate content.
- **Note:** This file is used by `src/queue_manager.py` (Worker 2's file) via relative import. Changes are backward-compatible.

**main_agent.py:**
- **Pipeline flow is correct:** Download → Save History → Git Push → Edit → Upload → Report.
- **Minor issue fixed:** `stats` dict could lack required keys if `run_downloader()` returned unexpected format. Now defensively initialized.
- **Minor issue fixed:** Git subprocess calls didn't use `check=True`, so push failures were silently swallowed.

**editor/advanced_editor.py:**
- **Critical:** ffmpeg subprocess had no timeout — a corrupt video could hang the pipeline forever.
- **Fixed:** Added timeouts (30s for ffprobe, 120s for ffmpeg encoding).
- **Critical:** Bare `except: pass` on audio detection silenced all errors.
- **Fixed:** Now catches specific exceptions and logs them.

---

## Worker 1 — Files Owned

**Assigned files:** `src/facebook_uploader.py`, `src/health_checker.py`

### Task for Worker 1: Review & Fix `src/facebook_uploader.py`

**Current state:** The Facebook Graph API upload uses v19.0 endpoints. Multi-step upload (init → upload data → publish) looks correct.

**Recommended fixes:**
1. **Add retry logic for transient API errors** — The upload function currently raises on any failure. Add exponential backoff retries for 5xx errors and rate limits (429).
2. **Add file size validation** — Currently reads entire video into memory (`f.read()`). For large videos (>50MB), consider streaming upload or chunked transfer.
3. **Add timeout to requests calls** — All `requests.post/get` calls lack timeouts, which could hang on network issues.
4. **Verify Graph API version** — v19.0 may become deprecated. Consider making the API version configurable via env var.
5. **Add logging for upload progress** — Large video uploads give no progress feedback.

### Task for Worker 1: Review & Fix `src/health_checker.py`

**Current state:** Checks internet, Facebook token, and Google Drive connectivity. Looks clean.

**Recommended fixes:**
1. **Add timeout to Google Drive check** — `service.files().get()` call has no timeout.
2. **Add YouTube API health check** — The pipeline uploads to YouTube but there's no health check for YouTube credentials.
3. **Consider caching health check results** — Running all 3 checks every cycle is expensive. Could cache results for 5 minutes.
4. **Add OpenAI/NVIDIA API health check** — SEO generation depends on external API but there's no pre-flight check.

---

## Worker 2 — Files Owned

**Assigned files:** `src/scheduler.py`, `src/queue_manager.py`, `src/database.py`

### Task for Worker 2: Review & Fix `src/scheduler.py`

**Current state:** Well-structured scheduler with time slot logic, health checks, force upload mode, and jitter. Uses Google Drive as the media queue.

**Recommended fixes:**
1. **Add `--dry-run` flag** — Would allow testing the scheduling logic without actually uploading.
2. **Fix jitter import placement** — `import random` and `import time` are inside the `else` block (line 179-180). Move to top of file for clarity.
3. **Add daily upload count from database** — Currently checks Google Drive for pending media but doesn't cross-reference with `database.py`'s `get_daily_upload_count()`. Could prevent over-uploading.
4. **Handle timezone edge cases** — The `get_latest_scheduled_slot_time` function could fail if EST timezone data is unavailable on the system (fallback to UTC).

### Task for Worker 2: Review & Fix `src/queue_manager.py`

**Current state:** Robust queue processor with duplicate detection, media validation, retry logic, and Google Drive file management. Well-structured with proper error handling.

**Recommended fixes:**
1. **Add database init call** — `init_db()` is called at import time in `database.py`, but `queue_manager.py` doesn't explicitly call it. Ensure DB is initialized before first use.
2. **Add upload progress logging** — For debugging, log the file size and estimated upload time before starting Facebook upload.
3. **Consider adding a "processing" status** — Currently only has `pending`, `uploaded`, `failed`. Adding `processing` would prevent race conditions in concurrent runs.
4. **Clean up temp state files** — The `temp/state_upload_{task_id}.json` files created by the editor are never cleaned up by queue_manager.

### Task for Worker 2: Review & Fix `src/database.py`

**Current state:** SQLite database with WAL mode, proper connection management, and migration support. Clean and functional.

**Recommended fixes:**
1. **Add `media_type` to `is_duplicate` query** — Currently checks by filename/hash across all media types. Should filter by media_type to prevent a reel being flagged as duplicate of a photo with the same hash.
2. **Add `get_pending_count()` helper** — Useful for the scheduler to check queue depth without importing drive_reader.
3. **Add database backup/rotation** — Over time the `reels` table could grow unbounded. Add a cleanup function to archive old records.
4. **Add `last_attempt_time` column** — Would help the scheduler determine how long it's been since the last retry attempt.

---

## File Ownership Matrix

| File | Owner | Can Touch? |
|------|-------|-----------|
| `src/seo_generator.py` | Orchestrator | ✅ Done |
| `main_agent.py` | Orchestrator | ✅ Done |
| `editor/advanced_editor.py` | Orchestrator | ✅ Done |
| `src/facebook_uploader.py` | Worker 1 | ❌ Do not touch |
| `src/health_checker.py` | Worker 1 | ❌ Do not touch |
| `src/scheduler.py` | Worker 2 | ❌ Do not touch |
| `src/queue_manager.py` | Worker 2 | ❌ Do not touch |
| `src/database.py` | Worker 2 | ❌ Do not touch |

---

## Shared Dependencies (read-only reference)

These files are used across the pipeline but NOT owned by any worker:

| File | Used By | Notes |
|------|---------|-------|
| `src/common/seo_generator.py` | Editor (Stage 1/2), Queue Manager | NVIDIA LLM + Gemini for AI analysis. Well-structured. |
| `src/common/telegram.py` | Main, Editor, Scheduler | Telegram notifications. No changes needed. |
| `src/common/limits.py` | Main, Queue Manager | Daily rate limiting. No changes needed. |
| `src/common/ui_frame_generator.py` | Editor | PIL/Pilmoji frame generation. No changes needed. |
| `src/agent_1_downloader.py` | Main | Twitter RSS + yt-dlp downloader. No changes needed. |
| `src/agent_2_editor.py` | Main | Editor wrapper. No changes needed. |
| `src/agent_3_uploader.py` | Main | Upload wrapper (FB + YT). No changes needed. |
| `src/youtube_uploader.py` | Agent 3, Queue Manager | YouTube Shorts upload. No changes needed. |
| `src/drive_reader.py` | Scheduler, Queue Manager | Google Drive API. No changes needed. |
| `src/watchdog.py` | Scheduler | Heartbeat monitoring. No changes needed. |
