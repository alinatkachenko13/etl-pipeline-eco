"""
отдельный модуль с правилами, который проверяет, насколько качественно извлёкся текст со страницы pdf,
чтобы можно было легко менять пороги и условия, не трогая основной код парсинга
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


# кириллические и латинские буквы для простых проверок
_CYR_RE = re.compile(r"[\u0400-\u04FF]")
_LAT_RE = re.compile(r"[A-Za-z]")


@dataclass
class PageTextQuality:
    """простая детерминированная оценка качества текста одной страницы."""

    score: float
    char_len: int
    letter_ratio: float
    alnum_ratio: float
    cyrillic_ratio: float  # доля кириллических букв среди всех букв
    latin_ratio: float  # доля латинских букв среди всех букв
    digit_ratio: float
    suspicious_repeat: bool
    reasons: list[str] = field(default_factory=list)


def postprocess_ocr_text(text: str) -> str:
    """
    мягкая чистка текста после ocr без агрессивных правок.
    """
    if not text:
        return ""
    t = text.replace("\r", "\n")
    # нормализация unicode без удаления полезного текста
    t = unicodedata.normalize("NFKC", t)
    # сжимаем пробелы и табы, переносы строк оставляем
    lines_out: list[str] = []
    for line in t.split("\n"):
        s = re.sub(r"[ \t]+", " ", line).strip()
        if s:
            lines_out.append(s)
    t = "\n".join(lines_out)
    t = re.sub(r"\n{3,}", "\n\n", t)
    # убираем строки из повторяющегося "шума"
    cleaned_lines: list[str] = []
    for line in t.split("\n"):
        core = re.sub(r"[\s\W_]+", "", line, flags=re.UNICODE)
        if not core:
            continue
        if len(set(core)) == 1 and len(core) >= 6:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _longest_char_run(s: str) -> int:
    if not s:
        return 0
    best = cur = 1
    prev = s[0]
    for c in s[1:]:
        if c == prev:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
            prev = c
    return best


def evaluate_page_text_quality(text: str) -> PageTextQuality:
    """
    возвращает оценку качества 0..1 и простые диагностические флаги.
    """
    reasons: list[str] = []
    raw = (text or "").strip()
    if not raw:
        return PageTextQuality(
            score=0.0,
            char_len=0,
            letter_ratio=0.0,
            alnum_ratio=0.0,
            cyrillic_ratio=0.0,
            latin_ratio=0.0,
            digit_ratio=0.0,
            suspicious_repeat=False,
            reasons=["empty"],
        )

    n = len(raw)
    letters = sum(1 for c in raw if c.isalpha())
    digits = sum(1 for c in raw if c.isdigit())
    alnum = sum(1 for c in raw if c.isalnum())
    space = sum(1 for c in raw if c.isspace())
    non_space = n - space
    if non_space <= 0:
        return PageTextQuality(
            score=0.0,
            char_len=n,
            letter_ratio=0.0,
            alnum_ratio=0.0,
            cyrillic_ratio=0.0,
            latin_ratio=0.0,
            digit_ratio=0.0,
            suspicious_repeat=False,
            reasons=["only_whitespace"],
        )

    cyr = len(_CYR_RE.findall(raw))
    lat = len(_LAT_RE.findall(raw))
    letter_ratio = letters / non_space
    alnum_ratio = alnum / non_space
    digit_ratio = digits / non_space
    cyrillic_ratio = (cyr / letters) if letters else 0.0
    latin_ratio = (lat / letters) if letters else 0.0

    # подсчёт служебного/битого шума
    bad_ctrl = sum(1 for c in raw if ord(c) < 32 and c not in "\n\t\r")
    bad_ratio = bad_ctrl / max(n, 1)

    run = _longest_char_run(re.sub(r"\s+", "", raw))
    suspicious_repeat = False
    if run >= 12:
        suspicious_repeat = True
        reasons.append(f"long_char_run={run}")
    # похоже на "залипшие" символы/артефакты
    if re.search(r"(.)\1{15,}", raw):
        suspicious_repeat = True
        reasons.append("repeated_glyph")

    if bad_ratio > 0.02:
        reasons.append(f"control_noise_ratio={bad_ratio:.3f}")

    # короткие страницы могут быть нормальными, если текст плотный
    len_score = min(1.0, non_space / 300.0)

    # плотность букв: у плохого ocr часто много знаков и цифр
    letter_score = min(1.0, letter_ratio / 0.55) if letter_ratio > 0 else 0.0

    # для домена ожидаем заметную долю букв (кириллица/латиница)
    if letters >= 8 and (cyrillic_ratio + latin_ratio) < 0.85:
        reasons.append("mixed_script_noise")

    script_balance = min(1.0, max(cyrillic_ratio, latin_ratio) + 0.25 * min(cyrillic_ratio, latin_ratio))

    junk_penalty = min(0.45, bad_ratio * 5.0 + (0.25 if suspicious_repeat else 0.0))

    score = (
        0.22 * len_score
        + 0.38 * letter_score
        + 0.22 * min(1.0, alnum_ratio / 0.65)
        + 0.18 * script_balance
        - junk_penalty
    )
    score = max(0.0, min(1.0, score))

    # жёсткие правила для явного мусора
    if letter_ratio < 0.18 and non_space > 80:
        score = min(score, 0.28)
        reasons.append("low_letters_long_page")
    if alnum_ratio < 0.12 and non_space > 120:
        score = min(score, 0.25)
        reasons.append("low_alnum_long_page")

    return PageTextQuality(
        score=score,
        char_len=n,
        letter_ratio=letter_ratio,
        alnum_ratio=alnum_ratio,
        cyrillic_ratio=cyrillic_ratio,
        latin_ratio=latin_ratio,
        digit_ratio=digit_ratio,
        suspicious_repeat=suspicious_repeat,
        reasons=reasons,
    )


def page_has_embedded_images(page) -> bool:
    """на странице есть встроенный растр (типичный скан), не только векторный фон."""
    try:
        return len(page.get_images(full=True)) > 0
    except Exception:
        return len(page.get_images()) > 0


def should_attempt_ocr(
    native_raw: str,
    page_has_images: bool,
) -> tuple[bool, str]:
    """
    нужен ли ocr на странице pdf.
    без эвристики «мало символов = скан»: пустые и короткие страницы без растра не ocr.
    ocr только если есть встроенные изображения и нет извлекаемого текстового слоя.
    """
    stripped = (native_raw or "").strip()
    if not page_has_images:
        return False, "no_raster"
    if not stripped:
        return True, "raster_without_text_layer"
    return False, "native_text_present"


def jaccard_word_similarity(a: str, b: str) -> float:
    """простое пересечение слов в диапазоне [0, 1]."""
    wa = {w for w in re.findall(r"\w+", (a or "").lower(), flags=re.UNICODE) if len(w) > 1}
    wb = {w for w in re.findall(r"\w+", (b or "").lower(), flags=re.UNICODE) if len(w) > 1}
    if not wa and not wb:
        return 1.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def try_complementary_merge(native: str, ocr: str) -> tuple[str | None, str | None]:
    """
    если ocr добавляет полезные строки, которых нет в native, делаем аккуратное объединение.
    возвращает (merged_text, None) при успехе, иначе (None, reason).
    """
    n = (native or "").strip()
    o = (ocr or "").strip()
    if not n:
        return None, "no_native"
    if not o:
        return None, "no_ocr"

    jac = jaccard_word_similarity(n, o)
    if jac > 0.82:
        return None, "high_overlap"

    extra: list[str] = []
    for line in o.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s in n:
            continue
        # не добавляем слишком короткие шумные куски
        if len(s) < 4:
            continue
        extra.append(line.strip())

    if not extra:
        return None, "no_extra_lines"

    merged = n.rstrip() + "\n\n" + "\n".join(extra)
    # защита от слишком раздутого текста из-за некачественного ocr
    if len(merged) > max(len(n), len(o)) * 1.6 + 80:
        return None, "merge_too_long"

    return merged, None
