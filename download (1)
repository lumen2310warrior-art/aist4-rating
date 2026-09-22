"""Расчет баллов: полевые игроки, бонус вратаря, итог и баллы за матч."""
from collections import defaultdict
from .parser import norm_team


def division_stats(calendar):
    """Результативность команд по сыгранным матчам из загруженных календарей."""
    goals = defaultdict(int)
    games = defaultdict(int)
    for m in calendar:
        if m["home_goals"] is None or m["away_goals"] is None:
            continue
        for team, g in ((m["home"], m["home_goals"]), (m["away"], m["away_goals"])):
            goals[norm_team(team)] += g
            games[norm_team(team)] += 1
    total_games = sum(games.values())
    league_avg = sum(goals.values()) / total_games if total_games else None
    return {"goals": dict(goals), "games": dict(games), "league_avg": league_avg}


def expected_goals(opponent, stats, gk_cfg):
    """Ожидаемые голы соперника: его средняя результативность или среднее по лиге."""
    key = norm_team(opponent)
    league = stats["league_avg"] if stats["league_avg"] is not None else gk_cfg["default_league_avg"]
    games = stats["games"].get(key, 0)
    if games >= gk_cfg["min_opponent_games"]:
        return stats["goals"][key] / games, "соперник"
    return league, "лига"


def new_row(p):
    return {"player_id": p["player_id"], "name": p["name"], "position": p["position"],
            "games": 0, "goals": 0, "assists": 0, "mvp": 0, "yellow": 0, "red": 0,
            "op": 0, "gk_games": 0, "gk_bonus": 0.0, "total": 0.0, "per_match": 0.0}


def score_players(matches, weights, gk_cfg):
    """matches: список матчей команды с полями players, conceded, expected, mvp_ids."""
    rows = {}
    for m in matches:
        for p in m["players"]:
            r = rows.setdefault(p["player_id"], new_row(p))
            r["name"] = p["name"] or r["name"]
            r["position"] = p["position"] or r["position"]
            r["games"] += 1
            for k in ("goals", "assists", "yellow", "red", "op"):
                r[k] += p[k]
            if p["player_id"] in m["mvp_ids"]:
                r["mvp"] += 1
            if p["position"] == "Вратарь" and m["conceded"] is not None:
                bonus = max(0.0, (m["expected"] - m["conceded"]) * gk_cfg["factor"])
                r["gk_games"] += 1
                r["gk_bonus"] += bonus
    w = weights
    for r in rows.values():
        r["total"] = round(w["game"] * r["games"] + w["goal"] * r["goals"]
                           + w["assist"] * r["assists"] + w["mvp"] * r["mvp"]
                           + w["yellow"] * r["yellow"] + w["red"] * r["red"]
                           + r["gk_bonus"], 2)
        r["gk_bonus"] = round(r["gk_bonus"], 2)
        r["per_match"] = round(max(0.0, r["total"] / r["games"]), 2) if r["games"] else 0.0
    return sorted(rows.values(), key=lambda r: (-r["total"], -r["per_match"], r["name"]))
