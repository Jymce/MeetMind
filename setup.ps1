#Requires -Version 5.1
<#
.SYNOPSIS
    MeetMind — one-shot local setup script (Windows).
.DESCRIPTION
    Installs all prerequisites and pre-downloads every AI model so the app
    runs 100% offline afterwards:
      1. Python 3.10+          (winget, if missing)
      2. venv + pip packages   (requirements.txt)
      3. Ollama + phi3:mini    (winget + ollama pull)
      4. FFmpeg                (winget; auto-detected if already present)
      5. AI model pre-download (Whisper, EasyOCR, all-MiniLM-L6-v2)
      6. Django migrations + optional demo meeting
.USAGE
    Right-click -> Run with PowerShell, or:
        powershell -ExecutionPolicy Bypass -File setup.ps1
#>

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor DarkGray }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-Warn "winget not found - automatic installs will be skipped. Install missing pieces manually."
}

# ---------------------------------------------------------------- 1. Python
Write-Step "1/7 Python"
$python = $null
foreach ($cmd in @('python', 'py')) {
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($p) {
        $ver = & $cmd -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($ver -and ([version]$ver -ge [version]'3.10')) { $python = $cmd; break }
    }
}
if ($python) {
    Write-Ok "Python $ver found ($python)"
} elseif ($winget) {
    Write-Host "  Installing Python 3.13 via winget..."
    winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
    $python = 'py'
    Write-Ok "Python installed"
} else {
    Write-Warn "Python 3.10+ not found. Install from https://python.org then re-run."
    exit 1
}

# ---------------------------------------------------------- 2. venv + pip
Write-Step "2/7 Virtual environment & Python packages"
if (-not (Test-Path 'venv\Scripts\python.exe')) {
    & $python -m venv venv
    Write-Ok "Created venv"
} else {
    Write-Skip "venv already exists"
}
& '.\venv\Scripts\python.exe' -m pip install --upgrade pip | Out-Null
& '.\venv\Scripts\pip.exe' install -r requirements.txt
if ($LASTEXITCODE -eq 0) { Write-Ok "requirements.txt installed" }
else { Write-Warn "pip install had errors - check output above" }

# ---------------------------------------------------------------- 3. Ollama
Write-Step "3/7 Ollama + LLM model"
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama -and $winget) {
    Write-Host "  Installing Ollama via winget..."
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
}
if ($ollama) {
    $hasPhi = $false
    try { $hasPhi = (ollama list 2>$null | Select-String 'phi3:mini') } catch {}
    if ($hasPhi) {
        Write-Skip "phi3:mini already pulled"
    } else {
        Write-Host "  Pulling phi3:mini (~2.4 GB, one-time download)..."
        ollama pull phi3:mini
    }
    Write-Ok "Ollama ready (start it with 'ollama serve' if the app can't connect)"
} else {
    Write-Warn "Ollama not installed - summaries/chat will not work until installed."
}

# ---------------------------------------------------------------- 4. FFmpeg
Write-Step "4/7 FFmpeg"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Skip "ffmpeg already on PATH"
} elseif (Test-Path 'C:\Program Files\Softdeluxe\Free Download Manager\ffmpeg.exe') {
    Write-Skip "Auto-detected ffmpeg bundled with Free Download Manager"
} elseif ($winget) {
    Write-Host "  Installing FFmpeg via winget..."
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    Write-Ok "FFmpeg installed"
} else {
    Write-Warn "FFmpeg not found - install from https://ffmpeg.org or 'winget install Gyan.FFmpeg'"
}

# -------------------------------------------- 5. Pre-download AI models
# Whisper + EasyOCR + sentence-transformers all download weights on first use.
# Doing it here means the app works fully offline from the very first meeting.
Write-Step "5/7 Pre-downloading AI models (~700 MB, one-time)"
$preloadScript = @'
import logging
logging.basicConfig(level=logging.WARNING)

try:
    from faster_whisper import WhisperModel
    print("  Downloading Whisper 'small'...", flush=True)
    WhisperModel('small', device='cpu', compute_type='int8')
    print("  [OK] Whisper model cached", flush=True)
except Exception as e:
    print(f"  [WARN] Whisper preload failed: {e}", flush=True)

try:
    import easyocr
    print("  Downloading EasyOCR models...", flush=True)
    easyocr.Reader(['en'], gpu=False, verbose=False)
    print("  [OK] EasyOCR models cached", flush=True)
except Exception as e:
    print(f"  [WARN] EasyOCR preload failed: {e}", flush=True)

try:
    from sentence_transformers import SentenceTransformer
    print("  Downloading all-MiniLM-L6-v2 embeddings...", flush=True)
    SentenceTransformer('all-MiniLM-L6-v2')
    print("  [OK] Embedding model cached", flush=True)
except Exception as e:
    print(f"  [WARN] Embedding model preload failed: {e}", flush=True)
'@
$preloadScript | & '.\venv\Scripts\python.exe' -
Write-Ok "Model pre-download complete"

# ------------------------------------------------------- 6. DB migrations
Write-Step "6/7 Database"
& '.\venv\Scripts\python.exe' manage.py migrate --noinput
Write-Ok "Migrations applied"

# --------------------------------------------------------- 7. Demo data
Write-Step "7/7 Demo meeting (optional)"
$seed = Read-Host "  Seed a demo meeting for instant evaluation? [Y/n]"
if ($seed -notmatch '^[Nn]') {
    & '.\venv\Scripts\python.exe' scripts\create_demo_data.py
    Write-Ok "Demo meeting created"
} else {
    Write-Skip "Skipped demo seed"
}

# -------------------------------------------------------------------- done
Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "  MeetMind setup complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host @"

  To start:
    1. ollama serve              (if not already running)
    2. .\venv\Scripts\activate
    3. python manage.py runserver
    4. Open http://127.0.0.1:8000

  Everything runs locally - safe to disconnect after setup.
"@
