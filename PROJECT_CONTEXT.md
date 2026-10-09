# 🧠 MeetMind — Privacy-First Local AI Meeting Assistant

> **Tagline:** Your meetings, your device, your data. Never leaves your machine.
> **Hackathon:** Local AI Hackathon (October 2026)
> **Team Device:** Windows Laptop — NVIDIA RTX 3050 (4GB VRAM), Python 3.14.6
> **Time Budget:** ~12 hours

---

## ⚡ Active Operational Commands

For any agent or developer executing tasks:
```powershell
# 1. Virtual environment activation
.\venv\Scripts\activate

# 2. Seed instant demonstration session
python scripts\create_demo_data.py

# 3. Launch application server (runs on port 8000)
python manage.py runserver 127.0.0.1:8000

# 4. Pull/Monitor Ollama model in terminal (shows live progress bar):
ollama pull phi3:mini

# Direct GGUF download link (via browser/FDM, 2.39 GB):
# https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
# Save to: c:\Users\Jymce\Desktop\hackathonjymce\models\Phi-3-mini-4k-instruct-q4.gguf
# Import into Ollama: ollama create phi3:mini -f Modelfile

# Or ultra-fast lightweight alternative (390MB, ~2 mins):
ollama pull qwen2.5:0.5b
```

---

## Problem Statement

Meeting recordings contain highly sensitive business discussions — strategy, financials, HR decisions, client data. Yet current transcription/summarization tools (Otter.ai, Fireflies, Google Meet transcripts) send **all audio to cloud servers**. This creates:

- 🔓 **Privacy risks** — sensitive conversations stored on 3rd party servers
- 💸 **Ongoing costs** — $0.006/min adds up across thousands of meeting hours
- 🌐 **Internet dependency** — no transcription without connectivity
- ❌ **No screen context** — existing tools only transcribe speech, completely ignoring what's being shown on screen

## Our Solution

**MeetMind** is a Django web application that processes meeting recordings **entirely on the user's device** using local AI models. Users upload a **single meeting video file** (e.g., a Zoom/Teams/Meet recording that captures the shared screen), and MeetMind automatically:

1. 🎬 **Extracts Audio + Screen Frames** — FFmpeg splits the video into an audio track and sampled screen frames (every 5-10 seconds, skipping duplicates)
2. 🎙️ **Local Speech-to-Text** — Whisper model transcribes the extracted audio on GPU
3. 📸 **Local Screen/Document Analysis** — OCR extracts text content from sampled screen frames
4. 🤖 **Local AI Summarizer** — Local LLM generates meeting summaries, action items, and **correlates spoken content with on-screen content** using shared timestamps
5. 🔍 **Local Semantic Search (RAG)** — Search across all past meetings using local embeddings — no data ever leaves the machine

### What Makes This Unique: Multi-Modal Correlation

Most meeting summarizers only do **speech → text → summary**. MeetMind does:

```
                    ┌──→ Extract Audio ──→ faster-whisper ──→ Timestamped Transcript ──┐
Meeting Video (.mp4)│                                                                  ├──→ Correlated Summary
                    └──→ Extract Frames (every N sec) ──→ EasyOCR ──→ Screen Text ──┘     + Action Items
```

**Example output:**
> "At 12:34, while showing the Q3 Revenue Dashboard (slide captured), Sarah mentioned that
> revenue dropped 15% and proposed cutting the marketing budget. ACTION: Sarah to prepare
> revised marketing budget by Friday."

This **correlation between what was said and what was shown** is something even most cloud tools don't do, and it's especially valuable for:
- Technical meetings where code/architecture diagrams are shared
- Business reviews with dashboards and charts
- Educational lectures with slide presentations

---

## Why Local AI Wins Here

| Aspect | Cloud Approach | MeetMind (Local) |
|--------|---------------|-----------------|
| **Privacy** | Audio sent to 3rd party servers | Audio never leaves your device |
| **Cost** | $0.006/min × thousands of hours | Free after model download |
| **Latency** | Network round-trip + queue wait | Direct GPU processing |
| **Offline** | ❌ No internet = no transcription | ✅ Works in airplane mode |
| **Compliance** | GDPR/HIPAA concerns | Data stays on-premises |
| **Screen Context** | ❌ Most tools ignore screen content | ✅ Full multi-modal analysis |

---

## Tech Stack

| Component | Technology | Role | Runs On |
|-----------|-----------|------|---------|
| Backend Framework | **Django 5** | Web server, API, async tasks | CPU |
| Video Processing | **FFmpeg** | Extract audio track + screen frames from video | CPU |
| Local Speech-to-Text | **faster-whisper** (small model) | Transcribe extracted audio | GPU (~1GB VRAM) |
| Local LLM | **Ollama + Phi-3-mini-4k-instruct (Q4_K_M)** | Summarization, correlation, chat | GPU (~2.5GB VRAM) |
| Local OCR | **EasyOCR** (PaddleOCR/Tesseract fallbacks) | Extract text from screen frames | CPU |
| Local Embeddings | **sentence-transformers** (all-MiniLM-L6-v2) | Embed transcript chunks for search | CPU |
| Vector Database | **ChromaDB** | Store & query embeddings locally | CPU (file-based) |
| Frontend | **HTML / CSS / JavaScript** | Responsive web UI | Browser |
| Database | **SQLite** | Meeting metadata, transcripts | CPU (file-based) |

### VRAM Budget (RTX 3050 4GB)

Models are loaded **sequentially** (not simultaneously) to stay within VRAM limits:

| Step | Model | VRAM |
|------|-------|------|
| 1. Extract A/V | FFmpeg (not a model) | N/A |
| 2. Transcribe | faster-whisper small | ~1 GB |
| 3. OCR Frames | EasyOCR | CPU only |
| 4. Embed | all-MiniLM-L6-v2 | CPU only |
| 5. Summarize | Phi-3-mini Q4_K_M | ~2.5 GB |
| **Peak** | | **~2.5 GB ✅** |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Browser (Web UI)                    │
│       Upload Meeting Video (.mp4/.webm) ─── Chat     │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────▼──────────────────────────────┐
│                  Django Backend                       │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Upload &    │  │ Meeting      │  │ Search &    │ │
│  │ Processing  │  │ Dashboard    │  │ Chat API    │ │
│  └──────┬──────┘  └──────────────┘  └──────┬──────┘ │
│         │                                   │        │
│  ┌──────▼──────────────────────────────────▼──────┐  │
│  │           Local AI Processing Pipeline          │  │
│  │                                                 │  │
│  │  Step 1: FFmpeg → Extract audio + screen frames │  │
│  │  Step 2: faster-whisper → Timestamped transcript│  │
│  │  Step 3: EasyOCR → Screen text from frames      │  │
│  │  Step 4: sentence-transformers → Embeddings     │  │
│  │  Step 5: ChromaDB → Vector storage & retrieval  │  │
│  │  Step 6: Ollama (Phi-3) → Summary + Correlation │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ⚡ ALL AI RUNS LOCALLY — ZERO CLOUD AI APIs ⚡       │
└───────────────────────────────────────────────────────┘
```

---

## Django Project Structure

```
hackathonjymce/
├── PROJECT_CONTEXT.md          ← This file
├── manage.py
├── meetmind/                   ← Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── meetings/                   ← Main Django app
│   ├── models.py               ← Meeting, Transcript, ScreenFrame, Summary models
│   ├── views.py                ← Upload, dashboard, search views
│   ├── urls.py
│   ├── tasks.py                ← Async AI processing pipeline
│   ├── ai/
│   │   ├── extractor.py        ← FFmpeg: extract audio + frames from video
│   │   ├── transcriber.py      ← faster-whisper integration
│   │   ├── ocr.py              ← EasyOCR/PaddleOCR/Tesseract integration
│   │   ├── summarizer.py       ← Ollama/Phi-3 integration
│   │   ├── embeddings.py       ← sentence-transformers + ChromaDB
│   │   └── correlator.py       ← Match transcript ↔ screen content by timestamp
│   └── templates/
│       └── meetings/
│           ├── base.html
│           ├── upload.html
│           ├── dashboard.html
│           ├── meeting_detail.html
│           └── search.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── media/                      ← Uploaded video files + extracted frames
│   ├── videos/                 ← Original uploaded meeting videos
│   ├── audio/                  ← Extracted audio tracks
│   └── frames/                 ← Extracted screen frames (per meeting)
├── chroma_db/                  ← Local vector database
└── requirements.txt
```

---

## Key Features

### 1. Single Video Upload & Automatic Processing
- Upload meeting video files (mp4, webm, mkv, avi)
- **FFmpeg automatically extracts**: audio track + screen frames (sampled every 5-10 seconds)
- Smart frame deduplication: skips near-identical frames to save processing time
- Background processing with real-time progress indicator

### 2. Timestamped Transcript
- Word-level timestamps from faster-whisper
- Timestamps are naturally synced with video frames (both come from the same video)
- Speaker diarization (stretch goal)

### 3. Automatic Screen Content Extraction
- FFmpeg extracts frames at regular intervals from the video
- EasyOCR extracts text from each frame
- Each frame's text is tagged with its video timestamp
- Display screen content alongside transcript in a unified timeline

### 4. AI-Generated Summary with Multi-Modal Correlation
- Meeting overview summary
- Key discussion points
- Action items with assignees
- **Correlation**: automatically links what was said to what was on screen using shared timestamps
- Example: "At 5:32, while the Q3 Dashboard was displayed, the team discussed revenue decline"
- Generated entirely by local LLM (Phi-3 via Ollama)

### 5. Semantic Search (RAG)
- Search across all past meetings by meaning, not just keywords
- "Chat with your meetings" — ask questions, get answers with sources
- Powered by local embeddings + ChromaDB

---

## Hackathon Disclosure (Required)

| Category | Details |
|----------|---------|
| **Models** | OpenAI Whisper (small), Microsoft Phi-3-mini-4k-instruct (Q4_K_M), all-MiniLM-L6-v2 |
| **Frameworks** | Django 5, faster-whisper, Ollama, sentence-transformers, ChromaDB, EasyOCR |
| **Tools** | FFmpeg (video processing) |
| **Languages** | Python 3.14, HTML/CSS/JavaScript |
| **Development Tools** | AI-assisted development (Google Antigravity IDE) |
| **Cloud Dependencies** | **None** — all AI inference is 100% local |
| **Hardware** | NVIDIA RTX 3050 Laptop GPU (4GB VRAM) |

---

## For Other AI Agents

If you are an AI agent reading this file for context:

- This is a **Django web application** — follow Django conventions
- All AI models run **locally** — never add cloud AI API calls
- VRAM is limited to **4GB** — keep models small and load sequentially
- The project uses **SQLite** (no external database server)
- Frontend is **vanilla HTML/CSS/JS** — no React/Vue/Angular
- The main app is called `meetings`
- AI processing modules live in `meetings/ai/`
- **Input is a single video file** — FFmpeg extracts audio + frames, do NOT ask users for separate audio/screenshot uploads
- **FFmpeg is required** — must be installed on the system PATH
- Media files are organized: `media/videos/`, `media/audio/`, `media/frames/`
- Timestamps from audio transcription and frame extraction are used to correlate speech with screen content
- Follow the architecture and file structure described above
- **Frontend uses Tailwind CSS (CDN) + shadcn/ui design tokens** — dark zinc theme, all CSS variables defined in `base.html`
- **Lucide icons** are used via unpkg CDN (`<i data-lucide="icon-name">`) — call `lucide.createIcons()` after dynamic DOM updates
- **Cache busting**: static JS uses `?v=N` query parameter in `base.html` — increment when modifying `app.js`

---

## 🚀 Next Features Roadmap (For Devin / Future Development)

The following three features should be implemented in order. Each section contains the exact files to modify, the approach, and design constraints.

### Feature 1: Toast Notification System

**Goal:** Replace all `alert()` and `confirm()` calls with elegant shadcn-style toast notifications that slide in from the bottom-right corner.

**Files to modify:**
- `meetings/templates/meetings/base.html` — Add toast container HTML + CSS
- `static/js/app.js` — Add `showToast(message, type, duration)` utility function
- Replace all `alert()` calls in `app.js` with `showToast()`

**Implementation details:**

1. **Add a toast container** to `base.html` just before `</body>`:
   ```html
   <div id="toastContainer" class="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"></div>
   ```

2. **Create `showToast()` function** in `app.js`:
   ```javascript
   window.showToast = function(message, type = 'info', duration = 4000) {
       // type: 'success' | 'error' | 'info' | 'warning'
       // Create toast element with shadcn styling:
       //   - rounded-xl border bg-card shadow-lg backdrop-blur
       //   - Icon on left (lucide): check-circle-2 (success), alert-triangle (error), info (info)
       //   - Color accents: emerald (success), rose (error), amber (warning), indigo (info)
       //   - Slide-in animation from right (translateX(100%) → translateX(0))
       //   - Auto-dismiss after `duration` ms with fade-out
       //   - Close button (X) on the right
       //   - pointer-events-auto on individual toasts so they're clickable
   }
   ```

3. **Replace these calls in `app.js`:**
   - `deleteMeeting()`: Replace `alert('Failed to delete meeting.')` → `showToast(data.error, 'error')`
   - `deleteMeeting()`: Replace `alert('Failed to connect to server.')` → `showToast('...', 'error')`
   - `deleteMeeting()` success: Add `showToast('Meeting deleted successfully', 'success')` after card fade-out
   - `confirm()` in delete: Keep `confirm()` for destructive actions OR replace with a custom modal

4. **Also add toasts in views that redirect** — use Django messages framework:
   - `pip install django-contrib-messages` (already built-in)
   - Add `django.contrib.messages` middleware if not present
   - In `views.py`: `messages.success(request, 'Meeting deleted successfully')`
   - In `base.html`: Loop over `messages` and call `showToast()` for each

**Design reference:** Match the shadcn/ui Toast component — dark background, subtle border, icon + text layout, 280-360px wide.

---

### Feature 2: Export Meeting Notes as PDF & Markdown

**Goal:** Add "Export" buttons on the meeting detail page that generate downloadable PDF and Markdown files containing the full meeting summary, transcript, action items, and correlations.

**Files to create:**
- `meetings/export.py` — Export logic (PDF generation + Markdown formatting)

**Files to modify:**
- `meetings/views.py` — Add `export_meeting_pdf` and `export_meeting_markdown` views
- `meetings/urls.py` — Add export URL routes
- `meetings/templates/meetings/meeting_detail.html` — Add export buttons in the action bar

**Dependencies to add to `requirements.txt`:**
```
reportlab>=4.0
```
> `reportlab` is a pure-Python PDF generator — no external binaries needed, works offline.

**Implementation details:**

1. **Create `meetings/export.py`:**

   ```python
   # Markdown export function
   def generate_markdown(meeting, transcript_segments, screen_frames, summary):
       """Returns a string of formatted Markdown containing the full meeting report."""
       # Structure:
       # # Meeting Title
       # **Date:** ...  |  **Duration:** ...
       # ## Executive Summary
       # {summary.overview}
       # ## Key Discussion Points
       # - point 1
       # - point 2
       # ## Action Items
       # - [ ] item 1
       # - [ ] item 2
       # ## Speech ↔ Screen Correlations
       # | Timestamp | What Was Said | Screen Content | AI Insight |
       # |-----------|--------------|----------------|------------|
       # ## Full Transcript
       # | Time | Text |
       # |------|------|
       # | 00:00 | ... |

   # PDF export function
   def generate_pdf(meeting, transcript_segments, screen_frames, summary):
       """Returns a BytesIO buffer containing a styled PDF report."""
       # Use reportlab:
       # - from reportlab.lib.pagesizes import A4
       # - from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer
       # - from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
       # - Custom dark-themed styles (or professional light theme for printability)
       # - Include: Title, date, summary, key points, action items, correlations table, transcript
       # - Add page numbers in footer
       # - Add "Generated by MeetMind — Local AI Meeting Intelligence" watermark
   ```

2. **Add views in `meetings/views.py`:**
   ```python
   from django.http import HttpResponse
   from .export import generate_markdown, generate_pdf

   def export_meeting_markdown(request, meeting_id):
       meeting = get_object_or_404(Meeting, id=meeting_id)
       # ... gather transcript_segments, screen_frames, summary
       md_content = generate_markdown(meeting, ...)
       response = HttpResponse(md_content, content_type='text/markdown')
       response['Content-Disposition'] = f'attachment; filename="meetmind_{meeting.title}.md"'
       return response

   def export_meeting_pdf(request, meeting_id):
       meeting = get_object_or_404(Meeting, id=meeting_id)
       # ... gather data
       pdf_buffer = generate_pdf(meeting, ...)
       response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
       response['Content-Disposition'] = f'attachment; filename="meetmind_{meeting.title}.pdf"'
       return response
   ```

3. **Add URL routes in `meetings/urls.py`:**
   ```python
   path('meeting/<uuid:meeting_id>/export/md/', views.export_meeting_markdown, name='export_markdown'),
   path('meeting/<uuid:meeting_id>/export/pdf/', views.export_meeting_pdf, name='export_pdf'),
   ```

4. **Add export buttons in `meeting_detail.html`** — in the top action bar (`div.flex.items-center.gap-2`), next to "Re-run Analysis" and "Delete Session":
   ```html
   {% if meeting.status == 'completed' %}
   <a href="{% url 'export_markdown' meeting.id %}" class="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium text-foreground shadow-sm transition hover:bg-secondary">
       <i data-lucide="file-text" class="h-3.5 w-3.5"></i>
       <span>Export .md</span>
   </a>
   <a href="{% url 'export_pdf' meeting.id %}" class="inline-flex items-center gap-1.5 rounded-md border border-indigo-500/20 bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-400 shadow-sm transition hover:bg-indigo-500/20">
       <i data-lucide="file-down" class="h-3.5 w-3.5"></i>
       <span>Export PDF</span>
   </a>
   {% endif %}
   ```

---

### Feature 3: Meeting Comparison View

**Goal:** Allow users to select 2-3 meetings and see a side-by-side comparison of their summaries, key points, action items, and topic overlap. This showcases the power of local vector search across meetings.

**Files to create:**
- `meetings/templates/meetings/compare.html` — Comparison view template

**Files to modify:**
- `meetings/views.py` — Add `compare_meetings_view`
- `meetings/urls.py` — Add comparison URL route
- `meetings/templates/meetings/dashboard.html` — Add checkboxes for selecting meetings + "Compare" button
- `meetings/ai/embeddings.py` — Add `find_common_topics()` function (optional enhancement)

**Implementation details:**

1. **Dashboard changes** — Add selection mode:
   - Add a "Compare" toggle button in the dashboard header
   - When active, show checkboxes on each meeting card (only for completed meetings)
   - Show a floating action bar at the bottom: "Compare N Selected" button (enabled when 2-3 selected)
   - JavaScript to track selected meeting IDs and navigate to `/compare/?ids=uuid1,uuid2,uuid3`

2. **Create comparison view in `views.py`:**
   ```python
   def compare_meetings_view(request):
       ids = request.GET.get('ids', '').split(',')
       meetings = Meeting.objects.filter(id__in=ids, status=Meeting.Status.COMPLETED)
       
       if meetings.count() < 2:
           return redirect('dashboard')
       
       comparison_data = []
       for meeting in meetings:
           summary = getattr(meeting, 'summary', None)
           comparison_data.append({
               'meeting': meeting,
               'summary': summary,
               'key_points': json.loads(summary.key_points) if summary and summary.key_points else [],
               'action_items': json.loads(summary.action_items) if summary and summary.action_items else [],
               'correlations': json.loads(summary.correlations) if summary and summary.correlations else [],
               'transcript_count': meeting.transcript_segments.count(),
               'frame_count': meeting.screen_frames.count(),
           })
       
       return render(request, 'meetings/compare.html', {'comparison_data': comparison_data})
   ```

3. **URL route:**
   ```python
   path('compare/', views.compare_meetings_view, name='compare_meetings'),
   ```

4. **Template `compare.html` design:**
   - Breadcrumb: Library → Compare Meetings
   - Side-by-side cards (2-3 columns) showing for each meeting:
     - Title, date, duration badge
     - Executive summary
     - Key points list
     - Action items list
     - Correlation count
   - Highlight **common topics** between meetings (optional: use embedding similarity)
   - At the bottom: "Combined Action Items" section aggregating all action items across meetings
   - Use the same shadcn dark theme, Tailwind classes, and Lucide icons

5. **(Optional) Common topic detection** in `embeddings.py`:
   ```python
   def find_common_topics(meeting_ids, chroma_dir, top_k=10):
       """Find overlapping topics across multiple meetings using vector similarity."""
       # Query ChromaDB for each meeting's top embeddings
       # Compare embedding clusters to find semantic overlap
       # Return list of common themes
   ```

---

### General Implementation Notes for All Features

- **Tailwind CSS** is loaded via CDN in `base.html` — no build step needed
- **shadcn design tokens** are defined as CSS variables in `base.html <style>` block
- **Lucide icons**: Use `<i data-lucide="icon-name">` and call `lucide.createIcons()` after any DOM update
- **Cache busting**: After modifying `static/js/app.js`, increment the `?v=N` query parameter in `base.html` line 196
- **Django CSRF**: For AJAX POST requests, either use `@csrf_exempt` decorator or send the `X-CSRFToken` header
- **Testing**: Run `python manage.py runserver` and test each feature manually in the browser
- **No cloud APIs**: All features must work 100% offline — do not add any external API calls
- **Python dependencies**: Only add packages available via pip that work offline after install

