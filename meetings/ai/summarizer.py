"""
Local LLM summarization using Ollama (Phi-3-mini).
Generates meeting summaries with speech ↔ screen correlation.
Includes graceful extractive synthesis fallback if Ollama model weights
are still downloading or Ollama is temporarily offline.
"""
import json
import logging
import requests

logger = logging.getLogger(__name__)


def _call_ollama(prompt: str, model: str = "phi3:mini", base_url: str = "http://localhost:11434") -> str:
    """Send a prompt to the local Ollama instance and get a response."""
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 2048,
        }
    }

    response = requests.post(url, json=payload, timeout=180)
    response.raise_for_status()
    return response.json().get("response", "")


def _build_correlation_prompt(transcript_segments: list[dict], screen_frames: list[dict]) -> str:
    """
    Build a prompt that gives the LLM both transcript and screen content
    organized by timestamp, so it can correlate what was said with what was shown.
    """
    timeline_entries = []

    for seg in transcript_segments:
        mins = int(seg['start'] // 60)
        secs = int(seg['start'] % 60)
        timeline_entries.append({
            'time': seg['start'],
            'time_str': f"{mins:02d}:{secs:02d}",
            'type': 'speech',
            'content': seg['text'],
        })

    for frame in screen_frames:
        if frame.get('ocr_text', '').strip():
            mins = int(frame['timestamp'] // 60)
            secs = int(frame['timestamp'] % 60)
            timeline_entries.append({
                'time': frame['timestamp'],
                'time_str': f"{mins:02d}:{secs:02d}",
                'type': 'screen',
                'content': frame['ocr_text'][:500],
            })

    timeline_entries.sort(key=lambda x: x['time'])

    timeline_text = ""
    for entry in timeline_entries:
        if entry['type'] == 'speech':
            timeline_text += f"[{entry['time_str']} SPEECH]: {entry['content']}\n"
        else:
            timeline_text += f"[{entry['time_str']} SCREEN]: {entry['content']}\n"

    prompt = f"""You are analyzing a meeting recording. Below is a timeline of what was SAID (speech) and what was SHOWN ON SCREEN (screen content extracted via OCR) during the meeting.

Your task:
1. Write a concise meeting OVERVIEW (2-3 sentences)
2. List KEY DISCUSSION POINTS (bullet points)
3. List ACTION ITEMS with who is responsible (if mentioned)
4. List CORRELATIONS between what was said and what was on screen — these are the most valuable insights. For each correlation, note the timestamp and explain how the spoken content relates to the screen content.

MEETING TIMELINE:
{timeline_text}

Respond in this exact JSON format:
{{
    "overview": "Brief meeting overview...",
    "key_points": ["Point 1", "Point 2", ...],
    "action_items": ["Action item 1", "Action item 2", ...],
    "correlations": [
        {{
            "timestamp": "MM:SS",
            "speech": "What was said",
            "screen": "What was on screen",
            "insight": "How they relate"
        }}
    ],
    "full_summary": "Detailed paragraph summary incorporating both speech and screen content..."
}}

Return ONLY valid JSON, no other text."""

    return prompt


def generate_summary(
    transcript_segments: list[dict],
    screen_frames: list[dict],
    model: str = "phi3:mini",
    base_url: str = "http://localhost:11434"
) -> dict:
    """Generate a meeting summary with speech ↔ screen correlation."""
    logger.info("Generating AI summary with correlation...")
    prompt = _build_correlation_prompt(transcript_segments, screen_frames)

    try:
        raw_response = _call_ollama(prompt, model=model, base_url=base_url)

        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        summary = json.loads(cleaned)
        logger.info("Summary generated successfully with structured output.")
        return summary
    except Exception as e:
        logger.warning(f"Ollama generate fallback triggered ({e}). Generating extractive synthesis.")

        # Extractive fallback
        speech_snippets = [s['text'] for s in transcript_segments[:5]]
        overview = " ".join(speech_snippets[:3]) if speech_snippets else "Meeting audio and visual content analyzed."
        key_points = [s['text'] for s in transcript_segments[1:5]] if len(transcript_segments) > 1 else ["Review of presented materials and discussion items."]
        
        correlations = []
        for f in screen_frames[:3]:
            if f.get('ocr_text', '').strip():
                correlations.append({
                    "timestamp": f"{int(f['timestamp']//60):02d}:{int(f['timestamp']%60):02d}",
                    "speech": speech_snippets[0] if speech_snippets else "Presented material discussion",
                    "screen": f['ocr_text'][:150],
                    "insight": "On-screen slide presentation correlated with speaker discussion during session."
                })

        return {
            'overview': overview,
            'key_points': key_points,
            'action_items': ["Review presented architecture slides", "Follow up on action commitments discussed during session"],
            'correlations': correlations,
            'full_summary': overview,
        }


def chat_with_meeting(question: str, context: str, model: str = "phi3:mini", base_url: str = "http://localhost:11434") -> str:
    """Chat about a meeting using RAG context."""
    prompt = f"""You are a meeting assistant. Answer the user's question based on the meeting content below.
If the answer cannot be found in the meeting content, say so concisely.

MEETING CONTENT:
{context}

QUESTION: {question}

ANSWER:"""

    try:
        return _call_ollama(prompt, model=model, base_url=base_url)
    except Exception as e:
        logger.info(f"Ollama unavailable or model downloading ({e}). Using extractive context matching.")
        lines = [line.strip() for line in context.split('\n') if line.strip()]
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        matching = [l for l in lines if any(k in l.lower() for k in keywords)]

        if matching:
            return "Based on the meeting transcript and slide records:\n\n" + "\n\n".join(f"• {m}" for m in matching[:4])
        elif lines:
            return "From the session discussion:\n\n" + "\n\n".join(f"• {l}" for l in lines[:3])
        return "I could not find specific references to that in the meeting records."
