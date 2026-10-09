"""
FFmpeg-based extractor: splits a meeting video into audio track + screen frames.
Auto-locates ffmpeg on Windows system.
"""
import os
import re
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> str:
    """Finds ffmpeg executable from PATH or common installed locations."""
    # 1. Check system PATH
    ffmpeg_on_path = shutil.which('ffmpeg')
    if ffmpeg_on_path:
        return ffmpeg_on_path

    # 2. Check known Windows software paths
    known_paths = [
        r"C:\Program Files\Softdeluxe\Free Download Manager\ffmpeg.exe",
        r"C:\Program Files\BlueStacks_nxt\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]
    for path in known_paths:
        if os.path.exists(path):
            logger.info(f"Using discovered FFmpeg at: {path}")
            return path

    return 'ffmpeg'


def get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using ffmpeg output.
    Does not require ffprobe.
    """
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [ffmpeg_bin, '-i', video_path]
    try:
        # ffmpeg outputs file info to stderr
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', result.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return duration
    except Exception as e:
        logger.error(f"Error parsing duration with ffmpeg: {e}")

    return 0.0


def extract_audio(video_path: str, output_path: str) -> str:
    """
    Extract audio track from video as WAV (16kHz mono — optimal for Whisper).
    """
    ffmpeg_bin = get_ffmpeg_path()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        ffmpeg_bin, '-i', video_path,
        '-vn',                    # no video
        '-acodec', 'pcm_s16le',   # 16-bit PCM
        '-ar', '16000',           # 16kHz sample rate (Whisper optimal)
        '-ac', '1',               # mono
        '-y',                     # overwrite output
        output_path
    ]

    logger.info(f"Extracting audio using {ffmpeg_bin} from {video_path}")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract audio: {e.stderr}")


def extract_frames(video_path: str, output_dir: str, interval: int = 5) -> list[dict]:
    """
    Extract frames from video at regular intervals (every N seconds).
    """
    ffmpeg_bin = get_ffmpeg_path()
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        ffmpeg_bin, '-i', video_path,
        '-vf', f'fps=1/{interval}',  # one frame per N seconds
        '-q:v', '2',                  # high quality JPEG
        '-y',
        os.path.join(output_dir, 'frame_%04d.jpg')
    ]

    logger.info(f"Extracting frames using {ffmpeg_bin} every {interval}s")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg frame extraction failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract frames: {e.stderr}")

    frames = []
    frame_files = sorted([
        f for f in os.listdir(output_dir)
        if f.startswith('frame_') and f.endswith('.jpg')
    ])

    for i, filename in enumerate(frame_files):
        frames.append({
            'path': os.path.join(output_dir, filename),
            'timestamp': i * interval,
        })

    logger.info(f"Extracted {len(frames)} frames")
    return frames


def mark_duplicate_frames(frames: list[dict], threshold: int = 8) -> list[dict]:
    """
    Flag near-identical frames using average-hash (aHash) Hamming distance.
    Compares each frame against the last unique frame — duplicates keep the
    original timestamp but are flagged so OCR/summarization can skip them.
    """
    from PIL import Image

    prev_hash = None
    for frame in frames:
        try:
            img = Image.open(frame['path']).convert('L').resize((16, 16), Image.LANCZOS)
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            h = 0
            for p in pixels:
                h = (h << 1) | (p > avg)
            frame['is_duplicate'] = (
                prev_hash is not None and bin(h ^ prev_hash).count('1') <= threshold
            )
            if not frame['is_duplicate']:
                prev_hash = h
        except Exception as e:
            logger.warning(f"Frame dedup check failed for {frame['path']}: {e}")
            frame['is_duplicate'] = False

    dupes = sum(1 for f in frames if f['is_duplicate'])
    logger.info(f"Frame dedup: {dupes}/{len(frames)} near-identical frames flagged")
    return frames
