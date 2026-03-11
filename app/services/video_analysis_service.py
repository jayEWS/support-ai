"""
Video Analysis Service — AI-powered screen recording analyzer.
Extracts key frames from screen recordings and uses Llama 4 Scout Vision
to explain POS menus, functions, and workflow steps visible on screen.
"""
import os
import base64
import asyncio
import subprocess
import tempfile
from pathlib import Path
from app.core.logging import logger
from app.core.config import settings


GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SYSTEM_PROMPT = """You are an expert Edgeworks POS System analyst. You are analyzing screenshots extracted from a screen recording of the Edgeworks POS system (EquipPOS / FnB POS / Retail POS).

Your job is to:
1. **Identify the Screen/Menu** — What POS screen or module is shown (e.g., Checkout, Closing Counter, Payment, Product Management, Reports, Settings, KDS, etc.)
2. **Describe What You See** — Explain every visible element: buttons, fields, tables, status indicators, error messages, totals
3. **Explain the Function** — What this screen is used for in daily POS operations
4. **Identify Any Issues** — If you see error messages, incorrect values, misconfigurations, or anything unusual
5. **Provide Step-by-Step Guidance** — What the user should do next based on what's shown

Format your response clearly with sections:
## 🖥️ Screen Identified
## 📋 What's On Screen  
## ⚙️ Function & Purpose
## ⚠️ Issues Detected (if any)
## 📝 Recommended Next Steps

If multiple frames show a workflow sequence, describe the flow step by step.
Be specific about button names, field values, and menu paths you can read from the screenshots.
If you cannot identify specific elements, describe what you see visually."""


def extract_frames(video_path: str, max_frames: int = 6, output_dir: str = None) -> list[str]:
    """
    Extract key frames from a video file using ffmpeg.
    Returns list of file paths to extracted PNG frames.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="frames_")

    os.makedirs(output_dir, exist_ok=True)

    # Get video duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip())
    except Exception:
        duration = 30.0  # fallback

    # Calculate frame extraction interval
    # Extract frames at evenly spaced intervals
    interval = max(duration / (max_frames + 1), 1.0)

    output_pattern = os.path.join(output_dir, "frame_%03d.png")

    try:
        # Use fps filter to extract frames at intervals
        fps_value = 1.0 / interval if interval > 0 else 0.5
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps={fps_value:.4f},scale=1280:-2",  # scale to max 1280w
            "-frames:v", str(max_frames),
            "-q:v", "2",  # high quality
            output_pattern
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        logger.warning("[VideoAnalysis] ffmpeg timed out, trying simpler extraction")
        # Fallback: extract just first, middle, last frames
        for i, ts in enumerate([0, duration / 2, max(duration - 2, 0)]):
            out = os.path.join(output_dir, f"frame_{i + 1:03d}.png")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
                 "-frames:v", "1", "-q:v", "2", out],
                capture_output=True, timeout=10
            )

    # Collect extracted frames
    frames = sorted([
        os.path.join(output_dir, f) for f in os.listdir(output_dir)
        if f.endswith(".png") and os.path.getsize(os.path.join(output_dir, f)) > 1000
    ])

    logger.info(f"[VideoAnalysis] Extracted {len(frames)} frames from {video_path} (duration={duration:.1f}s)")
    return frames[:max_frames]


def frames_to_base64(frame_paths: list[str]) -> list[str]:
    """Convert frame image files to base64 strings."""
    results = []
    for fp in frame_paths:
        try:
            with open(fp, "rb") as f:
                data = f.read()
            # Skip tiny/corrupt frames
            if len(data) < 2000:
                continue
            results.append(base64.b64encode(data).decode("utf-8"))
        except Exception as e:
            logger.warning(f"[VideoAnalysis] Failed to read frame {fp}: {e}")
    return results


async def analyze_video(video_path: str, user_question: str = None) -> dict:
    """
    Analyze a screen recording video file.
    1. Extracts key frames via ffmpeg
    2. Sends frames to Llama 4 Scout Vision via Groq
    3. Returns AI analysis

    Args:
        video_path: Path to the .webm/.mp4 video file
        user_question: Optional additional context/question from the user

    Returns:
        dict with 'analysis' (str) and 'frames_analyzed' (int)
    """
    if not os.path.exists(video_path):
        return {"analysis": "Video file not found.", "frames_analyzed": 0, "error": True}

    # 1. Extract frames
    try:
        frame_paths = extract_frames(video_path, max_frames=6)
    except Exception as e:
        logger.error(f"[VideoAnalysis] Frame extraction failed: {e}")
        return {"analysis": f"Could not extract frames from video: {e}", "frames_analyzed": 0, "error": True}

    if not frame_paths:
        return {"analysis": "No usable frames could be extracted from the video.", "frames_analyzed": 0, "error": True}

    # 2. Convert to base64
    b64_frames = frames_to_base64(frame_paths)
    if not b64_frames:
        return {"analysis": "Frames were extracted but could not be processed.", "frames_analyzed": 0, "error": True}

    # 3. Build vision API request
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        return {"analysis": "AI vision not configured (missing GROQ_API_KEY).", "frames_analyzed": 0, "error": True}

    # Build multi-image content
    content_parts = []
    content_parts.append({
        "type": "text",
        "text": f"I'm analyzing {len(b64_frames)} screenshots extracted from a POS system screen recording."
        + (f"\n\nUser's question: {user_question}" if user_question else "")
        + "\n\nPlease analyze each screenshot and explain what's shown."
    })

    for i, b64 in enumerate(b64_frames):
        content_parts.append({
            "type": "text",
            "text": f"\n--- Screenshot {i + 1} of {len(b64_frames)} ---"
        })
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}"
            }
        })

    # 4. Call Groq Vision API
    import httpx

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_VISION_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": content_parts}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                }
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                logger.error(f"[VideoAnalysis] Groq Vision API error {response.status_code}: {error_text}")
                return {
                    "analysis": f"AI Vision API returned error {response.status_code}. The service may be temporarily unavailable.",
                    "frames_analyzed": len(b64_frames),
                    "error": True
                }

            data = response.json()
            analysis = data["choices"][0]["message"]["content"]

    except asyncio.TimeoutError:
        logger.error("[VideoAnalysis] Groq Vision API timed out")
        return {"analysis": "AI analysis timed out. The recording may be too complex. Try a shorter recording.", "frames_analyzed": len(b64_frames), "error": True}
    except Exception as e:
        logger.error(f"[VideoAnalysis] Vision API call failed: {e}")
        return {"analysis": f"AI analysis failed: {str(e)[:200]}", "frames_analyzed": len(b64_frames), "error": True}
    finally:
        # Cleanup temp frames
        for fp in frame_paths:
            try:
                os.remove(fp)
            except Exception:
                pass
        # Remove temp dir
        try:
            parent = os.path.dirname(frame_paths[0])
            if parent.startswith(tempfile.gettempdir()):
                os.rmdir(parent)
        except Exception:
            pass

    return {
        "analysis": analysis,
        "frames_analyzed": len(b64_frames),
        "error": False
    }
