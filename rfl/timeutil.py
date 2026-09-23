"""Время команды: Самара, UTC+4 (время на афишах лиги и в протоколах)."""
import datetime as dt

TZ = dt.timezone(dt.timedelta(hours=4), "Самара")


def now_local():
    return dt.datetime.now(TZ)
