"""Минимальный клиент API ВКонтакте.

Два ключа:
  group - ключ сообщества (сообщения в беседу и в личные, чтение ответов);
  user  - ключ технического аккаунта (опросы, чтение стены лиги).
В режиме dry_run методы, которые что-то публикуют или отправляют, не вызываются,
а печатаются в журнал.
"""
import json
import random
import time

import requests

API = "https://api.vk.com/method/"
VERSION = "5.199"
WRITE_METHODS = {"messages.send", "polls.create", "polls.edit"}


class VKError(Exception):
    def __init__(self, method, code, msg):
        super().__init__(f"{method}: ошибка {code}: {msg}")
        self.code = code


class VK:
    def __init__(self, token, name, dry_run=False):
        self.token = token
        self.name = name
        self.dry_run = dry_run
        self.session = requests.Session()

    def call(self, method, **params):
        if self.dry_run and method in WRITE_METHODS:
            print(f"[пробный режим] {self.name}.{method} {json.dumps(params, ensure_ascii=False)[:500]}")
            return {"id": 0, "owner_id": 0} if method == "polls.create" else 0
        if not self.token:
            raise VKError(method, 0, f"не задан ключ {self.name}")
        clean = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                 for k, v in params.items() if v is not None}
        clean.update(access_token=self.token, v=VERSION)
        for attempt in range(3):
            resp = self.session.post(API + method, data=clean, timeout=30).json()
            err = resp.get("error")
            if err and err.get("error_code") == 6:  # слишком много запросов в секунду
                time.sleep(1 + attempt)
                continue
            if err:
                raise VKError(method, err.get("error_code"), err.get("error_msg"))
            time.sleep(0.35)
            return resp["response"]
        raise VKError(method, 6, "слишком много запросов")

    def send(self, peer_id, text, attachment=None):
        return self.call("messages.send", peer_id=peer_id, message=text, attachment=attachment,
                         random_id=random.randint(1, 2**31 - 1), disable_mentions=1)
