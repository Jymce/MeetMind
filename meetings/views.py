import json
import logging
import os
import shutil
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Meeting, TranscriptSegment, ScreenFrame, MeetingSummary
from .tasks import process_meeting_async
from .ai import embeddings, summarizer
from .export import generate_markdown, generate_pdf, parse_summary

logger = logging.getLogger(__name__)


def dashboard_view(request):
    """Main dashboard displaying meeting history and status."""
    meetings = Meeting.objects.all()
    total_meetings = meetings.count()
    completed_meetings = meetings.filter(status=Meeting.Status.COMPLETED).count()
    in_progress = meetings.exclude(status__in=[Meeting.Status.COMPLETED, Meeting.Status.FAILED]).count()

    context = {
        'meetings': meetings,
        'total_meetings': total_meetings,
        'completed_meetings': completed_meetings,
        'in_progress': in_progress,
        'ollama_model': getattr(settings, 'OLLAMA_MODEL', 'phi3:mini'),
        'whisper_model': getattr(settings, 'WHISPER_MODEL_SIZE', 'small'),
        'whisper_device': getattr(settings, 'WHISPER_DEVICE', 'cuda'),
    }
    return render(request, 'meetings/dashboard.html', context)


def upload_view(request):
    """Upload a new meeting recording video."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or 'Untitled Meeting'
        video_file = request.FILES.get('video_file')

        if not video_file:
            return render(request, 'meetings/upload.html', {'error': 'Please select a video file.'})

        meeting = Meeting.objects.create(
            title=title,
            video_file=video_file,
            status=Meeting.Status.UPLOADED,
            progress=5,
            status_detail='Uploaded. Queued for AI processing...',
        )

        # Kick off background processing
        process_meeting_async(str(meeting.id))
        messages.success(request, f'Meeting "{meeting.title}" uploaded — local AI processing started.')
        return redirect('meeting_detail', meeting_id=meeting.id)

    return render(request, 'meetings/upload.html')


def meeting_detail_view(request, meeting_id):
    """View full analysis of a specific meeting."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    transcript_segments = list(meeting.transcript_segments.all())
    screen_frames = list(meeting.screen_frames.filter(is_duplicate=False))

    # Correlate each frame with the transcript segment active at its timestamp,
    # so text-poor slides still show what was being said while on screen.
    seg_idx = 0
    for frame in screen_frames:
        frame.spoken_text = ''
        while (seg_idx + 1 < len(transcript_segments)
               and transcript_segments[seg_idx + 1].start_time <= frame.timestamp):
            seg_idx += 1
        if transcript_segments and transcript_segments[seg_idx].start_time <= frame.timestamp:
            frame.spoken_text = transcript_segments[seg_idx].text

    summary_obj = getattr(meeting, 'summary', None)
    key_points = []
    action_items = []
    correlations = []

    if summary_obj:
        try:
            key_points = json.loads(summary_obj.key_points) if summary_obj.key_points else []
        except Exception:
            key_points = []
        try:
            action_items = json.loads(summary_obj.action_items) if summary_obj.action_items else []
        except Exception:
            action_items = []
        try:
            correlations = json.loads(summary_obj.correlations) if summary_obj.correlations else []
        except Exception:
            correlations = []

    context = {
        'meeting': meeting,
        'transcript_segments': transcript_segments,
        'transcript_count': len(transcript_segments),
        'screen_frames': screen_frames,
        'frame_count': len(screen_frames),
        'summary': summary_obj,
        'key_points': key_points,
        'action_items': action_items,
        'correlations': correlations,
    }
    return render(request, 'meetings/meeting_detail.html', context)


def meeting_status_api(request, meeting_id):
    """API endpoint to poll meeting processing progress."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    return JsonResponse({
        'id': str(meeting.id),
        'status': meeting.status,
        'status_label': meeting.get_status_display(),
        'status_detail': meeting.status_detail,
        'progress': meeting.progress,
        'completed': meeting.status == Meeting.Status.COMPLETED,
        'failed': meeting.status == Meeting.Status.FAILED,
    })





@csrf_exempt
@require_http_methods(["POST"])
def meeting_chat_api(request, meeting_id):
    """Ask a question about the meeting via local RAG (ChromaDB + Ollama)."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
    except Exception:
        return JsonResponse({'error': 'Invalid request payload'}, status=400)

    if not question:
        return JsonResponse({'error': 'Question cannot be empty'}, status=400)

    # 1. Retrieve semantic context from ChromaDB
    try:
        results = embeddings.search_meetings(
            query=question,
            chroma_dir=str(settings.CHROMA_DB_DIR),
            meeting_id=str(meeting.id),
            top_k=5,
        )
        context_text = "\n\n".join([f"[{r['metadata'].get('type', 'content').upper()}]: {r['text']}" for r in results])
    except Exception as e:
        logger.warning(f"ChromaDB retrieval error: {e}")
        # Fallback to in-database transcript
        segments = meeting.transcript_segments.all()[:30]
        context_text = "\n".join([f"[{s.formatted_start}]: {s.text}" for s in segments])

    # 2. Call local Ollama
    try:
        answer = summarizer.chat_with_meeting(
            question=question,
            context=context_text,
            model=getattr(settings, 'OLLAMA_MODEL', 'phi3:mini'),
            base_url=getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434'),
        )
        return JsonResponse({'answer': answer})
    except Exception as e:
        logger.error(f"Chat generation error: {e}")
        return JsonResponse({'error': f'Failed to generate response: {str(e)}'}, status=500)


def search_view(request):
    """Semantic search view across all meetings."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        try:
            raw_results = embeddings.search_meetings(
                query=query,
                chroma_dir=str(settings.CHROMA_DB_DIR),
                top_k=15,
            )
            # Enrich results with meeting titles
            meeting_cache = {}
            for item in raw_results:
                m_id = item['metadata'].get('meeting_id')
                if m_id and m_id not in meeting_cache:
                    try:
                        meeting_cache[m_id] = Meeting.objects.get(id=m_id)
                    except Meeting.DoesNotExist:
                        meeting_cache[m_id] = None
                
                item['meeting'] = meeting_cache.get(m_id)
                results.append(item)
        except Exception as e:
            logger.error(f"Semantic search error: {e}")

        # Fallback to database text match if vector search found nothing
        if not results:
            for seg in TranscriptSegment.objects.filter(text__icontains=query)[:10]:
                results.append({
                    'text': seg.text,
                    'metadata': {'type': 'speech', 'start_time': seg.start_time, 'meeting_id': str(seg.meeting.id)},
                    'meeting': seg.meeting,
                })
            for frame in ScreenFrame.objects.filter(ocr_text__icontains=query)[:5]:
                results.append({
                    'text': frame.ocr_text,
                    'metadata': {'type': 'screen', 'timestamp': frame.timestamp, 'meeting_id': str(frame.meeting.id)},
                    'meeting': frame.meeting,
                })

    return render(request, 'meetings/search.html', {'query': query, 'results': results})


def reprocess_meeting_view(request, meeting_id):
    """Trigger reprocessing for an existing meeting."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    meeting.transcript_segments.all().delete()
    meeting.screen_frames.all().delete()
    if hasattr(meeting, 'summary'):
        meeting.summary.delete()

    meeting.status = Meeting.Status.UPLOADED
    meeting.progress = 5
    meeting.status_detail = "Restarting processing pipeline..."
    meeting.save()

    process_meeting_async(str(meeting.id))
    messages.info(request, f'Reprocessing "{meeting.title}" — pipeline restarted.')
    return redirect('meeting_detail', meeting_id=meeting.id)


def compare_meetings_view(request):
    """Side-by-side comparison of 2-3 completed meetings."""
    ids = [i for i in request.GET.get('ids', '').split(',') if i]
    fetched = {str(m.id): m for m in Meeting.objects.filter(id__in=ids, status=Meeting.Status.COMPLETED)}
    meetings = [fetched[i] for i in ids if i in fetched]  # preserve selection order

    if len(meetings) < 2:
        messages.warning(request, 'Select 2–3 completed meetings to compare.')
        return redirect('dashboard')

    comparison_data = []
    combined_action_items = []
    for meeting in meetings:
        summary = getattr(meeting, 'summary', None)
        key_points, action_items, correlations = parse_summary(summary)
        comparison_data.append({
            'meeting': meeting,
            'summary': summary,
            'key_points': key_points,
            'action_items': action_items,
            'correlations': correlations,
            'transcript_count': meeting.transcript_segments.count(),
            'frame_count': meeting.screen_frames.count(),
        })
        for item in action_items:
            combined_action_items.append({'text': item, 'meeting': meeting.title})

    common_topics = embeddings.find_common_topics(
        [str(m.id) for m in meetings],
        chroma_dir=str(settings.CHROMA_DB_DIR),
    )

    return render(request, 'meetings/compare.html', {
        'comparison_data': comparison_data,
        'common_topics': common_topics,
        'combined_action_items': combined_action_items,
    })


def export_meeting_markdown(request, meeting_id):
    """Download the full meeting report as a Markdown file."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    md_content = generate_markdown(
        meeting,
        meeting.transcript_segments.all(),
        meeting.screen_frames.filter(is_duplicate=False),
        getattr(meeting, 'summary', None),
    )
    filename = slugify(meeting.title) or 'meeting'
    response = HttpResponse(md_content, content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="meetmind_{filename}.md"'
    return response


def export_meeting_pdf(request, meeting_id):
    """Download the full meeting report as a styled PDF file."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    try:
        pdf_buffer = generate_pdf(
            meeting,
            meeting.transcript_segments.all(),
            meeting.screen_frames.filter(is_duplicate=False),
            getattr(meeting, 'summary', None),
        )
    except Exception as e:
        logger.error(f"PDF export failed for meeting {meeting_id}: {e}")
        messages.error(request, f'Failed to generate PDF: {e}')
        return redirect('meeting_detail', meeting_id=meeting.id)

    filename = slugify(meeting.title) or 'meeting'
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="meetmind_{filename}.pdf"'
    return response


@csrf_exempt
@require_http_methods(["POST"])
def delete_meeting_view(request, meeting_id):
    """Delete a meeting and all its associated files and data."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    meeting_title = meeting.title

    try:
        # 1. Clean up the processed directory (audio, frames, etc.)
        processed_dir = os.path.join(settings.MEDIA_ROOT, 'processed', str(meeting.id))
        if os.path.exists(processed_dir):
            shutil.rmtree(processed_dir, ignore_errors=True)
            logger.info(f"Removed processed directory: {processed_dir}")

        # 2. Clean up the uploaded video file
        if meeting.video_file:
            video_path = os.path.join(settings.MEDIA_ROOT, str(meeting.video_file))
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"Removed video file: {video_path}")

        # 3. Remove this meeting's vectors from the shared ChromaDB collection
        try:
            import chromadb
            chroma_dir = str(settings.CHROMA_DB_DIR)
            if os.path.exists(chroma_dir):
                client = chromadb.PersistentClient(path=chroma_dir)
                collection = client.get_collection("meetmind_meetings")
                collection.delete(where={"meeting_id": str(meeting.id)})
                logger.info(f"Removed ChromaDB vectors for meeting {meeting.id}")
        except Exception as e:
            logger.debug(f"ChromaDB cleanup skipped: {e}")

        # 4. Delete database record (cascades to segments, frames, summary)
        meeting.delete()
        logger.info(f"Deleted meeting '{meeting_title}' ({meeting_id})")

    except Exception as e:
        logger.error(f"Error deleting meeting {meeting_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=500)
        messages.error(request, f'Failed to delete meeting: {e}')
        return redirect('dashboard')

    # Return JSON for AJAX or redirect for standard requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'Meeting "{meeting_title}" deleted.'})
    messages.success(request, f'Meeting "{meeting_title}" deleted.')
    return redirect('dashboard')
