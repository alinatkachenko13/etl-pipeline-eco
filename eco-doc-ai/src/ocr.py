from paddleocr import PaddleOCR

_ocr = None
_ocr_init_error: Exception | None = None


def get_ocr():
    global _ocr, _ocr_init_error
    if _ocr_init_error is not None:
        raise _ocr_init_error
    if _ocr is None:
        try:
            _ocr = PaddleOCR(use_angle_cls=True, lang="ru")
        except Exception as e:
            _ocr_init_error = e
            raise
    return _ocr


def run_ocr_on_image(ocr, image_path: str):
    """
    совместимый вызов ocr: старые версии принимают cls=, новые — нет.
    """
    try:
        return ocr.ocr(image_path, cls=True)
    except TypeError:
        return ocr.ocr(image_path)
