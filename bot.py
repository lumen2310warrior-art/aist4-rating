"""Запуск бота команды.

  python bot.py              рабочий запуск (раз в час из GitHub Actions)
  python bot.py --dry-run    пробный запуск: ничего не отправляет и не сохраняет, только печатает
  python bot.py --check      проверка ключей и список бесед (для заполнения config.yaml)

Ключи берутся из переменных окружения VK_GROUP_TOKEN и VK_USER_TOKEN (секреты GitHub).
"""
import argparse
import os
import sys

import main as rating
from rfl.bot import Bot
from rfl.vk import VK, VKError


def conversations(vk, who):
    print(f"\nБеседы, доступные для ключа «{who}»:")
    try:
        items = vk.call("messages.getConversations", count=100)["items"]
    except VKError as e:
        print("  не удалось получить:", e)
        return
    chats = [i["conversation"] for i in items if i["conversation"]["peer"]["type"] == "chat"]
    if not chats:
        print("  бесед нет (проверьте, что аккаунт или сообщество добавлены в беседу)")
    for c in chats:
        print(f"  {c['peer']['id']}  «{c.get('chat_settings', {}).get('title', '')}»")


def check(cfg):
    group = VK(os.environ.get("VK_GROUP_TOKEN"), "сообщество")
    user = VK(os.environ.get("VK_USER_TOKEN"), "технический аккаунт")
    ok = True
    try:
        g = group.call("groups.getById")
        g = g["groups"][0] if isinstance(g, dict) else g[0]
        print(f"Ключ сообщества работает: «{g['name']}» (club{g['id']})")
        conversations(group, "сообщество")
    except VKError as e:
        ok = False
        print("Ключ сообщества НЕ работает:", e)
    try:
        u = user.call("users.get")[0]
        print(f"\nКлюч технического аккаунта работает: {u['first_name']} {u['last_name']} (id{u['id']})")
        conversations(user, "технический аккаунт")
        user.call("wall.get", owner_id=-int(cfg["bot"]["league_group_id"]), count=1)
        print("Стена лиги читается")
    except VKError as e:
        ok = False
        print("Ключ технического аккаунта НЕ работает:", e)
    try:
        names = [cfg["vk"]["captain"]] + cfg["vk"]["assistants"]
        users = group.call("users.get", user_ids=",".join(names))
        print("\nКапитан и помощники:", ", ".join(f"{u['first_name']} {u['last_name']}" for u in users))
    except VKError as e:
        print("Не удалось найти капитана и помощников:", e)
    print("\nВпишите номера беседы команды в config.yaml: chat_peer_group (из списка сообщества) "
          "и chat_peer_user (из списка технического аккаунта).")
    return 0 if ok else 1


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = rating.load_config()
    if args.check:
        return check(cfg)
    if not cfg["bot"].get("chat_peer_group") or not cfg["bot"].get("chat_peer_user"):
        print("Бот не настроен: в config.yaml не указаны номера беседы. Запустите проверку ключей.")
        rating.update(cfg, rating.web_getter())
        return 0
    bot = Bot(cfg, os.environ.get("VK_GROUP_TOKEN"), os.environ.get("VK_USER_TOKEN"),
              dry_run=args.dry_run or os.environ.get("BOT_DRY_RUN") == "1", rating=rating)
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
