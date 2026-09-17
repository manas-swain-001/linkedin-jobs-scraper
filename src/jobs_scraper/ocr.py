import logging

_engine = None
_engine_error = None
_log = logging.getLogger("jobs_scraper.ocr")


def _get_engine():
    global _engine, _engine_error
    if _engine is not None or _engine_error is not None:
        return _engine
    try:
        from rapidocr import RapidOCR

        _engine = RapidOCR()
        _log.info("Offline OCR engine loaded (RapidOCR).")
    except Exception as exc:  # pragma: no cover - depends on environment
        _engine_error = exc
        _engine = None
        _log.warning("OCR unavailable: %s", exc)
    return _engine


def ocr_image_bytes(img_bytes: bytes) -> str:
    """Return the text OCR-ed from an image. Empty string if OCR is not usable."""
    engine = _get_engine()
    if engine is None or not img_bytes:
        return ""
    try:
        out = engine(img_bytes)
        txts = getattr(out, "txts", None)
        if not txts:
            return ""
        lines = [str(t).strip() for t in txts if str(t).strip()]
        return " ".join(lines)
    except Exception as exc:
        _log.debug("OCR failed for image: %s", exc)
        return ""