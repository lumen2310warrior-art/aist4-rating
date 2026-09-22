"""Разбор страниц rfll.ru: календаря турнира и протокола матча."""
import re
from bs4 import BeautifulSoup

POSITIONS = {"Вратарь", "Защитник", "Нападающий", "Полузащитник", "Универсал"}
STAT_COLS = {"Г": "goals", "П": "assists", "ОП": "op", "ЖК": "yellow", "КК": "red"}
SCORE_RE = re.compile(r"^(.*?)\s+(\d+|-)\s*:\s*(\d+|-)\s+(.*)$")
NOISE = ("Логотип команды", "Аватарка игрока", "Фото игрока")


def clean(text):
    for n in NOISE:
        text = text.replace(n, " ")
    return re.sub(r"\s+", " ", text).strip()


def norm_team(name):
    """Нормализация названия команды для сравнения."""
    return re.sub(r"[\s\"'«»]", "", (name or "").lower().replace("ё", "е"))


def split_score(text):
    """'Солнышко 10:6 Аист-4' -> ('Солнышко', 10, 6, 'Аист-4'). Несыгранный матч дает None в счете."""
    m = SCORE_RE.match(clean(text))
    if not m:
        return None
    home, hs, aws, away = m.groups()
    to_int = lambda x: None if x == "-" else int(x)
    return home.strip(), to_int(hs), to_int(aws), away.strip()


def parse_calendar(html):
    """Список матчей из календаря: номер, команды, счет, дата."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"/match/(\d+)", a["href"])
        if not m:
            continue
        mid = int(m.group(1))
        if mid in found:
            continue
        parsed = split_score(a.get_text(" "))
        if not parsed:
            continue
        home, hs, aws, away = parsed
        date = ""
        tr = a.find_parent("tr")
        if tr:
            first = tr.find("td")
            if first is not None and first is not a.find_parent("td"):
                date = clean(first.get_text(" "))
        found[mid] = {"match_id": mid, "home": home, "away": away,
                      "home_goals": hs, "away_goals": aws, "date": date}
    return list(found.values())


def _player_cell(cell):
    link = cell.find("a", href=re.compile(r"/player/\d+"))
    if not link:
        return None
    pid = int(re.search(r"/player/(\d+)", link["href"]).group(1))
    lines = [clean(x) for x in cell.get_text("\n").split("\n")]
    lines = [x for x in lines if x]
    position = next((x for x in lines if x in POSITIONS), "")
    name = next((x for x in lines if x not in POSITIONS), "")
    if not name:  # имя может быть только в alt картинки
        img = cell.find("img", alt=True)
        if img:
            alt = clean(img["alt"])
            name = next((x for x in [alt] if x and x not in POSITIONS), "")
    return pid, name, position


def parse_match(html, match_id):
    """Протокол матча: счет и составы с личной статистикой."""
    soup = BeautifulSoup(html, "html.parser")
    home = away = None
    hs = aws = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        parsed = split_score(h.get_text(" "))
        if parsed:
            home, hs, aws, away = parsed
            break

    lineups = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [clean(c.get_text(" ")) for c in rows[0].find_all(["th", "td"])]
        if not headers or "Игрок" not in headers[0] or "Г" not in headers:
            continue
        idx = {STAT_COLS[h]: i for i, h in enumerate(headers) if h in STAT_COLS}
        players = []
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            info = _player_cell(cells[0])
            if not info:
                continue
            pid, name, position = info
            stats = {}
            for key in STAT_COLS.values():
                i = idx.get(key)
                txt = clean(cells[i].get_text(" ")) if i is not None and i < len(cells) else ""
                stats[key] = int(txt) if txt.isdigit() else 0
            players.append({"player_id": pid, "name": name, "position": position, **stats})
        lineups.append(players)

    team_ids = {}
    for a in soup.find_all("a", href=re.compile(r"/team/\d+")):
        tid = int(re.search(r"/team/(\d+)", a["href"]).group(1))
        text = norm_team(clean(a.get_text(" ")))
        for side, name in (("home", home), ("away", away)):
            if name and side not in team_ids and norm_team(name) and norm_team(name) in text:
                team_ids[side] = tid
    dm = re.search(r"\b(\d{2}\.\d{2})\s+(\d{2}:\d{2})\b", clean(soup.get_text(" ")))
    date = f"{dm.group(1)} {dm.group(2)}" if dm else ""

    if home is None or len(lineups) < 2:
        raise ValueError(f"Протокол матча {match_id} не распознан: "
                         f"заголовок={'да' if home else 'нет'}, таблиц составов={len(lineups)}")
    return {"match_id": match_id, "home": home, "away": away,
            "home_goals": hs, "away_goals": aws, "date": date,
            "home_id": team_ids.get("home"), "away_id": team_ids.get("away"),
            "lineups": {"home": lineups[0], "away": lineups[1]}}


def selected_tournament(soup):
    """Название турнира, выбранного на странице команды (Чемпионат-2026, Кубки РФЛ и Лиг 2026)."""
    for opt in soup.find_all("option"):
        if opt.has_attr("selected"):
            text = clean(opt.get_text(" "))
            if re.search(r"Чемпионат|Кубок|Кубки", text):
                return text
    # выпадающий список может быть сделан не на <select>: ищем отмеченный пункт
    for el in soup.select('[class*="active"], [class*="selected"], [aria-selected="true"]'):
        text = clean(el.get_text(" "))
        if re.fullmatch(r".{0,40}(Чемпионат|Кубок|Кубки).{0,40}", text):
            return text
    # запасной вариант: ссылка «Текущее положение команды»
    for a in soup.find_all("a", href=re.compile(r"/tournament/\d+\?round_id=")):
        text = clean(a.get_text(" "))
        if re.search(r"Чемпионат|Кубок|Кубки", text):
            return text
    return ""


def parse_team_calendar(html):
    """Страница /team/ID/calendar: выбранный турнир и матчи команды в нем."""
    soup = BeautifulSoup(html, "html.parser")
    return selected_tournament(soup), parse_calendar(html)
