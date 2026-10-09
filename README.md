# 🧠 MeetMind — Privacy-First Local AI Meeting Assistant

> **Your meetings, your device, your data. Never leaves your machine.**

MeetMind processes meeting recordings **entirely on your device** using local AI models. Upload a meeting video and get a timestamped transcript, screen content extraction, and an AI-generated summary that **correlates what was said with what was shown on screen** — all without sending a single byte to the cloud.

---

## 🎯 Why MeetMind?

Most meeting tools only transcribe speech. They throw away **half the meeting** — the screen.

When someone says *"as you can see here, the numbers dropped significantly"*, a speech-only tool gives you a useless transcript. MeetMind shows you the chart they were pointing at **and** what they said about it.

| Feature | Cloud Tools (Otter.ai, etc.) | MeetMind |
|---------|------------------------------|----------|
| Transcription | ✅ Cloud-based | ✅ **Local** (Whisper) |
| Screen content analysis | ❌ | ✅ **Local** (OCR) |
| Speech ↔ Screen correlation | ❌ | ✅ **Local** (LLM) |
| Privacy | ⚠️ Audio sent to servers | ✅ Never leaves device |
| Cost | 💸 Per-minute pricing | 🆓 Free forever |
| Works offline | ❌ | ✅ |

---

## 📋 Requirements

### Hardware
- **GPU**: NVIDIA GPU with at least **4GB VRAM** (e.g., RTX 3050, RTX 3060, RTX 4060, etc.)
  - AMD GPUs may work with ROCm but are untested
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: ~5GB free space (for models + dependencies)

### Software
- **OS**: Windows 10/11 (developed on Windows; Linux should also work)
- **Python**: 3.10 or higher
- **NVIDIA Drivers**: Up to date ([download here](https://www.nvidia.com/Download/index.aspx))
- **CUDA Toolkit**: 11.8+ (usually bundled with drivers)
- **FFmpeg**: Required for video processing ([download here](https://ffmpeg.org/download.html))
- **Ollama**: Required for the local LLM ([download here](https://ollama.com/download))

---

## ⚡ Setup

### Step 0 — Get the code

```powershell
git clone https://github.com/Jymce/MeetMind.git
cd MeetMind
```

> No git? On the GitHub page click **Code → Download ZIP**, extract it, then `cd` into the folder in PowerShell.

### Option A — One-Shot Installer (Recommended)

Double-click **`setup.bat`**, or run in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The script does everything automatically and is safe to re-run (it skips what's already done):

- ✅ Installs **Python 3.10+** if missing (via winget)
- ✅ Creates `venv` and installs `requirements.txt`
- ✅ Installs **Ollama** + pulls `phi3:mini` (~2.4 GB, resumable)
- ✅ Installs or auto-detects **FFmpeg**
- ✅ **Pre-downloads every AI model** (~700 MB): Whisper small, EasyOCR, all-MiniLM-L6-v2 — so the app works fully offline from the very first meeting
- ✅ Runs database migrations + optionally seeds a demo meeting

### Option B — Manual Setup

After cloning (Step 0), run everything yourself:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate

# Local LLM (one-time ~2.4 GB download, shows live progress):
ollama pull phi3:mini

# Or ultra-lightweight 390 MB alternative:
ollama pull qwen2.5:0.5b   # then set OLLAMA_MODEL = 'qwen2.5:0.5b' in meetmind/settings.py

# FFmpeg (only needed if not auto-detected):
winget install Gyan.FFmpeg
```

> **Note on FFmpeg:** MeetMind also auto-detects ffmpeg bundled with common apps (e.g. `C:\Program Files\Softdeluxe\Free Download Manager\ffmpeg.exe`), so a standalone install is often unnecessary.

### ▶️ Run

```powershell
ollama serve                  # terminal 1 — skip if Ollama is already running

.\venv\Scripts\activate       # terminal 2
python manage.py runserver    # → http://127.0.0.1:8000
```

### ⚡ Instant Demo (no upload needed)

```powershell
python scripts\create_demo_data.py
```

Seeds a realistic engineering incident meeting with synthetic slides, OCR text, a timestamped transcript, multi-modal speech ↔ slide correlations, and action items — ready to inspect in seconds.

### 🌐 Optional: Remote Judge Access (ngrok)

```powershell
ngrok http 8000
```

Share the generated public URL with judges — all processing still runs 100% on your laptop GPU.

---

## 📖 How to Use

### 1. Upload a Meeting Video
- Click **"Process Recording"** in the navbar or on the dashboard
- Give your meeting a title
- Upload a meeting recording video file (`.mp4`, `.webm`, `.mkv`, `.avi`)
  - This can be a Zoom recording, Teams recording, Google Meet recording, screen recording, etc.
- Click **"Process"**

### 2. Wait for Processing
MeetMind will automatically:
1. **Extract** the audio track and screen frames from the video (FFmpeg)
2. **Transcribe** the audio into timestamped text (Whisper AI)
3. **Extract text** from screen frames using OCR (EasyOCR)
4. **Generate** a summary that correlates speech with screen content (Phi-3 LLM)
5. **Index** the meeting for future search (ChromaDB)

A progress bar shows the current status. Processing time depends on the video length and your GPU.

### 3. View Results
- **Transcript**: Timestamped, word-level transcription
- **Screen Content**: OCR text extracted from each sampled frame, shown alongside the transcript
- **Summary**: AI-generated overview with:
  - Key discussion points
  - Action items
  - Correlations between speech and screen content
- **Frames**: Thumbnails of extracted screen frames with their timestamps

### 4. Search Past Meetings
- Use the **Search** page to find information across all processed meetings
- Search by meaning (semantic search), not just keywords
- Ask questions like: *"What did we decide about the marketing budget?"*

### 5. Export & Compare
- **Export PDF** — download a styled report (summary, action items, correlations, full transcript) from any completed meeting page
- **Chat Copilot** — ask the meeting questions directly; answers are generated locally via RAG over its transcript + slide text
- **Compare** — select 2–3 completed meetings on the dashboard for a side-by-side view with shared topics and combined action items

---

## 🏗️ Tech Stack

All AI inference runs **100% locally** on your device:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Django 5 | Web framework |
| Video Processing | FFmpeg | Extract audio + frames |
| Speech-to-Text | faster-whisper (Whisper small) | Local transcription on GPU |
| Screen OCR | EasyOCR | Extract text from frames |
| Summarization | Ollama + Phi-3-mini | Local LLM summarization |
| Embeddings | sentence-transformers | Local semantic embeddings |
| Vector Search | ChromaDB | Local vector database |
| Frontend | HTML / CSS / JavaScript | Web UI |

**No cloud AI APIs are used. No data is sent to external servers.**

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ffmpeg not found` | Install FFmpeg and add to PATH, then restart terminal |
| `ollama: connection refused` | Run `ollama serve` in a separate terminal first |
| `CUDA out of memory` | Close other GPU-intensive apps. Models are loaded sequentially to stay under 4GB VRAM |
| Slow transcription | Make sure faster-whisper is using GPU (not CPU). Check CUDA installation |
| `phi3:mini not found` | Run `ollama pull phi3:mini` first |
| Screen frames show no text | EasyOCR models download on first OCR run (~100 MB one-time); check the terminal log |

---

## 📜 Hackathon Disclosure

| Category | Details |
|----------|---------|
| **Models** | OpenAI Whisper (small), Microsoft Phi-3-mini-4k-instruct (Q4_K_M), all-MiniLM-L6-v2, EasyOCR (CRAFT + CRNN) |
| **Frameworks** | Django 5, faster-whisper, Ollama, sentence-transformers, ChromaDB, EasyOCR, reportlab |
| **Tools** | FFmpeg, AI-assisted development (Google Antigravity IDE, Devin) |
| **Cloud Dependencies** | **None** — all AI inference is 100% local |

---

## 📄 License

MIT License — built during the Local AI Hackathon, October 2026.
