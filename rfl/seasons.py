"""Сезоны: определение даты матча с годом и отнесение матча к сезону.

На сайте лиги даты матчей указаны без года («21 сентября 21:00» или «21.09 21:00»).
Год подбирается по правилу: берется последняя такая дата, не позднее завтрашнего дня.
Найденная дата сохраняется в data/our_matches.json и в дальнейшем не пересчитывается.
Для матчей, которые правило определяет неверно или которые не имеют даты,
даты задаются вручную в data/match_dates.csv.
"""
import csv
import datetime as dt
import re

from .timeutil import TZ

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]

DEFAULT_SEASONS = [
    {"key": "2026", "title": "Сезон 2026", "start": "2026-01-01", "end": "2026-10-15"},
    {"key": "2026-2027", "title": "Сезон 2026-2027", "start": "2026-10-16", "end": "2027-03-31"},
    {"key": "2027", "title": "Сезон 2027", "start": "2027-04-01", "end": "2027-12-31"},
]


def _day_month_time(text):
    """(месяц, день, часы, минуты) из «21 сентября 21:00» или «21.09 21:00»; часы и минуты могут быть None."""
    t = (text or "").lower()
    m = re.search(r"(\d{1,2})\s+([а-я]+)(?:\s+(\d{1,2}):(\d{2}))?", t)
    if m and m[2] in MONTHS:
        month, day, hh, mm = MONTHS.index(m[2]) + 1, int(m[1]), m[3], m[4]
    else:
        m = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?(?:\s+(\d{1,2}):(\d{2}))?", t)
        if not m:
            return None
        month, day, hh, mm = int(m[2]), int(m[1]), m[3], m[4]
    return month, day, int(hh) if hh else None, int(mm) if mm else None


def resolve_date(text, now):
    """Дата матча с годом (datetime с часовым поясом команды) или None, если дату определить нельзя."""
    parsed = _day_month_time(text)
    if not parsed:
        return None
    month, day, hh, mm = parsed
    limit = now + dt.timedelta(days=1)
    for year in (now.year, now.year - 1, now.year - 2):
        try:
            d = dt.datetime(year, month, day, hh or 0, mm or 0, tzinfo=TZ)
        except ValueError:
            continue
        if d <= limit:
            return d
    return None


def load_match_dates(path):
    """data/match_dates.csv: match_id, date (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД, можно со временем ЧЧ:ММ)."""
    result = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = (row.get("match_id") or "").strip()
            raw = (row.get("date") or "").strip()
            if not mid.isdigit() or not raw:
                continue
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?$", raw) or None
            if m:
                y, mo, d, hh, mm = m.groups()
            else:
                m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2}))?$", raw)
                if not m:
                    continue
                d, mo, y, hh, mm = m.groups()
            try:
                result[int(mid)] = dt.datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), tzinfo=TZ)
            except ValueError:
                continue
    return result


def seasons_from_cfg(cfg):
    """Список сезонов из config.yaml (раздел seasons) или значения по умолчанию."""
    raw = cfg.get("seasons") or DEFAULT_SEASONS
    out = []
    for s in raw:
        out.append({"key": str(s["key"]), "title": s.get("title") or f"Сезон {s['key']}",
                    "start": dt.date.fromisoformat(str(s["start"])),
                    "end": dt.date.fromisoformat(str(s["end"]))})
    return out


def season_of(played, seasons):
    """Ключ сезона для datetime (или ISO-строки); None, если дата вне всех сезонов."""
    if not played:
        return None
    if isinstance(played, str):
        played = dt.datetime.fromisoformat(played)
    day = played.date()
    for s in seasons:
        if s["start"] <= day <= s["end"]:
            return s["key"]
    return None
