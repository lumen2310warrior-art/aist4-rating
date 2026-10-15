"""Проверка сезонов: python tests/test_seasons.py  (или python -m pytest tests)"""
import datetime as dt
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import main as M
from rfl.seasons import DEFAULT_SEASONS, resolve_date, season_of, seasons_from_cfg
from rfl.timeutil import TZ

SEASONS = seasons_from_cfg({})
NOW = dt.datetime(2026, 10, 15, 12, 0, tzinfo=TZ)


def test_year_is_last_past_date():
    assert resolve_date("29 мая 20:00", NOW).year == 2026
    assert resolve_date("21.09 21:00", NOW).date() == dt.date(2026, 9, 21)
    # дата позже «сегодня + 1 день» относится к прошлому году, а не к будущему
    assert resolve_date("20 декабря 19:00", NOW).year == 2025
    # дата в пределах суток вперед остается в этом году
    assert resolve_date("16 октября 10:00", NOW).date() == dt.date(2026, 10, 16)
    assert resolve_date("(не задано)", NOW) is None
    assert resolve_date("", NOW) is None


def test_season_of():
    key = lambda s: season_of(resolve_date(s, NOW), SEASONS)
    assert key("29 мая 20:00") == "2026"
    assert key("15 октября 23:00") == "2026"
    assert key("16 октября 10:00") == "2026-2027"
    assert season_of(dt.datetime(2027, 5, 1, tzinfo=TZ), SEASONS) == "2027"
    assert season_of(dt.datetime(2025, 5, 1, tzinfo=TZ), SEASONS) is None
    assert season_of(None, SEASONS) is None


def test_config_override():
    cfg = {"seasons": [{"key": "2027", "title": "Сезон 2027", "start": "2027-01-01", "end": "2027-12-31"}]}
    s = seasons_from_cfg(cfg)
    assert [x["key"] for x in s] == ["2027"] and s[0]["start"] == dt.date(2027, 1, 1)


def _match(mid, season, played, scored=3, conceded=1):
    pl = {"player_id": 1, "name": "Игрок 1", "position": "Нападающий",
          "goals": 1, "assists": 0, "op": 0, "yellow": 0, "red": 0}
    return {"match_id": mid, "date": "", "played": played, "season": season, "opponent": "X", "home": True,
            "scored": scored, "conceded": conceded, "expected": 5, "expected_basis": "лига",
            "players": [pl], "mvp_ids": set(), "mvp_names": [], "group": "championship", "events": []}


def test_views_split_by_season():
    cfg = M.load_config()
    groups = {"championship": {"title": "Чемпионат", "matches": [
        _match(1, "2026", "2026-05-01T20:00:00+04:00"),
        _match(2, "2026", "2026-09-01T20:00:00+04:00"),
        _match(3, "2026-2027", "2026-10-16T20:00:00+04:00"),
        _match(4, None, "")]}, "cup": {"title": "Кубок", "matches": []}}
    views, info, default = M.build(cfg, groups)
    games = lambda k: views[k]["all"]["players"][0]["games"] if views[k]["all"]["players"] else 0
    assert games("all") == 4 and games("2026") == 2 and games("2026-2027") == 1
    assert {s["key"] for s in info} >= {"2026", "2026-2027"}
    assert default in ("2026", "2026-2027", "all")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
