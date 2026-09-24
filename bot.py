"""Запуск бота команды.

  python bot.py                  рабочий запуск (раз в час из GitHub Actions)
  python bot.py --dry-run        пробный запуск: ничего не отправляет и не сохраняет, только печатает
  python bot.py --check          проверка ключей и список бесед (для заполнения config.yaml)
  python bot.py --check-posters  проверка чтения и распознавания афиш лиги

Ключи берутся из переменных окружения (секреты GitHub):
  VK_GROUP_TOKEN    ключ сообщества;
  VK_SERVICE_TOKEN  сервисный ключ собственного приложения VK ID (только для афиш).
"""
import argparse
import os
import sys

import main as rating
from rfl.bot import Bot
from rfl.vk import VK, VKError


def check(cfg):
    group = VK(os.environ.get("VK_GROUP_TOKEN"), "сообщество")
    ok = True
    try:
        g = group.call("groups.getById")
        g = g["groups"][0] if isinstance(g, dict) else g[0]
        print(f"Ключ сообщества работает: «{g['name']}» (club{g['id']})")
        items = group.call("messages.getConversations", count=100)["items"]
        chats = [i["conversation"] for i in items if i["conversation"]["peer"]["type"] == "chat"]
        print("\nБеседы, в которые добавлено сообщество:")
        if not chats:
            print("  нет ни одной (добавьте сообщество в беседу команды и назначьте администратором)")
        for c in chats:
            print(f"  {c['peer']['id']}  «{c.get('chat_settings', {}).get('title', '')}»")
    except VKError as e:
        ok = False
        print("Ключ сообщества НЕ работает:", e)
    try:
        names = [cfg["vk"]["captain"]] + cfg["vk"]["assistants"]
        users = group.call("users.get", user_ids=",".join(names))
        print("\nКапитан и помощники:", ", ".join(f"{u['first_name']} {u['last_name']}" for u in users))
    except VKError as e:
        print("Не удалось найти капитана и помощников:", e)
    service = VK(os.environ.get("VK_SERVICE_TOKEN"), "приложение")
    if service.token:
        try:
            service.call("wall.get", owner_id=-int(cfg["bot"]["league_group_id"]), count=1)
            print("\nСервисный ключ работает: стена лиги читается")
        except VKError as e:
            print("\nСервисный ключ НЕ работает:", e)
    else:
        print("\nСервисный ключ не задан: расписание будет браться только с сайта лиги")
    print("\nВпишите номер беседы команды в config.yaml, параметр chat_peer_group.")
    return 0 if ok else 1


def check_posters(cfg):
    """Загружает последние посты лиги и показывает, что распознано на афишах."""
    import requests
    from rfl.poster import find_team_matches, read_poster
    service = VK(os.environ.get("VK_SERVICE_TOKEN"), "приложение")
    try:
        posts = service.call("wall.get", owner_id=-int(cfg["bot"]["league_group_id"]), count=10)["items"]
    except VKError as e:
        print("Стена лиги НЕ читается:", e)
        return 1
    print(f"Стена лиги читается, постов: {len(posts)}")
    shown = 0
    for p in posts:
        photos = [a["photo"] for a in p.get("attachments", []) if a["type"] == "photo"]
        for ph in photos:
            url = max(ph["sizes"], key=lambda s: s["width"] * s["height"])["url"]
            poster = read_poster(requests.get(url, timeout=60).content)
            if not poster["rows"]:
                continue
            shown += 1
            print(f"\nПост {p['id']}: даты {poster['range']}, матчей распознано {len(poster['rows'])}")
            for r in poster["rows"][:5]:
                print(f"  {r['day']:>5} {r['date']}  {r['home']}  {r['time']}  {r['away']}  {r['venue']}")
            for r in find_team_matches(poster, cfg["bot"]["poster_aliases"]):
                print(f"  НАЙДЕН МАТЧ КОМАНДЫ: соперник «{r['opponent']}», {r['date']} {r['time']}, поле {r['venue']}")
            if shown >= 3:
                return 0
    if not shown:
        print("Афиш с таблицами в последних постах не найдено")
    return 0


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--check-posters", action="store_true")
    args = ap.parse_args()
    cfg = rating.load_config()
    if args.check:
        return check(cfg)
    if args.check_posters:
        return check_posters(cfg)
    if not cfg["bot"].get("chat_peer_group"):
        print("Бот не настроен: в config.yaml не указан номер беседы. Обновляю только рейтинг.")
        rating.update(cfg, rating.web_getter())
        return 0
    bot = Bot(cfg, os.environ.get("VK_GROUP_TOKEN"), os.environ.get("VK_SERVICE_TOKEN"),
              dry_run=args.dry_run or os.environ.get("BOT_DRY_RUN") == "1", rating=rating)
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
