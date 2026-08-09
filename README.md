# American-Valor-Edit-Engine

Automated pipeline to download, edit, and upload USA Military & Army videos from X (Twitter).

This project combines the American-Valor workflow with the AI editing skills from the funny-video-eddit-agent pipeline. It keeps the American-Valor branding frame (logo + headline overlay) and adds **AI voiceover, ALL-CAPS subtitles, sound effects, and a red hook circle** to every video. The video download logic now accepts Twitter/X profiles via environment-variable input instead of a hardcoded list.

## How It Works

```
main_agent.py (Orchestrator)
  ├── [1] src/agent_1_downloader.py  → Download video from input X profile(s) via Nitter RSS + yt-dlp
  ├── [2] src/agent_2_editor.py      → AI-enhanced edit (editor/ai_editor.py) with voiceover + subtitles + SFX + red hook circle on a 9:16 branding frame
  ├── [3] src/agent_3_uploader.py    → Upload to Facebook / YouTube Shorts / TikTok
  └── [4] src/agent_4_reporter.py    → Discord report + workspace cleanup
```

## Editing Skills (`editor/ai_editor.py`)

The editing stage applies these AI skills on top of the American-Valor branding layout:

1. **Video Analysis** — PySceneDetect scene detection + faster-whisper transcription. If the video is longer than 59s, the LLM selects the most engaging crop window; the LLM also plans 2-4 sound effects.
2. **AI Voiceover Script** — NVIDIA LLM writes a short, epic, patriotic narration (based on the transcript, or the visual summary if the clip is silent).
3. **Voice Generation** — Kokoro ONNX TTS (female `af_sarah` voice) synthesizes the voiceover.
4. **Branding Frame** — Pillow/pilmoji builds a 1080x1920 "American Valor" frame (logo, verified badge, headline/story) around the 9:16 cropped video.
5. **Red Hook Circle** — YOLOv8n detects the subject's head and draws a red circle for the first 1.5 seconds.
6. **Subtitles** — faster-whisper word timestamps generate ASS subtitles (ALL CAPS, bold with black outline) burned into the video.
7. **Sound Effects** — synthesized WAV SFX (boing/whoosh/ding/alert/fail/laugh) are mixed at the AI-planned timestamps.
8. **Audio Mix** — TTS voiceover plays over the video, with the original audio swapped back in for 5 seconds in the middle.

## Download Logic

`src/agent_1_downloader.py` downloads the latest unprocessed video posted in the last 24 hours from a given X/Twitter profile.

1. **Input profiles** are read from the environment variable `X_PROFILES` (or the alias `TWITTER_PROFILES`).
   - Accepts comma-separated usernames (`USArmy,USNavy`), full `x.com` URLs, or `twitter.com` URLs.
   - If no profile is provided, it falls back to a default list of USA military profiles.
2. Each profile's RSS feed is fetched via Nitter (`https://nitter.net/{username}/rss`).
3. Items are filtered to keep only:
   - **Videos** (description contains `Video`)
   - **Posted within the last 24 hours**
   - **Not already processed** (checked against `downloaded_history.txt`)
4. Valid videos are sorted oldest-first and downloaded with yt-dlp to `workspace/raw_video.mp4`.
5. The downloaded video flows into the AI editing workflow (`src/agent_2_editor.py` → `editor/ai_editor.py`).

## Configuration

Set these environment variables (as GitHub Actions secrets, or in `.env` for local runs):

| Variable | Description |
|----------|-------------|
| `X_PROFILES` | Comma-separated X/Twitter profiles to download from (e.g. `USArmy,USNavy`) |
| `TWITTER_PROFILES` | Alias for `X_PROFILES` |
| `DISCORD_WEBHOOK_URL` | Discord webhook for notifications/reports |
| `NVIDIA_API_KEY` | NVIDIA NIM API key (LLM SEO generation) |
| `FB_ACCESS_TOKEN` | Facebook Page access token |
| `FB_PAGE_ID` | Facebook Page ID |
| `YOUTUBE_TOKEN_JSON` | YouTube OAuth token JSON |
| `TIKTOK_AUTH_STATE` / `TIKTOK_AUTH_STATE_B64` | TikTok auth state |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram notifications |

See `.env.example` for a full template.

## GitHub Actions

The workflow `.github/workflows/pipeline.yml`:

- Runs on a schedule (every 2 hours).
- Can be manually triggered (`workflow_dispatch`) with an optional `x_profiles` / `twitter_profiles` input.
- `X_PROFILES` is resolved as: manual dispatch input → GitHub secret `X_PROFILES` → default military list.

## Requirements

- Python 3.11+
- FFmpeg + ffprobe (system dependency, installed in the workflow)
- Playwright (Chromium) — installed by the workflow
- Python packages in `requirements.txt`
