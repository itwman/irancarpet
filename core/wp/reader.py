"""خواندن مستقیم از دیتابیس وردپرس (فقط SELECT)."""
from collections import defaultdict
from datetime import datetime, timezone as dt_tz
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from django.db import connections

from core.utils.php import as_list, php_unserialize

TEHRAN = ZoneInfo("Asia/Tehran")


def chunks(seq, size=2000):
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def slug(value):
    return unquote(value or "").strip()


def wp_datetime(gmt, local=None):
    """تاریخ وردپرس را به datetime آگاه از منطقهٔ زمانی تبدیل می‌کند."""
    for value, tz in ((gmt, dt_tz.utc), (local, TEHRAN)):
        if not value:
            continue
        if isinstance(value, str):
            if value.startswith("0000"):
                continue
            value = datetime.fromisoformat(value)
        if value.year < 1971:
            continue
        return value.replace(tzinfo=tz)
    return datetime(2017, 1, 1, tzinfo=dt_tz.utc)


def robots_from_meta(value):
    items = [str(x) for x in as_list(php_unserialize(value, default=[]))]
    flags = [x for x in items if x in ("noindex", "nofollow", "noarchive", "noimageindex", "nosnippet")]
    return ",".join(flags)


class WPReader:
    def __init__(self, alias="wp", prefix="wp_"):
        self.conn = connections[alias]
        self.p = prefix

    def t(self, name):
        return f"{self.p}{name}"

    def rows(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql.replace("{p}", self.p), params or [])
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def option(self, name, default=None):
        r = self.rows("SELECT option_value FROM {p}options WHERE option_name=%s", [name])
        return r[0]["option_value"] if r else default

    def posts(self, post_type, statuses=("publish",), extra=""):
        ph = ",".join(["%s"] * len(statuses))
        return self.rows(
            f"SELECT * FROM {{p}}posts WHERE post_type=%s AND post_status IN ({ph}) {extra} ORDER BY ID",
            [post_type, *statuses],
        )

    def postmeta(self, ids, keys=None):
        """{post_id: {meta_key: meta_value}} — اگر کلید تکراری بود، اولی نگه داشته می‌شود."""
        out = defaultdict(dict)
        for part in chunks(ids):
            ph = ",".join(["%s"] * len(part))
            sql = f"SELECT post_id, meta_key, meta_value FROM {{p}}postmeta WHERE post_id IN ({ph})"
            params = list(part)
            if keys:
                sql += f" AND meta_key IN ({','.join(['%s'] * len(keys))})"
                params += list(keys)
            sql += " ORDER BY meta_id"
            for r in self.rows(sql, params):
                out[r["post_id"]].setdefault(r["meta_key"], r["meta_value"])
        return out

    def postmeta_all(self, ids, key):
        """همهٔ مقادیر یک کلید (مثلاً _wp_old_slug که چندتایی است)."""
        out = defaultdict(list)
        for part in chunks(ids):
            ph = ",".join(["%s"] * len(part))
            for r in self.rows(
                f"SELECT post_id, meta_value FROM {{p}}postmeta WHERE meta_key=%s AND post_id IN ({ph})",
                [key, *part],
            ):
                out[r["post_id"]].append(r["meta_value"])
        return out

    def terms(self, taxonomy):
        return self.rows(
            "SELECT t.term_id, t.name, t.slug, tt.term_taxonomy_id, tt.parent, tt.description, tt.count "
            "FROM {p}terms t JOIN {p}term_taxonomy tt ON tt.term_id=t.term_id WHERE tt.taxonomy=%s ORDER BY t.term_id",
            [taxonomy],
        )

    def termmeta(self, term_ids):
        out = defaultdict(dict)
        for part in chunks(term_ids):
            if not part:
                continue
            ph = ",".join(["%s"] * len(part))
            for r in self.rows(
                f"SELECT term_id, meta_key, meta_value FROM {{p}}termmeta WHERE term_id IN ({ph})", list(part)
            ):
                out[r["term_id"]].setdefault(r["meta_key"], r["meta_value"])
        return out

    def object_terms(self, object_ids, taxonomies):
        """{object_id: {taxonomy: [term_id,...]}}"""
        out = defaultdict(lambda: defaultdict(list))
        tph = ",".join(["%s"] * len(taxonomies))
        for part in chunks(object_ids):
            ph = ",".join(["%s"] * len(part))
            for r in self.rows(
                "SELECT r.object_id, tt.taxonomy, tt.term_id FROM {p}term_relationships r "
                "JOIN {p}term_taxonomy tt ON tt.term_taxonomy_id=r.term_taxonomy_id "
                f"WHERE r.object_id IN ({ph}) AND tt.taxonomy IN ({tph}) ORDER BY r.term_order",
                [*part, *taxonomies],
            ):
                out[r["object_id"]][r["taxonomy"]].append(r["term_id"])
        return out
