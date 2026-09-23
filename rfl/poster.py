"""Распознавание афиши расписания РФЛ.

Афиша устроена как набор таблиц: [день] [команда на белом] [время на темном] [команда на белом] [поле].
Белые ячейки находятся по цвету, время читается между ними, день слева, поле справа.
Дата матча = день недели (или число, как в «ВТ22») внутри диапазона из заголовка «25 - 28 СЕНТЯБРЯ 2026».
"""
import datetime as dt
import difflib
import re

import cv2
import numpy as np
import pytesseract

MONTHS = {"ЯНВАРЯ": 1, "ФЕВРАЛЯ": 2, "МАРТА": 3, "АПРЕЛЯ": 4, "МАЯ": 5, "ИЮНЯ": 6, "ИЮЛЯ": 7,
          "АВГУСТА": 8, "СЕНТЯБРЯ": 9, "ОКТЯБРЯ": 10, "НОЯБРЯ": 11, "ДЕКАБРЯ": 12}
WEEKDAYS = {"ПН": 0, "ВТ": 1, "СР": 2, "ЧТ": 3, "ПТ": 4, "СБ": 5, "ВС": 6}
LOOKALIKE = str.maketrans("ABCEHKMOPTXYЁ", "АВСЕНКМОРТХУЕ")


def norm(text):
    """Приведение к сравнимому виду: заглавные, латиница-двойник в кириллицу, только буквы и цифры."""
    t = (text or "").upper().replace("Ё", "Е").translate(LOOKALIKE)
    return re.sub(r"[^0-9А-ЯA-Z]", "", t)


def same_team(ocr_text, alias):
    a, b = norm(ocr_text), norm(alias)
    if not a or not b:
        return False
    if re.sub(r"\D", "", a) != re.sub(r"\D", "", b):  # номер команды должен совпасть точно
        return False
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def snap_venue(text):
    """Код поля: М1, М2, О1, О2, А1-А4, С1, С2, ЗВ (с поправкой на типичные ошибки распознавания)."""
    t = (text or "").upper().translate(LOOKALIKE)
    t = t.translate(str.maketrans({"L": "1", "I": "1", "|": "1", "l": "1", "Z": "2", "G": "4", "Ч": "4"}))
    t = re.sub(r"[^МОАСЗВ0-9]", "", t)
    if t.startswith("З"):
        return "ЗВ"
    m = re.match(r"([МОАС])([1-4])", t)
    return f"{m[1]}{m[2]}" if m else ""


def _ocr(img, lang, psm=7, whitelist=None, invert=False):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if invert:
        g = 255 - g
    g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cfg = f"--psm {psm}"
    if whitelist:
        cfg += f" -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(b, lang=lang, config=cfg).strip()


def _white_cells(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    H, W = img.shape[:2]
    return [tuple(int(v) for v in s[:4]) for s in stats[1:]
            if s[2] > 0.05 * W and 0.012 * H < s[3] < 0.045 * H]


def parse_range(text):
    """«25 - 28 СЕНТЯБРЯ 2026» -> (date(2026,9,25), date(2026,9,28))."""
    t = text.upper().replace("Ё", "Е")
    m = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([А-Я]+)\s+(\d{4})", t)
    if m:
        d1, d2, mon, year = int(m[1]), int(m[2]), MONTHS.get(m[3]), int(m[4])
        if mon:
            start_mon = mon if d1 <= d2 else (mon - 2) % 12 + 1
            start_year = year if start_mon <= mon else year - 1
            return dt.date(start_year, start_mon, d1), dt.date(year, mon, d2)
    m = re.search(r"(\d{1,2})\s+([А-Я]+)\s+(\d{4})", t)
    if m and MONTHS.get(m[2]):
        d = dt.date(int(m[3]), MONTHS[m[2]], int(m[1]))
        return d, d
    return None


def resolve_date(day_text, rng):
    """День недели (и, возможно, число) -> дата внутри диапазона афиши."""
    if not rng:
        return None
    t = norm(day_text)
    wd = next((WEEKDAYS[k] for k in WEEKDAYS if t.startswith(k)), None)
    num = re.search(r"(\d{1,2})", t)
    start, end = rng
    if num:
        day = int(num.group(1))
        for base in (start, end):
            try:
                cand = base.replace(day=day)
            except ValueError:
                continue
            if wd is None or cand.weekday() == wd:
                return cand
    if wd is not None:
        d = start
        while d <= end:
            if d.weekday() == wd:
                return d
            d += dt.timedelta(days=1)
    return None


def read_poster(image_bytes, lang="rus+eng"):
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"range": None, "rows": []}
    H, W = img.shape[:2]
    header = _ocr(img[: int(0.14 * H), int(0.55 * W):], lang, psm=6, invert=True)
    rng = parse_range(header)

    cells = sorted(_white_cells(img), key=lambda c: (c[1], c[0]))
    rows, used = [], set()
    for i, a in enumerate(cells):
        if i in used:
            continue
        ax, ay, aw, ah = a
        for j, b in enumerate(cells):
            if j == i or j in used:
                continue
            bx, by, bw, bh = b
            gap = bx - (ax + aw)
            if abs(by - ay) < 0.4 * ah and 0.01 * W < gap < 0.08 * W:
                used.update({i, j})
                pad = 3
                time_txt = _ocr(img[ay + pad: ay + ah - pad, ax + aw + pad: bx - pad], "eng",
                                whitelist="0123456789:", invert=True)
                dw = int(0.025 * W)
                day_txt = _ocr(img[ay + pad: ay + ah - pad, max(0, ax - dw): ax - 2], lang, invert=True)
                venue_txt = _ocr(img[by + pad: by + bh - pad, bx + bw + 2: min(W, bx + bw + dw)],
                                 lang, invert=True)
                home = _ocr(img[ay + pad: ay + ah - pad, ax + pad: ax + aw - pad], lang)
                away = _ocr(img[by + pad: by + bh - pad, bx + pad: bx + bw - pad], lang)
                tm = re.search(r"(\d{1,2}):?(\d{2})", time_txt)
                rows.append({
                    "home": home, "away": away, "day": day_txt,
                    "time": f"{int(tm[1]):02d}:{tm[2]}" if tm else "",
                    "venue": snap_venue(venue_txt),
                    "date": resolve_date(day_txt, rng),
                })
                break
    return {"range": rng, "rows": rows}


def find_team_matches(poster, aliases):
    """Строки афиши с участием команды (по любому из вариантов названия)."""
    found = []
    for r in poster["rows"]:
        for side, other in (("home", "away"), ("away", "home")):
            if any(same_team(r[side], a) for a in aliases):
                found.append({**r, "opponent": r[other].strip()})
                break
    return found
