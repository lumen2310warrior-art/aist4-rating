"""Прогон логики бота на поддельном ВКонтакте: python tests/test_bot_flow.py"""
import datetime as dt, sys, pathlib, tempfile, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rfl.bot as B
from rfl.timeutil import TZ

class FakeVK:
    def __init__(self, name, token="x"): self.name, self.token, self.sent, self.inbox = name, token, [], {}
    def call(self, method, **p):
        if method == "users.get":
            return [{"id": {"lumwar": 1, "alexander__eremeev": 2, "alex_khait": 3, "id30136141": 4, "ivkaur": 5}[n]}
                    for n in p["user_ids"].split(",")]
        if method == "messages.getHistory": return {"items": self.inbox.get(p["peer_id"], [])}
        raise AssertionError(method)
    def send(self, peer, text, attachment=None): self.sent.append((peer, text))

players = [{"player_id": 10 + i, "name": n, "position": pos, "goals": g, "assists": a, "yellow": 0, "red": 0, "op": 0}
           for i, (n, pos, g, a) in enumerate([("Казаков Кирилл", "Вратарь", 0, 0), ("Демидов Данила", "Нападающий", 2, 0),
                                                ("Селезнев Егор", "Нападающий", 2, 1), ("Воинцев Алексей", "Защитник", 0, 0)])]
match = {"match_id": 40001, "date": "26 сентября 19:40", "opponent": "Титаны", "home": True, "scored": 4,
         "conceded": 3, "expected": 6.0, "players": players, "mvp_ids": set(), "group": "championship",
         "events": [{"name": "Селезнев Егор", "second": 60}]}

class FakeRating:
    def __init__(self): self.res = {"matches": [], "upcoming": [], "fresh": set()}
    def web_getter(self): return None
    def update(self, cfg, getter): return self.res

def make(now, state=None):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg["bot"]["chat_peer_group"] = 2000000001
    bot = B.Bot(cfg, "g", "", dry_run=True, rating=FAKE)
    bot.group = G
    if state is not None: bot.state = state
    bot.now = now
    return bot

G, FAKE = FakeVK("group"), FakeRating()
t0 = dt.datetime(2026, 9, 23, 9, 0, tzinfo=TZ)

# 1. сайт показал матч -> вопрос капитану
FAKE.res["upcoming"] = [{"match_id": 40001, "opponent": "Титаны", "date": "26 сентября 19:40"}]
b = make(t0); b.run(); st = b.state
print("1.", G.sent[-1][1].replace("\n", " | "))

# 2. капитан отвечает 1 -> объявление в беседе
G.inbox[1] = [{"id": 7, "from_id": 1, "text": "1", "date": int(t0.timestamp()) + 600}]
b = make(t0 + dt.timedelta(hours=1), st); b.run()
assert list(st["games"].values())[0]["status"] == "confirmed"
print("2.", G.sent[-1][1].replace("\n", " | "))

# 3. протокол -> сводка в беседе и сразу вопрос капитану
FAKE.res = {"matches": [match], "upcoming": [], "fresh": {40001}}
b = make(dt.datetime(2026, 9, 26, 21, 45, tzinfo=TZ), st); b.run()
print("3. беседа:", G.sent[-2][1].replace("\n", " | "))
print("   капитану:", G.sent[-1][1].replace("\n", " | "))

# 4a. вариант: капитан ответил номером
import copy
st_a = copy.deepcopy(st)
G.inbox[1] = [{"id": 8, "from_id": 1, "text": "2", "date": int(dt.datetime(2026, 9, 26, 22, 30, tzinfo=TZ).timestamp())}]
FAKE.res = {"matches": [match], "upcoming": [], "fresh": set()}
b = make(dt.datetime(2026, 9, 26, 23, 0, tzinfo=TZ), st_a); b.run()
g = list(st_a["games"].values())[0]
print("4a.", g["mvp"]["winner"], "|", g["mvp"]["how"])
assert g["mvp"]["winner"] == "Демидов Данила"

# 4b. вариант: все молчат -> помощники -> формула
G.inbox[1] = []
b = make(dt.datetime(2026, 9, 28, 22, 0, tzinfo=TZ), st); b.run()
b = make(dt.datetime(2026, 9, 29, 23, 0, tzinfo=TZ), st); b.run()
g = list(st["games"].values())[0]
print("4b.", g["mvp"]["winner"], "|", g["mvp"]["how"])
assert g["mvp"]["winner"] == "Селезнев Егор"
print("Все шаги пройдены")
