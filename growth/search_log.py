"""ثبت جستجوها (بی‌آنکه سرعت جستجو کم شود)."""
import re

from django.db.models import F
from django.utils import timezone

FA = str.maketrans({**{c: str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}, "ي": "ی", "ك": "ک", "‌": " "})


def norm(q):
    q = (q or "").translate(FA)
    return re.sub(r"\s+", " ", q).strip().lower()[:200]


def log(query, source, results):
    q = norm(query)
    if len(q) < 2:
        return
    from .models import SearchLog

    try:
        n = SearchLog.objects.filter(query=q, source=source).update(hits=F("hits") + 1, results=results, last_seen=timezone.now())
        if not n:
            SearchLog.objects.create(query=q, source=source, results=results)
    except Exception:  # noqa: BLE001  — هم‌زمانی؛ ثبت جستجو مهم‌تر از خطا نیست
        pass
