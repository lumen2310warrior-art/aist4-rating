"""Проверка формулы: python -m pytest tests  или  python tests/test_scoring.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rfl.scoring import division_stats, expected_goals, score_players
from rfl.parser import split_score

W = {"game": 1.0, "goal": 1.2, "assist": 1.0, "mvp": 1.5, "yellow": -0.5, "red": -1.0}
GK = {"factor": 0.3, "min_opponent_games": 3, "default_league_avg": 6.0}

def p(pid, pos="Нападающий", **kw):
    base = {"player_id": pid, "name": f"Игрок {pid}", "position": pos,
            "goals": 0, "assists": 0, "op": 0, "yellow": 0, "red": 0}
    base.update(kw); return base

def test_field_player():
    m = {"players": [p(1, goals=2, assists=1, yellow=1)], "mvp_ids": {1}, "conceded": 3, "expected": 6}
    r = score_players([m], W, GK)[0]
    assert r["total"] == round(1 + 2.4 + 1 + 1.5 - 0.5, 2)

def test_goalkeeper_bonus_and_floor():
    good = {"players": [p(9, "Вратарь")], "mvp_ids": set(), "conceded": 2, "expected": 6}
    bad = {"players": [p(9, "Вратарь")], "mvp_ids": set(), "conceded": 9, "expected": 6}
    r = score_players([good, bad], W, GK)[0]
    assert r["gk_bonus"] == 1.2 and r["total"] == 3.2

def test_per_match_not_negative():
    m = {"players": [p(5, yellow=1, red=1)], "mvp_ids": set(), "conceded": 0, "expected": 0}
    r = score_players([m], W, GK)[0]
    assert r["total"] == -0.5 and r["per_match"] == 0.0

def test_expected_goals_rules():
    cal = [{"home": "A", "away": "B", "home_goals": 8, "away_goals": 2}] * 3 + \
          [{"home": "C", "away": "D", "home_goals": 4, "away_goals": 6}]
    s = division_stats(cal)
    assert expected_goals("A", s, GK)[0] == 8
    assert expected_goals("C", s, GK) == ((24 + 6 + 4 + 6) / 8, "лига")

def test_score_split():
    assert split_score("Команда 2 3:1 Аист-4") == ("Команда 2", 3, 1, "Аист-4")
    assert split_score("Аист-4 -:- Солнышко") == ("Аист-4", None, None, "Солнышко")

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
