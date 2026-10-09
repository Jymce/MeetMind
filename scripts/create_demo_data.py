"""
Creates a realistic sample meeting session with synthesized slides,
timestamped audio transcript turns, and multi-modal correlations for immediate demoing.
"""
import os
import sys
import json
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meetmind.settings')

import django
django.setup()

from django.conf import settings
from meetings.models import Meeting, TranscriptSegment, ScreenFrame, MeetingSummary
from PIL import Image, ImageDraw, ImageFont


def generate_slide_image(output_path: str, title: str, subtitle: str, bullets: list[str], accent_color=(99, 102, 241)):
    """Generate a clean dark-mode slide image."""
    width, height = 1280, 720
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Gradient top bar
    draw.rectangle([(0, 0), (width, 8)], fill=accent_color)

    # Title card background
    draw.rectangle([(60, 60), (width - 60, 160)], fill=(30, 41, 59))
    draw.rectangle([(60, 60), (70, 160)], fill=accent_color)

    # Simple text rendering
    draw.text((90, 80), title, fill=(248, 250, 252))
    draw.text((90, 120), subtitle, fill=(148, 163, 184))

    # Bullets
    y = 220
    for bullet in bullets:
        draw.rectangle([(90, y + 8), (98, y + 16)], fill=accent_color)
        draw.text((120, y), bullet, fill=(226, 232, 240))
        y += 70

    # Watermark / Footer
    draw.text((60, height - 50), "CONFIDENTIAL • INTERNAL ENGINEERING ALL-HANDS", fill=(71, 85, 105))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=90)
    return output_path


def seed_demo_meeting():
    print("Creating demo meeting: 'Q3 Cloud Migration & Performance Bottleneck'...")

    # Clear existing demo if present
    Meeting.objects.filter(title__icontains="Q3 Cloud Migration").delete()

    meeting = Meeting.objects.create(
        title="Q3 Cloud Migration & Performance Bottleneck",
        duration_seconds=185.0,
        status=Meeting.Status.COMPLETED,
        status_detail="All local models finished successfully.",
        progress=100,
    )

    media_dir = os.path.join(settings.MEDIA_ROOT, 'processed', str(meeting.id), 'frames')
    os.makedirs(media_dir, exist_ok=True)

    # 1. Slides Generation & ScreenFrame Models
    slides_data = [
        {
            "filename": "frame_0000.jpg",
            "time": 0.0,
            "title": "Q3 Engineering Review: Service Latency & Scale",
            "subtitle": "Architecture & Production Incidents Overview",
            "bullets": [
                "P99 API response time degraded from 110ms to 480ms",
                "High concurrency traffic spike during October campaign",
                "Customer churn risk identified across Tier-1 enterprise users",
            ],
            "accent": (99, 102, 241),
        },
        {
            "filename": "frame_0001.jpg",
            "time": 45.0,
            "title": "Root Cause: Redis Connection Pool Exhaustion",
            "subtitle": "Thread Pool Saturation under load",
            "bullets": [
                "Max connection limit hardcoded to 50 sockets",
                "Workers hanging on timeout waiting for pooled connection",
                "Memory usage spike: 89% saturation on primary cache node",
            ],
            "accent": (239, 68, 68),
        },
        {
            "filename": "frame_0002.jpg",
            "time": 95.0,
            "title": "Mitigation Strategy: Async Pooling & Circuit Breaker",
            "subtitle": "Proposed Architecture Fix for Phase 2",
            "bullets": [
                "Scale connection pool dynamically from 50 to 250 connections",
                "Introduce circuit breaker with 500ms fallback cache read",
                "Migrate background jobs off the primary synchronous path",
            ],
            "accent": (16, 185, 129),
        },
        {
            "filename": "frame_0003.jpg",
            "time": 150.0,
            "title": "Action Plan & Deployment Timeline",
            "subtitle": "Owner commitments before sprint freeze",
            "bullets": [
                "Sarah: Deploy Redis pool configuration update by Friday 5 PM",
                "Alex: Implement circuit breaker middleware and stress test",
                "Marcus: Monitor Datadog metrics and alert threshold adjustments",
            ],
            "accent": (245, 158, 11),
        },
    ]

    for s in slides_data:
        full_path = os.path.join(media_dir, s['filename'])
        generate_slide_image(
            full_path,
            s['title'],
            s['subtitle'],
            s['bullets'],
            accent_color=s['accent']
        )
        rel_path = f"processed/{meeting.id}/frames/{s['filename']}"
        ocr_text = f"{s['title']}\n{s['subtitle']}\n" + "\n".join(s['bullets'])

        ScreenFrame.objects.create(
            meeting=meeting,
            timestamp=s['time'],
            frame_path=rel_path,
            ocr_text=ocr_text,
        )

    # 2. Transcript Segments (Realistic spoken dialog)
    dialogue = [
        (0.0, 18.0, "Welcome everyone. Let's look at the first slide here showing our Q3 response times. As you can see, our P99 latency degraded from 110 milliseconds up to 480 milliseconds during peak traffic."),
        (19.0, 42.0, "Our enterprise tier customers have definitely started noticing this lag. We need to isolate whether this is database indexing or an upstream network bottleneck."),
        (45.0, 75.0, "Turning to slide two, the telemetry is clear. We hit Redis connection pool exhaustion. The connection pool was capped at only 50 connections, so worker threads were backed up waiting on sockets."),
        (76.0, 94.0, "Notice the cache node was running at 89% memory saturation. Once the queue filled up, incoming HTTP requests simply timed out."),
        (95.0, 130.0, "Here is our mitigation plan on slide three. We are scaling the connection pool up to 250 sockets and adding a circuit breaker fallback so timeouts fail gracefully."),
        (131.0, 149.0, "We also need to decouple synchronous workers from asynchronous queues so background exports don't choke request handling."),
        (150.0, 182.0, "Wrapping up with the action items on the last slide. Sarah, you have the Redis config deployment by Friday 5 PM. Alex will write the circuit breaker middleware, and Marcus will recalibrate the alerts."),
    ]

    for start, end, text in dialogue:
        TranscriptSegment.objects.create(
            meeting=meeting,
            start_time=start,
            end_time=end,
            text=text,
        )

    # 3. Summary & Correlations
    overview = (
        "During the Q3 Engineering Review, the team investigated severe P99 API latency spikes (110ms to 480ms). "
        "Telemetry confirmed the root cause was Redis connection pool exhaustion capped at 50 connections with 89% cache memory saturation. "
        "The team agreed to expand the pool to 250 connections, introduce a circuit breaker fallback, and assigned owners for deployment before Friday."
    )

    key_points = [
        "P99 latency degraded from 110ms to 480ms during high concurrency campaigns.",
        "Root cause isolated to hardcoded Redis connection pool exhaustion (50 max connections).",
        "Cache memory reached 89% saturation, causing worker thread timeouts.",
        "Solution involves dynamic connection scaling (up to 250) and circuit breaker middleware.",
    ]

    action_items = [
        "Sarah to deploy updated Redis connection pool configuration (250 sockets) by Friday 5 PM.",
        "Alex to implement circuit breaker fallback middleware and execute stress tests.",
        "Marcus to update Datadog alert thresholds and monitor post-deployment latency.",
    ]

    correlations = [
        {
            "timestamp": "00:00",
            "speech": "As you can see, our P99 latency degraded from 110 milliseconds up to 480 milliseconds during peak traffic.",
            "screen": "Q3 Engineering Review: Service Latency & Scale\nP99 API response time degraded from 110ms to 480ms",
            "insight": "Speaker directly points out the 110ms to 480ms latency spike shown on the title review slide."
        },
        {
            "timestamp": "00:45",
            "speech": "Turning to slide two, the telemetry is clear. We hit Redis connection pool exhaustion... capped at only 50 connections.",
            "screen": "Root Cause: Redis Connection Pool Exhaustion\nMax connection limit hardcoded to 50 sockets\nMemory saturation 89%",
            "insight": "Speaker refers to the root cause diagram detailing socket pool saturation and 89% cache memory load."
        },
        {
            "timestamp": "02:30",
            "speech": "Wrapping up with the action items on the last slide. Sarah, you have the Redis config deployment by Friday 5 PM...",
            "screen": "Action Plan & Deployment Timeline\nSarah: Deploy Redis pool configuration update by Friday 5 PM\nAlex: Implement circuit breaker",
            "insight": "Spoken ownership assignments directly match the names and deadlines listed on the final commitments slide."
        }
    ]

    MeetingSummary.objects.create(
        meeting=meeting,
        overview=overview,
        key_points=json.dumps(key_points),
        action_items=json.dumps(action_items),
        correlations=json.dumps(correlations),
        full_summary=overview,
    )

    print("Demo meeting created successfully! ID:", meeting.id)


if __name__ == '__main__':
    seed_demo_meeting()
