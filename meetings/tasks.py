"""
Background task runner for MeetMind.
Orchestrates the entire multi-modal AI processing pipeline.
"""
import os
import threading
import logging
from django.conf import settings
from .models import Meeting, TranscriptSegment, ScreenFrame, MeetingSummary
from .ai import extractor, transcriber, ocr, summarizer, embeddings, correlator

logger = logging.getLogger(__name__)

# Serialize pipelines so only one meeting hits GPU models at a time (4GB VRAM budget).
_pipeline_lock = threading.Lock()


def _update_meeting(meeting_id, **fields) -> bool:
    """Update meeting fields; returns False if the meeting was deleted mid-run."""
    return Meeting.objects.filter(id=meeting_id).update(**fields) > 0


def process_meeting_async(meeting_id: str):
    """Launch meeting processing in a background daemon thread."""
    thread = threading.Thread(target=_run_pipeline, args=(meeting_id,), daemon=True)
    thread.start()
    return thread


def _run_pipeline(meeting_id: str):
    """
    Executes the sequential local AI pipeline:
    1. Extract Audio & Frames (FFmpeg)
    2. Transcribe Audio (faster-whisper on GPU)
    3. Screen OCR on extracted frames (EasyOCR / PaddleOCR / Tesseract on CPU)
    4. Correlate speech with screen text & generate summary (Ollama Phi-3)
    5. Build Vector Search Index (ChromaDB + sentence-transformers)
    """
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting {meeting_id} does not exist.")
        return

    # Wait for any in-flight pipeline — keeps GPU model usage sequential
    _update_meeting(meeting_id, status_detail='Queued — waiting for GPU pipeline...')
    with _pipeline_lock:
        if not Meeting.objects.filter(id=meeting_id).exists():
            logger.info(f"Meeting {meeting_id} was deleted while queued. Skipping.")
            return
        _run_pipeline_steps(meeting_id)


def _run_pipeline_steps(meeting_id: str):
    """Inner pipeline body — always runs under _pipeline_lock."""
    meeting = Meeting.objects.get(id=meeting_id)
    try:
        video_path = meeting.video_file.path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file missing at {video_path}")

        # Directory setup
        meeting_dir = os.path.join(settings.MEDIA_ROOT, 'processed', str(meeting.id))
        audio_dir = os.path.join(meeting_dir, 'audio')
        frames_dir = os.path.join(meeting_dir, 'frames')
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)

        audio_path = os.path.join(audio_dir, 'extracted_audio.wav')
        _update_meeting(
            meeting_id,
            audio_path=os.path.relpath(audio_path, settings.MEDIA_ROOT),
            frames_dir=os.path.relpath(frames_dir, settings.MEDIA_ROOT),
        )

        # --- STEP 1: FFmpeg Extraction ---
        if not _update_meeting(meeting_id, status=Meeting.Status.EXTRACTING,
                               status_detail="Extracting audio track and screen frames...",
                               progress=10):
            return

        duration = extractor.get_video_duration(video_path)
        _update_meeting(meeting_id, duration_seconds=duration)

        extractor.extract_audio(video_path, audio_path)
        extracted_frames = extractor.extract_frames(
            video_path,
            frames_dir,
            interval=getattr(settings, 'FRAME_INTERVAL_SECONDS', 5)
        )
        extracted_frames = extractor.mark_duplicate_frames(extracted_frames)

        # Save preliminary ScreenFrame models
        created_frames = []
        for f in extracted_frames:
            rel_frame_path = os.path.relpath(f['path'], settings.MEDIA_ROOT).replace('\\', '/')
            sf = ScreenFrame.objects.create(
                meeting=meeting,
                timestamp=f['timestamp'],
                frame_path=rel_frame_path,
                is_duplicate=f.get('is_duplicate', False),
            )
            created_frames.append({
                'id': sf.id, 'timestamp': sf.timestamp, 'path': f['path'],
                'is_duplicate': f.get('is_duplicate', False),
            })

        # --- STEP 2: Transcribe (faster-whisper GPU) ---
        if not _update_meeting(meeting_id, status=Meeting.Status.TRANSCRIBING,
                               status_detail="Transcribing spoken audio with Whisper...",
                               progress=30):
            return

        raw_segments = transcriber.transcribe(
            audio_path,
            model_size=getattr(settings, 'WHISPER_MODEL_SIZE', 'small'),
            device=getattr(settings, 'WHISPER_DEVICE', 'cuda'),
        )

        transcript_records = []
        for seg in raw_segments:
            ts = TranscriptSegment(
                meeting=meeting,
                start_time=seg['start'],
                end_time=seg['end'],
                text=seg['text'],
            )
            transcript_records.append(ts)
        TranscriptSegment.objects.bulk_create(transcript_records)

        # Free Whisper GPU VRAM before next steps
        transcriber.unload_model()

        # --- STEP 3: Screen OCR (CPU — skips near-identical frames) ---
        if not _update_meeting(meeting_id, status=Meeting.Status.OCR_PROCESSING,
                               status_detail="Analyzing on-screen content and slides...",
                               progress=55):
            return

        unique_frames = [f for f in created_frames if not f['is_duplicate']]
        processed_ocr = ocr.process_frames(
            [{'path': f['path'], 'timestamp': f['timestamp']} for f in unique_frames]
        )

        # Update ScreenFrame database entries
        for orig, res in zip(unique_frames, processed_ocr):
            ScreenFrame.objects.filter(id=orig['id']).update(ocr_text=res.get('ocr_text', ''))

        # Prepare memory representations for summarizer and correlator
        transcript_data = [{'start': s.start_time, 'end': s.end_time, 'text': s.text} for s in transcript_records]
        screen_data = [{'timestamp': f['timestamp'], 'ocr_text': res.get('ocr_text', '')} for f, res in zip(unique_frames, processed_ocr)]

        # --- STEP 4: Correlate & Summarize (Ollama / Phi-3) ---
        if not _update_meeting(meeting_id, status=Meeting.Status.SUMMARIZING,
                               status_detail="Correlating speech with screen content and generating AI summary...",
                               progress=75):
            return

        # Compute direct correlations
        matched_correlations = correlator.correlate(transcript_data, screen_data)

        # Run LLM
        summary_result = summarizer.generate_summary(
            transcript_data,
            screen_data,
            model=getattr(settings, 'OLLAMA_MODEL', 'phi3:mini'),
            base_url=getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434'),
        )

        import json
        MeetingSummary.objects.update_or_create(
            meeting=meeting,
            defaults={
                'overview': summary_result.get('overview', ''),
                'key_points': json.dumps(summary_result.get('key_points', [])),
                'action_items': json.dumps(summary_result.get('action_items', [])),
                'correlations': json.dumps(summary_result.get('correlations', matched_correlations)),
                'full_summary': summary_result.get('full_summary', ''),
            }
        )

        # --- STEP 5: Indexing in ChromaDB ---
        if not _update_meeting(meeting_id, status=Meeting.Status.EMBEDDING,
                               status_detail="Indexing into local vector search...",
                               progress=90):
            return

        embeddings.index_meeting(
            str(meeting.id),
            transcript_data,
            screen_data,
            str(settings.CHROMA_DB_DIR)
        )

        # --- Done ---
        _update_meeting(meeting_id, status=Meeting.Status.COMPLETED,
                        status_detail="Processing complete! All insights ready.",
                        progress=100)
        logger.info(f"Meeting {meeting.id} processing successfully finished.")

    except Exception as e:
        logger.exception(f"Pipeline error processing meeting {meeting_id}: {e}")
        _update_meeting(meeting_id, status=Meeting.Status.FAILED,
                        status_detail=f"Failed: {str(e)}")
