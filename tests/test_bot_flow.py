"""Прогон логики бота на поддельном ВКонтакте: python tests/test_bot_flow.py"""
import datetime as dt, sys, pathlib, tempfile, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rfl.bot as B
from rfl.timeutil import TZ

class FakeVK:
    def __init__(self, name): self.name, self.sent, self.polls, self.inbox, self.votes = name, [], [], {}, {}
    def call(self, method, **p):
        if method == "users.get":
            return [{"id": {"lumwar": 1, "alexander__eremeev": 2, "alex_khait": 3, "id30136141": 4, "ivkaur": 5}[n]}
                    for n in p["user_ids"].split(",")]
        if method == "wall.get": return {"items": []}
        if method == "polls.create":
            self.polls.append(p); return {"id": len(self.polls), "owner_id": 99}
        if method == "messages.getHistory": return {"items": self.inbox.get(p["peer_id"], [])}
        if method == "polls.getById":
            return {"answers": [{"id": i + 1, "text": t} for i, t in enumerate(self.polls[p["poll_id"] - 1]["add_answers"])]}
        if method == "polls.getVoters":
            return [{"answer_id": a, "users": {"items": us}} for a, us in self.votes.items()]
        raise AssertionError(method)
    def send(self, peer, text, attachment=None): self.sent.append((peer, text, attachment))

players = [{"player_id": 10 + i, "name": n, "position": pos, "goals": g, "assists": a, "yellow": 0, "red": 0, "op": 0}
           for i, (n, pos, g, a) in enumerate([("Казаков Кирилл", "Вратарь", 0, 0), ("Демидов Данила", "Нападающий", 2, 0),
                                                ("Селезнев Егор", "Нападающий", 2, 1), ("Воинцев Алексей", "Защитник", 0, 0)])]
match = {"match_id": 40001, "date": "26 сентября 19:40", "opponent": "Титаны", "home": True, "scored": 4,
         "conceded": 3, "expected": 6.0, "players": players, "mvp_ids": set(), "group": "championship",
         "events": [{"name": "Селезнев Егор", "second": 60}, {"name": "Демидов Данила", "second": 90}]}

class FakeRating:
    def __init__(self): self.res = {"matches": [], "upcoming": [], "fresh": set()}
    def web_getter(self): return None
    def update(self, cfg, getter): return self.res

def make(now, state=None):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg["bot"]["chat_peer_group"], cfg["bot"]["chat_peer_user"] = 2000000001, 2000000005
    bot = B.Bot(cfg, "g", "u", dry_run=True, rating=FAKE)
    bot.group, bot.user = G, U
    if state is not None: bot.state = state
    bot.now = now
    return bot

tmp = pathlib.Path(tempfile.mkdtemp())
B.MVP_CSV = tmp / "mvp.csv"
G, U, FAKE = FakeVK("group"), FakeVK("user"), FakeRating()
t0 = dt.datetime(2026, 9, 23, 10, 0, tzinfo=TZ)

# 1. сайт показал матч -> вопрос капитану
FAKE.res["upcoming"] = [{"match_id": 40001, "opponent": "Титаны", "date": "26 сентября 19:40"}]
b = make(t0.replace(hour=9)); b.run(); st = b.state
assert any(q["kind"] == "confirm" and q["status"] == "sent" for q in st["questions"]), "нет вопроса"
print("1. вопрос капитану:", G.sent[-1][1].splitlines()[0])

# 2. капитан отвечает 1 -> опрос о явке
G.inbox[1] = [{"id": 7, "from_id": 1, "text": "1", "date": int(t0.timestamp()) + 600}]
b = make(t0 + dt.timedelta(hours=1), st); b.run()
assert list(st["games"].values())[0]["status"] == "confirmed"
assert U.polls and U.polls[-1]["add_answers"] == ["Буду", "Не буду", "Под вопросом"]
print("2. опрос о явке:", U.polls[-1]["question"])

# 3. через 2 часа после матча появился протокол -> сводка и опрос
FAKE.res = {"matches": [match], "upcoming": [], "fresh": {40001}}
b = make(dt.datetime(2026, 9, 26, 21, 45, tzinfo=TZ), st); b.run()
print("3. сводка:", G.sent[-1][1].replace("\n", " | "))
assert U.polls[-1]["add_answers"][1] == "Демидов Данила"

# 4. опрос закрыт: ничья 1,0 : 1,0, голос за себя отброшен -> вопрос капитану
FAKE.res = {"matches": [match], "upcoming": [], "fresh": set()}
U.votes = {2: [{"id": 50, "first_name": "Иван", "last_name": "Петров"}],
           3: [{"id": 51, "first_name": "Олег", "last_name": "Сидоров"},
               {"id": 52, "first_name": "Егор", "last_name": "Селезнев"}]}   # Селезнев за себя
b = make(dt.datetime(2026, 9, 27, 22, 0, tzinfo=TZ), st); b.run()
g = list(st["games"].values())[0]
print("4. итоги голосования:", g["mvp"]["totals"], "этап:", g["mvp"]["stage"])
assert g["mvp"]["stage"] == "captain"

# 5. капитан молчит 48 ч -> помощники; помощники тоже молчат 24 ч -> формула
b = make(dt.datetime(2026, 9, 29, 23, 0, tzinfo=TZ), st); b.run()
assert g["mvp"]["stage"] == "assistants"
b = make(dt.datetime(2026, 9, 30, 23, 30, tzinfo=TZ), st); b.run()
print("5. итог:", g["mvp"]["winner"], "|", g["mvp"]["how"])
assert g["mvp"]["winner"] == "Селезнев Егор"   # 1+2,4+1 больше, чем у Демидова 1+2,4
print("6. сообщение в беседу:", G.sent[-1][1].splitlines()[0])
print("Все шаги пройдены")
