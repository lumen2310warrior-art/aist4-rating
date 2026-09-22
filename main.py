"""Обновление рейтинга: забирает данные с rfll.ru, считает баллы, собирает страницу docs/index.html.

Запуск:  python main.py          (рабочий режим, данные с сайта лиги)
         python main.py --demo   (проверка на сохраненных страницах из tests/fixtures)
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys
import time

import requests
import yaml

from rfl.parser import norm_team, parse_match, parse_team_calendar
from rfl.scoring import division_stats, expected_goals, score_players
from rfl.site import render

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "data" / "cache"
BASE = "https://rfll.ru"


def web_getter():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (team stats script; aist-4)"

    def get(url):
        time.sleep(1)  # бережно к сайту лиги
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    return get


def fixture_getter():
    mapping = json.loads((ROOT / "tests" / "fixtures" / "map.json").read_text(encoding="utf-8"))

    def get(url):
        return (ROOT / "tests" / "fixtures" / mapping[url]).read_text(encoding="utf-8")
    return get


def load_mvp(path):
    """data/mvp.csv: match_id, player (номер игрока на rfll.ru или фамилия/ФИО как в протоколе)."""
    result = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = (row.get("match_id") or "").strip()
            who = (row.get("player") or "").strip()
            if mid.isdigit() and who:
                result.setdefault(int(mid), []).append(who)
    return result


def resolve_mvp(entries, players, match_id, warnings):
    ids = set()
    for e in entries:
        if e.isdigit() and any(p["player_id"] == int(e) for p in players):
            ids.add(int(e))
            continue
        key = e.lower().replace("ё", "е")
        hits = [p for p in players if p["name"].lower().replace("ё", "е").startswith(key)]
        if len(hits) == 1:
            ids.add(hits[0]["player_id"])
        else:
            warnings.append(f"Матч {match_id}: лучший игрок «{e}» не найден в составе однозначно")
    return ids


def get_protocol(match_id, get_html, use_cache):
    path = CACHE / f"match_{match_id}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    proto = parse_match(get_html(f"{BASE}/match/{match_id}"), match_id)
    if use_cache and proto["home_goals"] is not None:
        path.write_text(json.dumps(proto, ensure_ascii=False, indent=1), encoding="utf-8")
    return proto


def group_of(tournament, cfg):
    for key, words in cfg["groups"].items():
        if any(w.lower() in tournament.lower() for w in words):
            return key
    return None


def load_index():
    path = ROOT / "data" / "our_matches.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_manual_cup(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [int(r["match_id"]) for r in csv.DictReader(f) if (r.get("match_id") or "").strip().isdigit()]


def collect(cfg, get_html, use_cache, warnings):
    team = cfg["team"]
    team_key = norm_team(team["name"])
    mvp_all = load_mvp(ROOT / "data" / "mvp.csv")

    # 1. Свои матчи: страница команды (адрес без параметров, разрешен правилами сайта).
    #    Список копится в data/our_matches.json, чтобы матчи не терялись при смене турнира на странице.
    index = load_index() if use_cache else {}
    try:
        tournament, cal = parse_team_calendar(get_html(f"{BASE}/team/{team['rfll_id']}/calendar"))
        group = group_of(tournament, cfg)
        if not group:
            warnings.append(f"Турнир «{tournament}» на странице команды не отнесен ни к Чемпионату, ни к Кубку")
        for m in cal:
            if m["home_goals"] is not None and group:
                index[str(m["match_id"])] = {"group": group, "tournament": tournament, "date": m["date"]}
    except Exception as exc:
        warnings.append(f"Страница команды не загружена ({exc})")
    for mid in load_manual_cup(ROOT / "data" / "cup_matches.csv"):
        index.setdefault(str(mid), {"group": "cup", "tournament": "Кубок", "date": ""})
    if use_cache:
        (ROOT / "data" / "our_matches.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2. Протоколы своих матчей.
    games = []
    for mid, meta in sorted(index.items(), key=lambda x: int(x[0])):
        try:
            proto = get_protocol(int(mid), get_html, use_cache)
        except Exception as exc:
            warnings.append(f"Матч {mid}: протокол не загружен ({exc})")
            continue
        if proto["home_goals"] is None:
            continue
        home_side = proto.get("home_id") == team["rfll_id"] or norm_team(proto["home"]) == team_key
        games.append((meta, proto, home_side))

    # 3. Календари соперников: их результативность и общее среднее по лиге.
    pool = {}
    loaded = set()
    for meta, proto, home_side in games:
        opp_id = proto["away_id"] if home_side else proto["home_id"]
        if not opp_id or opp_id in loaded:
            continue
        loaded.add(opp_id)
        try:
            _, opp_cal = parse_team_calendar(get_html(f"{BASE}/team/{opp_id}/calendar"))
            for m in opp_cal:
                pool[m["match_id"]] = m
        except Exception as exc:
            warnings.append(f"Календарь соперника {proto['away' if home_side else 'home']} не загружен ({exc})")
    stats = division_stats(list(pool.values()))

    # 4. Сборка матчей для расчета.
    groups = {k: {"title": cfg["group_titles"][k], "matches": []} for k in cfg["groups"]}
    for meta, proto, home_side in games:
        side, other = ("home", "away") if home_side else ("away", "home")
        opponent = proto[other]
        expected, basis = expected_goals(opponent, stats, cfg["goalkeeper"])
        players = proto["lineups"][side]
        mid = proto["match_id"]
        mvp_ids = resolve_mvp(mvp_all.get(mid, []), players, mid, warnings)
        groups[meta["group"]]["matches"].append({
            "match_id": mid, "date": meta.get("date") or proto.get("date", ""), "opponent": opponent,
            "home": home_side, "scored": proto[f"{side}_goals"], "conceded": proto[f"{other}_goals"],
            "expected": round(expected, 2), "expected_basis": basis,
            "players": players, "mvp_ids": mvp_ids,
            "mvp_names": [p["name"] for p in players if p["player_id"] in mvp_ids],
            "group": meta["group"],
        })
    return groups


def build(cfg, groups):
    out = {}
    all_matches = []
    for key, g in groups.items():
        all_matches += g["matches"]
        out[key] = {"title": g["title"],
                    "players": score_players(g["matches"], cfg["weights"], cfg["goalkeeper"]),
                    "matches": [public_match(m) for m in g["matches"]]}
    out["all"] = {"title": "Все турниры",
                  "players": score_players(all_matches, cfg["weights"], cfg["goalkeeper"]),
                  "matches": [public_match(m) for m in all_matches]}
    return out


def public_match(m):
    return {k: m[k] for k in ("match_id", "date", "opponent", "home", "scored", "conceded",
                              "expected", "expected_basis", "mvp_names", "group")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="собрать страницу по сохраненным образцам")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    warnings = []
    getter = fixture_getter() if args.demo else web_getter()
    groups = collect(cfg, getter, use_cache=not args.demo, warnings=warnings)
    data = {"team": cfg["team"]["name"], "title": cfg["site"]["title"],
            "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).strftime("%d.%m.%Y %H:%M"),
            "weights": cfg["weights"], "gk_factor": cfg["goalkeeper"]["factor"],
            "groups": build(cfg, groups), "warnings": warnings}

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (docs / "index.html").write_text(render(data), encoding="utf-8")

    for w in warnings:
        print("ВНИМАНИЕ:", w)
    n = len(data["groups"]["all"]["matches"])
    print(f"Готово: матчей {n}, игроков {len(data['groups']['all']['players'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
