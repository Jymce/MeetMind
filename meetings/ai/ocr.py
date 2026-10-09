"""
Local OCR using PaddleOCR to extract text from screen frames.
Falls back to a simple approach if PaddleOCR isn't available.
"""
import logging
import os

logger = logging.getLogger(__name__)

_ocr_engine = None


def _get_ocr():
    """Lazy-load an OCR engine: PaddleOCR -> EasyOCR -> Tesseract."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_engine = ('paddle', PaddleOCR(
                use_angle_cls=True,
                lang='en',
                show_log=False,
                use_gpu=False,  # OCR runs on CPU to save GPU VRAM for Whisper/LLM
            ))
            logger.info("PaddleOCR engine loaded (CPU)")
        except ImportError:
            try:
                import easyocr
                _ocr_engine = ('easyocr', easyocr.Reader(['en'], gpu=False, verbose=False))
                logger.info("EasyOCR engine loaded (CPU)")
            except ImportError:
                logger.warning("EasyOCR not available either, trying pytesseract...")
                try:
                    import pytesseract
                    _ocr_engine = ('tesseract', pytesseract)
                    logger.info("Using Tesseract OCR as fallback")
                except ImportError:
                    logger.error("No OCR engine available! Install easyocr, paddleocr or pytesseract.")
                    _ocr_engine = ('none', None)
    return _ocr_engine


def extract_text_from_frame(frame_path: str) -> str:
    """
    Extract text from a single frame image using OCR.

    Args:
        frame_path: Path to the frame image file

    Returns:
        Extracted text as a string
    """
    if not os.path.exists(frame_path):
        logger.warning(f"Frame not found: {frame_path}")
        return ""

    engine_name, engine = _get_ocr()

    if engine_name == 'none':
        return ""

    if engine_name == 'tesseract':
        from PIL import Image
        try:
            return engine.image_to_string(Image.open(frame_path)).strip()
        except Exception as e:
            logger.error(f"Tesseract OCR failed on {frame_path}: {e}")
            return ""

    if engine_name == 'easyocr':
        try:
            results = engine.readtext(frame_path)
            return '\n'.join(r[1] for r in results if len(r) >= 2)
        except Exception as e:
            logger.error(f"EasyOCR failed on {frame_path}: {e}")
            return ""

    # PaddleOCR
    try:
        result = engine.ocr(frame_path, cls=True)
        if result and result[0]:
            lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0]  # text content
                    lines.append(text)
            return '\n'.join(lines)
        return ""
    except Exception as e:
        logger.error(f"PaddleOCR failed on {frame_path}: {e}")
        return ""


def process_frames(frames: list[dict]) -> list[dict]:
    """
    Run OCR on all extracted frames.

    Args:
        frames: List of dicts with 'path' and 'timestamp' keys

    Returns:
        Same list with 'ocr_text' added to each dict
    """
    logger.info(f"Running OCR on {len(frames)} frames...")

    for i, frame in enumerate(frames):
        frame['ocr_text'] = extract_text_from_frame(frame['path'])
        if frame['ocr_text']:
            logger.debug(f"Frame {i} ({frame['timestamp']}s): {len(frame['ocr_text'])} chars extracted")
        else:
            logger.debug(f"Frame {i} ({frame['timestamp']}s): no text found")

    frames_with_text = sum(1 for f in frames if f['ocr_text'])
    logger.info(f"OCR complete: {frames_with_text}/{len(frames)} frames had text")

    return frames
