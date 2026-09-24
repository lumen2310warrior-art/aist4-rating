"""Бот команды: расписание по афише лиги, сводка матча, выбор лучшего игрока, месячный рейтинг.

Запускается раз в час. Все, что бот «помнит» между запусками, хранится в data/bot_state.json.
Сообщество (ключ group) пишет в беседу и в личные сообщения капитану и помощникам.
Сервисный ключ собственного приложения (ключ service) нужен только для чтения афиш на стене лиги.
"""
import csv
import datetime as dt
import json
import pathlib
import re

import requests

from .parser import norm_team
from .scoring import score_players
from .timeutil import TZ, now_local
from .vk import VK, VKError

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "bot_state.json"
MVP_CSV = ROOT / "data" / "mvp.csv"
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
              "сентября", "октября", "ноября", "декабря"]
MONTHS_NOM = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
              "сентябрь", "октябрь", "ноябрь", "декабрь"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


# ---------- время и даты ----------

def iso(d):
    return d.isoformat()


def from_iso(s):
    return dt.datetime.fromisoformat(s) if s else None


def ts(d):
    return int(d.timestamp())


def human(d):
    return f"{WEEKDAYS[d.weekday()]} {d:%d.%m} в {d:%H:%M}"


def parse_site_date(text, now):
    """«26 сентября 19:40» или «26.09 19:40» -> datetime (год подбирается ближайший)."""
    t = (text or "").lower()
    m = re.search(r"(\d{1,2})\s+([а-я]+)\s+(\d{1,2}):(\d{2})", t)
    if m and m[2] in MONTHS_GEN:
        month = MONTHS_GEN.index(m[2]) + 1
    else:
        m = re.search(r"(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})", t)
        if not m:
            return None
        month = int(m[2])
    best = None
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            d = dt.datetime(year, month, int(m[1]), int(m[3]), int(m[4]), tzinfo=TZ)
        except ValueError:
            continue
        if best is None or abs((d - now).days) < abs((best - now).days):
            best = d
    return best


def surname(name):
    return (name or "").split(" ")[0]


# ---------- состояние ----------

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"seen_posts": [], "games": {}, "questions": [], "user_ids": {},
            "dm_last": {}, "unmatched_notified": [], "monthly_sent": "", "alerts": {}}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


class Bot:
    def __init__(self, cfg, group_token, service_token, dry_run=False, rating=None):
        self.cfg = cfg
        self.b = cfg["bot"]
        self.v = cfg["vk"]
        self.group = VK(group_token, "сообщество", dry_run)
        self.service = VK(service_token, "приложение", dry_run)
        self.dry = dry_run
        self.rating = rating          # модуль main: update(), web_getter()
        self.state = load_state()
        self.now = now_local()
        self.log = []
        self.rebuild = False

    def say(self, text):
        print(text)
        self.log.append(text)

    # ---------- люди ----------

    def resolve_people(self):
        names = [self.v["captain"]] + list(self.v["assistants"])
        missing = [n for n in names if n not in self.state["user_ids"]]
        if missing:
            users = self.group.call("users.get", user_ids=",".join(missing))
            for n, u in zip(missing, users):
                self.state["user_ids"][n] = u["id"]
        ids = self.state["user_ids"]
        self.captain = ids[self.v["captain"]]
        self.assistants = [ids[a] for a in self.v["assistants"]]

    # ---------- вопросы в личных сообщениях ----------

    def ask(self, to, kind, game_key, text, options=None):
        q = {"id": f"{kind}:{game_key}:{to}", "to": to, "kind": kind, "game": game_key,
             "text": text, "options": options or [], "asked": iso(self.now),
             "status": "queued"}
        if any(x["id"] == q["id"] and x["status"] in ("queued", "sent") for x in self.state["questions"]):
            return
        self.state["questions"].append(q)
        self.flush_queue(to)

    def flush_queue(self, to):
        """Каждому человеку отправляется только один вопрос за раз, остальные ждут очереди."""
        qs = [q for q in self.state["questions"] if q["to"] == to]
        if any(q["status"] == "sent" for q in qs):
            return
        nxt = next((q for q in qs if q["status"] == "queued"), None)
        if nxt:
            try:
                self.group.send(to, nxt["text"])
                nxt["status"] = "sent"
                nxt["sent"] = iso(self.now)
            except VKError as e:
                self.say(f"Не удалось написать пользователю {to}: {e}. "
                         "Он должен один раз написать сообществу в личные сообщения.")

    def close_questions(self, game_key, kind_prefix):
        for q in self.state["questions"]:
            if q["game"] == game_key and q["kind"].startswith(kind_prefix) and q["status"] in ("queued", "sent"):
                q["status"] = "closed"
                self.flush_queue(q["to"])

    def read_answers(self):
        people = {q["to"] for q in self.state["questions"] if q["status"] == "sent"}
        for uid in people:
            try:
                hist = self.group.call("messages.getHistory", peer_id=uid, count=20)
            except VKError as e:
                self.say(f"Не прочитаны ответы пользователя {uid}: {e}")
                continue
            last = self.state["dm_last"].get(str(uid), 0)
            incoming = sorted((m for m in hist["items"] if m["from_id"] == uid and m["id"] > last),
                              key=lambda m: m["id"])
            for m in incoming:
                self.state["dm_last"][str(uid)] = m["id"]
                q = next((q for q in self.state["questions"] if q["to"] == uid and q["status"] == "sent"), None)
                # учитываются только сообщения, написанные после вопроса
                if q and m["date"] >= ts(from_iso(q.get("sent") or q["asked"])):
                    self.handle_answer(q, m["text"].strip())

    def handle_answer(self, q, text):
        game = self.state["games"].get(q["game"])
        if not game:
            q["status"] = "closed"
            return
        if q["kind"] == "confirm":
            if re.fullmatch(r"(1|да|верно|ок)\.?", text.lower()):
                q["status"] = "answered"
                self.confirm_game(q["game"], by=q["to"])
            elif re.fullmatch(r"(2|нет|неверно)\.?", text.lower()):
                q["status"] = "answered"
                self.close_questions(q["game"], "confirm")
                self.ask(q["to"], "datetime", q["game"],
                         f"Пришлите правильные дату и время матча с командой «{game['opponent']}» "
                         "в формате 26.09 19:40")
            else:
                self.group.send(q["to"], "Не понял ответ. Пришлите 1 (верно) или 2 (неверно).")
            self.flush_queue(q["to"])
            return
        if q["kind"] == "datetime":
            m = re.search(r"(\d{1,2})\.(\d{1,2})\s+(\d{1,2})[:.](\d{2})", text)
            if not m:
                self.group.send(q["to"], "Не разобрал дату. Пример: 26.09 19:40")
                return
            start = dt.datetime(self.now.year, int(m[2]), int(m[1]), int(m[3]), int(m[4]), tzinfo=TZ)
            if start < self.now - dt.timedelta(days=60):
                start = start.replace(year=start.year + 1)
            game["start"] = iso(start)
            q["status"] = "answered"
            self.confirm_game(q["game"], by=q["to"])
            self.flush_queue(q["to"])
            return
        if q["kind"].startswith("mvp"):
            if text.isdigit() and 1 <= int(text) <= len(q["options"]):
                q["status"] = "answered"
                q["answer"] = q["options"][int(text) - 1]
                self.group.send(q["to"], f"Принято: {q['answer']}.")
                if q["kind"] == "mvp_captain":
                    self.set_mvp(q["game"], q["answer"], "выбор капитана")
            else:
                self.group.send(q["to"], f"Пришлите номер от 1 до {len(q['options'])}.")
            self.flush_queue(q["to"])

    # ---------- расписание ----------

    def game_key(self, opponent, start):
        return f"{start:%Y-%m-%d}_{norm_team(opponent)}"

    def find_game(self, opponent, start, days=3):
        key_opp = norm_team(opponent)
        for k, g in self.state["games"].items():
            if g["opp_norm"] == key_opp or _similar(g["opp_norm"], key_opp):
                if abs((from_iso(g["start"]) - start).total_seconds()) <= days * 86400:
                    return k, g
        return None, None

    def add_game(self, opponent, start, venue, source):
        key, g = self.find_game(opponent, start)
        if g:
            return key, g, False
        key = self.game_key(opponent, start)
        g = {"opponent": opponent, "opp_norm": norm_team(opponent), "start": iso(start),
             "venue": venue, "source": source, "status": "confirm", "created": iso(self.now)}
        self.state["games"][key] = g
        self.ask_confirm(key)
        return key, g, True

    def venue_text(self, code):
        full = self.b.get("venues", {}).get(code)
        return f"поле {code}, {full}" if full else (f"поле {code}" if code else "место не указано")

    def ask_confirm(self, key, to=None):
        g = self.state["games"][key]
        start = from_iso(g["start"])
        text = (f"Найден матч ({g['source']}): {self.cfg['team']['name']} и {g['opponent']}\n"
                f"{human(start)}, {self.venue_text(g.get('venue'))}\n"
                "Верно? Ответьте 1 (да) или 2 (нет)")
        for uid in ([to] if to else [self.captain]):
            self.ask(uid, "confirm", key, text)

    def confirm_game(self, key, by):
        g = self.state["games"][key]
        if g["status"] != "confirm":
            return
        g["status"] = "confirmed"
        g["confirmed_by"] = by
        self.close_questions(key, "confirm")
        self.close_questions(key, "datetime")
        self.say(f"Матч с командой «{g['opponent']}» подтвержден")

    def check_posters(self):
        if not self.service.token:
            return  # сервисный ключ не задан: расписание берется только с сайта лиги
        try:
            posts = self.service.call("wall.get", owner_id=-int(self.b["league_group_id"]), count=10)["items"]
        except VKError as e:
            self.token_problem(e)
            return
        new = [p for p in posts if p["id"] not in self.state["seen_posts"]
               and self.now.timestamp() - p["date"] < 14 * 86400]
        if not new:
            return
        from .poster import find_team_matches, read_poster  # тяжелые библиотеки только при необходимости
        for p in new:
            photos = [a["photo"] for a in p.get("attachments", []) if a["type"] == "photo"]
            for ph in photos:
                url = max(ph["sizes"], key=lambda s: s["width"] * s["height"])["url"]
                try:
                    poster = read_poster(requests.get(url, timeout=60).content)
                except Exception as e:
                    self.say(f"Афиша в посте {p['id']} не распознана: {e}")
                    continue
                for r in find_team_matches(poster, self.b["poster_aliases"]):
                    if not r["date"] or not r["time"]:
                        self.say(f"В посте {p['id']} найден матч с {r['opponent']}, но без даты или времени")
                        continue
                    hh, mm = map(int, r["time"].split(":"))
                    start = dt.datetime(r["date"].year, r["date"].month, r["date"].day, hh, mm, tzinfo=TZ)
                    if start < self.now:
                        continue
                    opp = self.known_name(r["opponent"])
                    _, _, created = self.add_game(opp, start, r["venue"], "афиша лиги")
                    if created:
                        self.say(f"С афиши: {opp}, {human(start)}")
            self.state["seen_posts"].append(p["id"])
        self.state["seen_posts"] = self.state["seen_posts"][-100:]

    def known_name(self, ocr_name):
        """Название соперника с афиши (заглавными) -> как на сайте лиги, если удается сопоставить."""
        names = set(self.state.get("known_teams", []))
        best = max(names, key=lambda n: _ratio(norm_team(n), norm_team(ocr_name)), default=None)
        if best and _ratio(norm_team(best), norm_team(ocr_name)) >= 0.75:
            return best
        return ocr_name.title()

    def expire_games(self):
        """Матчи, по которым за 4 дня так и не появился протокол, закрываются."""
        for key, g in self.state["games"].items():
            if g["status"] in ("confirm", "confirmed") and \
                    self.now > from_iso(g["start"]) + dt.timedelta(days=4):
                g["status"] = "expired"
                self.close_questions(key, "confirm")
                self.close_questions(key, "datetime")

    def escalate_confirmations(self):
        limit = dt.timedelta(hours=self.b["confirm_hours"])
        for key, g in self.state["games"].items():
            if g["status"] != "confirm" or g.get("confirm_escalated"):
                continue
            if self.now - from_iso(g["created"]) >= limit:
                g["confirm_escalated"] = True
                for uid in self.assistants:
                    self.ask_confirm(key, to=uid)
                self.say(f"Подтверждение матча с командой «{g['opponent']}» передано помощникам")

    # ---------- опрос о явке ----------

    def announce_games(self):
        """После подтверждения матч объявляется в беседе команды."""
        for key, g in self.state["games"].items():
            start = from_iso(g["start"])
            if g["status"] == "confirmed" and not g.get("announced") and start > self.now:
                self.group.send(self.b["chat_peer_group"],
                                f"Ближайшая игра: {self.cfg['team']['name']} и {g['opponent']}\n"
                                f"{human(start)}, {self.venue_text(g.get('venue'))}")
                g["announced"] = True
                self.say(f"Матч с командой «{g['opponent']}» объявлен в беседе")

    # ---------- рейтинг, протоколы, сводки ----------

    def need_rating_update(self):
        for g in self.state["games"].values():
            start = from_iso(g["start"])
            if g["status"] in ("confirm", "confirmed") and \
                    start + dt.timedelta(hours=self.b["protocol_delay_hours"]) <= self.now <= \
                    start + dt.timedelta(hours=self.b["protocol_search_hours"]):
                return True
        return self.now.hour in (9, 15, 21) or self.rebuild

    def run_rating(self):
        res = self.rating.update(self.cfg, self.rating.web_getter())
        teams = {m["opponent"] for m in res["matches"]} | {u["opponent"] for u in res["upcoming"]}
        self.state["known_teams"] = sorted(set(self.state.get("known_teams", [])) | teams)
        self.site_schedule(res["upcoming"])
        for m in res["matches"]:
            if m["match_id"] in res["fresh"]:
                self.new_protocol(m)
        self.rebuild = False
        return res

    def site_schedule(self, upcoming):
        """Запасной источник расписания и проверка переносов."""
        for u in upcoming:
            start = parse_site_date(u["date"], self.now)
            if not start or start < self.now:
                continue
            key, g = self.find_game(u["opponent"], start)
            if not g:
                self.add_game(u["opponent"], start, "", "сайт лиги")
                self.say(f"С сайта: {u['opponent']}, {human(start)}")
            elif abs((from_iso(g["start"]) - start).total_seconds()) > 300 and \
                    g.get("site_diff") != iso(start):
                g["site_diff"] = iso(start)
                self.group.send(self.captain,
                                f"Расхождение в расписании: матч с командой «{g['opponent']}» в боте "
                                f"{human(from_iso(g['start']))}, а на сайте лиги {human(start)}. "
                                "Если время изменилось, ответьте на ближайший вопрос бота 2 и пришлите новое, "
                                "либо просто учтите это.")

    def new_protocol(self, m):
        played = parse_site_date(m["date"], self.now)
        if played and self.now - played > dt.timedelta(days=3):
            return  # старый матч (например, при первом запуске): без сводки и опроса
        start = played or self.now
        key, g = self.find_game(m["opponent"], start)
        if not g:
            key = self.game_key(m["opponent"], start)
            g = {"opponent": m["opponent"], "opp_norm": norm_team(m["opponent"]), "start": iso(start),
                 "venue": "", "source": "протокол", "created": iso(self.now)}
            self.state["games"][key] = g
        if g.get("match_id"):
            return
        g.update(status="played", match_id=m["match_id"])
        self.close_questions(key, "confirm")
        self.close_questions(key, "datetime")
        self.post_summary(key, m)

    def post_summary(self, key, m):
        g = self.state["games"][key]
        team = self.cfg["team"]["name"]
        score = f"{team} {m['scored']}:{m['conceded']} {m['opponent']}" if m["home"] \
            else f"{m['opponent']} {m['conceded']}:{m['scored']} {team}"
        players = m["players"]
        goals = ", ".join(f"{surname(p['name'])}{' ' + str(p['goals']) if p['goals'] > 1 else ''}"
                          for p in sorted(players, key=lambda p: -p["goals"]) if p["goals"])
        assists = ", ".join(f"{surname(p['name'])}{' ' + str(p['assists']) if p['assists'] > 1 else ''}"
                            for p in sorted(players, key=lambda p: -p["assists"]) if p["assists"])
        gks = ", ".join(surname(p["name"]) for p in players if p["position"] == "Вратарь")
        lines = [f"{score} ({m['date']})"]
        if goals:
            lines.append(f"Голы: {goals}")
        if assists:
            lines.append(f"Передачи: {assists}")
        if gks:
            lines.append(f"В воротах: {gks}, пропущено {m['conceded']} "
                         f"(ожидалось {str(m['expected']).replace('.', ',')})")
        lines.append(f"Протокол: https://rfll.ru/match/{m['match_id']}")
        self.group.send(self.b["chat_peer_group"], "\n".join(lines))
        names = [p["name"] for p in players]
        g["mvp"] = {"stage": "captain", "candidates": names, "players": players,
                    "events": m.get("events", []), "expected": m["expected"], "conceded": m["conceded"],
                    "deadline": iso(self.now + dt.timedelta(hours=self.b["captain_hours"]))}
        lst = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
        self.ask(self.captain, "mvp_captain", key,
                 f"{score}. Выберите лучшего игрока матча, пришлите номер:\n{lst}", names)
        self.say(f"Сводка по матчу с командой «{m['opponent']}» опубликована, вопрос капитану")

    # ---------- лучший игрок ----------

    def match_points(self, p, mvp):
        w = self.cfg["weights"]
        pts = (w["game"] + w["goal"] * p["goals"] + w["assist"] * p["assists"]
               + w["yellow"] * p["yellow"] + w["red"] * p["red"])
        if p["position"] == "Вратарь":
            pts += max(0.0, (mvp["expected"] - mvp["conceded"]) * self.cfg["goalkeeper"]["factor"])
        return pts

    def by_formula(self, mvp, candidates):
        players = {p["name"]: p for p in mvp["players"] if p["name"] in candidates}
        order = [e["name"] for e in mvp.get("events", [])]
        first = lambda n: order.index(n) if n in order else 999
        best = sorted(players.values(), key=lambda p: (
            -self.match_points(p, mvp), -p["goals"], -p["assists"],
            0 if p["position"] == "Вратарь" else 1, first(p["name"]), p["name"]))
        return best[0]["name"] if best else None

    def set_mvp(self, key, name, how):
        g = self.state["games"][key]
        mvp = g.get("mvp") or {}
        if mvp.get("winner"):
            return
        mvp.update(winner=name, how=how, stage="done")
        self.close_questions(key, "mvp")
        if not self.dry:
            with MVP_CSV.open("a", encoding="utf-8") as f:
                f.write(f"{g['match_id']},{name}\n")
        self.group.send(self.b["chat_peer_group"],
                        f"Лучший игрок матча с командой «{g['opponent']}»: {name} ({how}).\n"
                        f"Рейтинг обновлен: {self.b['site_url']}")
        g["status"] = "done"
        self.rebuild = True
        self.say(f"Лучший игрок матча с командой «{g['opponent']}»: {name} ({how})")

    def process_mvp(self):
        for key, g in self.state["games"].items():
            mvp = g.get("mvp")
            if not mvp or mvp.get("stage") == "done":
                continue
            if mvp["stage"] == "captain" and self.now >= from_iso(mvp["deadline"]):
                mvp.update(stage="assistants",
                           deadline=iso(self.now + dt.timedelta(hours=self.b["assistants_hours"])))
                lst = "\n".join(f"{i}. {n}" for i, n in enumerate(mvp["candidates"], 1))
                self.say(f"Капитан не ответил по матчу с командой «{g['opponent']}», вопрос помощникам")
                for uid in self.assistants:
                    self.ask(uid, "mvp_assist", key,
                             f"Капитан не выбрал лучшего игрока матча с командой «{g['opponent']}». "
                             f"Проголосуйте, пришлите номер (24 часа, решает большинство):\n{lst}",
                             mvp["candidates"])
            elif mvp["stage"] == "assistants" and self.now >= from_iso(mvp["deadline"]):
                votes = [q["answer"] for q in self.state["questions"]
                         if q["game"] == key and q["kind"] == "mvp_assist" and q.get("answer")]
                counts = {n: votes.count(n) for n in set(votes)}
                top = max(counts.values(), default=0)
                leaders = [n for n, c in counts.items() if c == top and c > 0]
                if len(leaders) == 1:
                    self.set_mvp(key, leaders[0], "решение помощников")
                else:
                    self.set_mvp(key, self.by_formula(mvp, mvp["candidates"]), "по баллам за матч")

    # ---------- месячный рейтинг ----------

    def monthly_report(self, matches):
        month = (self.now.replace(day=1) - dt.timedelta(days=1))
        tag = f"{month:%Y-%m}"
        if self.now.day != 1 or self.now.hour < 12 or self.state["monthly_sent"] == tag:
            return
        ms = [m for m in matches if (d := parse_site_date(m["date"], self.now))
              and d.year == month.year and d.month == month.month]
        self.state["monthly_sent"] = tag
        if not ms:
            return
        rows = score_players(ms, self.cfg["weights"], self.cfg["goalkeeper"])
        fmt = lambda x: str(round(x, 2)).replace(".", ",")
        top = "\n".join(f"{i}. {r['name']}: {fmt(r['total'])}" for i, r in enumerate(rows[:5], 1))
        regular = [r for r in rows if r["games"] >= 2] or rows
        per = "\n".join(f"{i}. {r['name']}: {fmt(r['per_match'])}" for i, r in enumerate(
            sorted(regular, key=lambda r: -r["per_match"])[:3], 1))
        gks = [r for r in rows if r["gk_games"]]
        gk = max(gks, key=lambda r: r["total"], default=None)
        text = (f"Итоги месяца: {MONTHS_NOM[month.month - 1]} {month.year}, "
                f"матчей: {len(ms)}\n\nЛучшие по общему баллу:\n{top}\n\n"
                f"Лучшие по баллам за матч (от 2 игр):\n{per}")
        if gk:
            text += f"\n\nЛучший вратарь: {gk['name']}, {fmt(gk['total'])}"
        text += f"\n\nПолный рейтинг: {self.b['site_url']}"
        self.group.send(self.b["chat_peer_group"], text)
        self.say("Опубликован рейтинг месяца")

    # ---------- ключи ----------

    def token_problem(self, err):
        self.say(f"Ошибка ВКонтакте: {err}")
        if getattr(err, "code", None) in (5, 15, 27, 28, 30):
            day = f"{self.now:%Y-%m-%d}"
            if self.state["alerts"].get("service_token") != day:
                self.state["alerts"]["service_token"] = day
                try:
                    self.group.send(self.captain,
                                    "Бот не может прочитать афиши лиги: сервисный ключ приложения не работает. "
                                    "Расписание пока берется с сайта лиги. Проверьте ключ по README.")
                except VKError:
                    pass

    # ---------- основной цикл ----------

    def run(self):
        self.resolve_people()
        self.read_answers()
        self.check_posters()
        self.expire_games()
        self.escalate_confirmations()
        res = None
        if self.need_rating_update():
            res = self.run_rating()
            players = {p["name"] for m in res["matches"] for p in m["players"]}
            self.state["known_players"] = sorted(players)
        self.announce_games()
        self.process_mvp()
        if self.rebuild:
            res = self.run_rating()
        if self.now.day == 1 and self.now.hour >= 12:
            if res is None:
                res = self.run_rating()
            self.monthly_report(res["matches"])
        for q in self.state["questions"]:
            if q["status"] == "queued":
                self.flush_queue(q["to"])
        # старые завершенные записи не нужны
        cutoff = self.now - dt.timedelta(days=60)
        self.state["questions"] = [q for q in self.state["questions"]
                                   if q["status"] in ("queued", "sent") or from_iso(q["asked"]) > cutoff]
        if not self.dry:
            save_state(self.state)
        if not self.log:
            print("Бот: делать нечего")


def _ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _similar(a, b):
    return _ratio(a, b) >= 0.8
