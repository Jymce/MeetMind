"""
Local speech-to-text using faster-whisper (runs on GPU).
"""
import logging

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid VRAM usage until needed
_model = None


def _get_model(model_size: str = "small", device: str = "cuda"):
    """Lazy-load the Whisper model with automatic CPU fallback."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        
        actual_device = device
        try:
            import torch
            if device == "cuda" and not torch.cuda.is_available():
                actual_device = "cpu"
        except Exception:
            pass

        logger.info(f"Loading Whisper model: {model_size} on {actual_device}")
        try:
            _model = WhisperModel(
                model_size,
                device=actual_device,
                compute_type="float16" if actual_device == "cuda" else "int8"
            )
        except Exception as e:
            logger.warning(f"Failed to load Whisper on {actual_device} ({e}), falling back to CPU.")
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
            
        logger.info("Whisper model loaded successfully")
    return _model


def unload_model():
    """Unload the model to free VRAM for other models."""
    global _model
    if _model is not None:
        del _model
        _model = None
        # Force CUDA memory cleanup
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        logger.info("Whisper model unloaded, VRAM freed")


def transcribe(audio_path: str, model_size: str = "small", device: str = "cuda") -> list[dict]:
    """
    Transcribe an audio file using local Whisper model.

    Args:
        audio_path: Path to WAV audio file
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium')
        device: 'cuda' for GPU or 'cpu'

    Returns:
        List of segments: [{'start': float, 'end': float, 'text': str}, ...]
    """
    model = _get_model(model_size, device)

    logger.info(f"Transcribing: {audio_path}")
    segments_gen, info = model.transcribe(
        audio_path,
        beam_size=5,
        language=None,  # auto-detect language
        vad_filter=True,  # filter out silence
    )

    logger.info(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")

    segments = []
    for segment in segments_gen:
        segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip(),
        })

    logger.info(f"Transcription complete: {len(segments)} segments")
    return segments
