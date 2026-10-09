"""
Correlator: matches transcript segments with screen content by timestamp proximity.
This is the core innovation — connecting what was SAID with what was SHOWN.
"""
import logging

logger = logging.getLogger(__name__)


def correlate(transcript_segments: list[dict], screen_frames: list[dict], window_seconds: float = 10.0) -> list[dict]:
    """
    Match transcript segments to screen frames by temporal proximity.

    For each screen frame, find transcript segments that occurred within
    a time window around it. This allows the LLM to see what was being
    discussed when a particular screen was shown.

    Args:
        transcript_segments: List of {'start', 'end', 'text'} dicts
        screen_frames: List of {'timestamp', 'ocr_text'} dicts
        window_seconds: Time window (seconds) to look before/after frame timestamp

    Returns:
        List of correlation dicts linking speech to screen content
    """
    correlations = []

    frames_with_text = [f for f in screen_frames if f.get('ocr_text', '').strip()]

    for frame in frames_with_text:
        frame_time = frame['timestamp']

        # Find transcript segments within the time window
        nearby_speech = []
        for seg in transcript_segments:
            # Check if segment overlaps with the frame's time window
            if (seg['start'] <= frame_time + window_seconds and
                    seg['end'] >= frame_time - window_seconds):
                nearby_speech.append(seg)

        if nearby_speech:
            combined_speech = ' '.join(s['text'] for s in nearby_speech)
            correlations.append({
                'timestamp': frame_time,
                'screen_text': frame['ocr_text'][:500],
                'speech_text': combined_speech[:500],
                'speech_segments': nearby_speech,
            })

    logger.info(f"Found {len(correlations)} speech-screen correlations")
    return correlations
