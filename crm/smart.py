"""پیامک هوشمند فرصت ویژه: نام کوتاه فرش، امتیاز هر گیرنده و ارسال مرحله‌ای.

امتیاز از داده‌های خود سایت ساخته می‌شود (بدون سرویس بیرونی):
  خرید همان نقشه با سایز دیگر (ست)، همان نقشه در سبد/بازدید/سفارش ناتمام، کلیک روی پیامک‌های قبلی،
  همان رنگ زمینه، همان شانه، همان سایز، و فعالیت در ۹۰ روز اخیر. وزن هر نشانه در تنظیمات باشگاه است.
"""
import hashlib
import re
from collections import defaultdict

from django.utils import timezone

from core.templatetags.fa import fa_num, jdate

SMS_SINGLE, SMS_PART = 70, 67


def sms_parts(text):
    n = len(text or "")
    return 1 if n <= SMS_SINGLE else -(-n // SMS_PART)


def _norm(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace(" ", "")
    return s.strip(" -–،,").lower()


def _clean_color(c):
    return re.split(r"\s+[-–]\s+|،|,|\(", c or "")[0].strip()


def features(p):
    """(نقشه، رنگ، شانه) یک فرش، نرمال‌شده برای مقایسه."""
    from content.render import color_of, design_of

    from core.templatetags.fa import reeds_of

    return _norm(design_of(p)), _norm(_clean_color(color_of(p))), reeds_of(p.title or "")


def short_size(label):
    return re.sub(r"\s*\(.*\)\s*$", "", label or "").strip()


def offer_label(o):
    """«پارادایس سرمه‌ای ۷۰۰ شانه، ۹ متری مستطیل» به‌جای عنوان بلند فرش."""
    from content.render import color_of, design_of

    from core.templatetags.fa import reeds_of

    p = o.product
    design, color, reeds = design_of(p), _clean_color(color_of(p)), reeds_of(p.title or "")
    size = short_size(o.size.label if o.size_id else "")
    if not design:
        base = re.sub(r"^فرش\s+", "", p.title or "")[:45].strip()
        return fa_num(f"{base}، {size}" if size else base)
    parts = [design] + ([color] if color else []) + ([f"{reeds} شانه"] if reeds else [])
    return fa_num(" ".join(parts) + (f"، {size}" if size else ""))


def offer_left(o):
    if o.ends_at:
        return f"تا {jdate(o.ends_at, '%A %d %B')}"
    return f"فقط {fa_num(o.remaining)} تخته"


# ------------------------------------------------------------------ امتیاز گیرنده‌ها
def _users_of(mobiles):
    """{شناسهٔ کاربر: موبایل} برای این موبایل‌ها (از پروفایل یا نام کاربری)."""
    from django.contrib.auth import get_user_model

    from accounts.models import Profile

    mobiles = list(mobiles)
    out = {}
    for i in range(0, len(mobiles), 900):
        chunk = mobiles[i:i + 900]
        out.update(dict(Profile.objects.filter(mobile__in=chunk).values_list("user_id", "mobile")))
        out.update({pk: u for pk, u in get_user_model().objects.filter(username__in=chunk).values_list("pk", "username")
                    if pk not in out})
    return out


def signals(mobiles):
    """{موبایل: {"bought": [(product_id, size_id)], "interest": [(product_id, size_id)], "clicks": n, "last": datetime}}"""
    from accounts.utils import normalize_mobile
    from catalog.models import Variation
    from shop.coupons import PLACED
    from shop.models import OrderItem

    from .models import CartSnapshot, ProductView, ShortLink

    mobiles = set(mobiles)
    out = defaultdict(lambda: {"bought": [], "interest": [], "clicks": 0, "last": None})

    def touch(m, when):
        if when and (out[m]["last"] is None or when > out[m]["last"]):
            out[m]["last"] = when

    items = (OrderItem.objects.filter(order__mobile__in=mobiles).exclude(product_id=None)
             .values_list("order__mobile", "product_id", "variation__size_id", "order__status", "order__created_at"))
    for mob, pid, sid, status, at in items.iterator(chunk_size=2000):
        m = normalize_mobile(mob)
        if m not in mobiles:
            continue
        out[m]["bought" if status in PLACED else "interest"].append((pid, sid))
        touch(m, at)
    umap = _users_of(mobiles)
    views = list(ProductView.objects.filter(user_id__in=list(umap)).values_list("user_id", "product_id", "seen_at"))
    carts = list(CartSnapshot.objects.filter(user_id__in=list(umap)).values_list("user_id", "data", "updated_at"))
    for uid, pid, at in views:
        m = umap.get(uid)
        if m in mobiles:
            out[m]["interest"].append((pid, None))
            touch(m, at)
    vids = {int(v) for _, data, _ in carts for v in (data or {}) if str(v).isdigit()}
    vmap = {v.pk: (v.product_id, v.size_id) for v in Variation.objects.filter(pk__in=vids).only("product_id", "size_id")}
    for uid, data, at in carts:
        m = umap.get(uid)
        if m in mobiles:
            for v in data or {}:
                if str(v).isdigit() and int(v) in vmap:
                    out[m]["interest"].append(vmap[int(v)])
            touch(m, at)
    for m, n in ShortLink.objects.filter(campaign__isnull=False, clicks__gt=0, mobile__in=mobiles).values_list("mobile", "clicks"):
        out[m]["clicks"] += n
    return out


def score_all(offer, mobiles, settings_obj=None, now=None):
    """[(موبایل، امتیاز، دلیل‌ها، ست؟)] مرتب‌شده؛ بیشترین امتیاز اول."""
    from catalog.models import Product

    from .models import CrmSettings

    s = settings_obj or CrmSettings.load()
    now = now or timezone.now()
    sig = signals(mobiles)
    pids = {pid for x in sig.values() for pid, _ in x["bought"] + x["interest"]} | {offer.product_id}
    feats = {p.pk: features(p) for p in Product.objects.filter(pk__in=pids).prefetch_related("specs__attribute")}
    d0, c0, r0 = feats.get(offer.product_id, ("", "", ""))
    size0 = offer.size_id
    recent = now - timezone.timedelta(days=90)
    rows = []
    for m in mobiles:
        x = sig.get(m)
        score, why, is_set = 0, [], False
        if x:
            bought = [(feats.get(p, ("", "", "")), sid) for p, sid in x["bought"]]
            interest = [(feats.get(p, ("", "", "")), sid) for p, sid in x["interest"]]
            if d0 and any(f[0] == d0 and sid != size0 for f, sid in bought):
                score += s.w_set
                why.append("همین نقشه را با سایز دیگر خریده")
                is_set = True
            elif d0 and any(f[0] == d0 for f, _ in bought + interest):
                score += s.w_design
                why.append("به همین نقشه علاقه داشته")
            if x["clicks"]:
                score += s.w_click + min(x["clicks"] - 1, 2)
                why.append("روی پیامک‌های قبلی کلیک کرده")
            if c0 and any(f[1] == c0 for f, _ in bought + interest):
                score += s.w_color
                why.append("همین رنگ زمینه")
            if r0 and any(f[2] == r0 for f, _ in bought):
                score += s.w_reeds
                why.append(f"{fa_num(r0)} شانه خریده")
            if size0 and any(sid == size0 for _, sid in x["bought"] + x["interest"]):
                score += s.w_size
                why.append("همین سایز")
            if x["last"] and x["last"] >= recent:
                score += s.w_recent
                why.append("فعالیت اخیر")
        tie = hashlib.md5(f"{offer.pk}:{m}".encode()).hexdigest()
        rows.append((m, score, why, is_set, x["last"].timestamp() if x and x["last"] else 0, tie))
    rows.sort(key=lambda r: (-r[1], -r[4], r[5]))
    return [(m, sc, why, is_set) for m, sc, why, is_set, _, _ in rows]


def recently_messaged(days, exclude_campaign=None):
    from .models import SmsLog

    if not days:
        return set()
    qs = SmsLog.objects.filter(kind=SmsLog.Kind.CAMPAIGN, ok=True, created_at__gte=timezone.now() - timezone.timedelta(days=days))
    if exclude_campaign is not None:
        qs = qs.exclude(campaign=exclude_campaign)
    return set(qs.values_list("mobile", flat=True))


def plan(campaign, people=None, settings_obj=None):
    """رتبه‌بندی و اندازهٔ مرحله‌ها (برای پیش‌نمایش و شروع ارسال)."""
    from .campaigns import recipients
    from .models import CrmSettings

    s = settings_obj or CrmSettings.load()
    people = people if people is not None else recipients(campaign)
    capped = recently_messaged(s.freq_cap_days, exclude_campaign=campaign)
    eligible = [c["mobile"] for c in people if c["mobile"] not in capped]
    ranked = score_all(campaign.offer, eligible, s)
    rem = max(campaign.offer.remaining, 1)
    sizes = []
    first = min(len(ranked), s.wave1_per_piece * rem) if s.wave1_per_piece else len(ranked)
    sizes.append(first)
    if s.wave2_per_piece and first < len(ranked):
        sizes.append(min(len(ranked) - first, s.wave2_per_piece * rem))
    if s.wave_last_all and sum(sizes) < len(ranked):
        sizes.append(len(ranked) - sum(sizes))
    return {"ranked": ranked, "capped": len(people) - len(eligible), "total": len(people), "waves": sizes,
            "remaining": rem, "gap": s.wave_gap_hours}


def quota_for(wave, campaign, total, s):
    """تا چندمین نفر فهرست در مرحلهٔ wave فرستاده شود (تجمعی)."""
    rem = max(campaign.offer.remaining, 1) if campaign.offer_id else 1
    if wave <= 1:
        return min(total, s.wave1_per_piece * rem) if s.wave1_per_piece else total
    if wave == 2 and s.wave2_per_piece:
        return min(total, campaign.wave_quota + s.wave2_per_piece * rem)
    return total if s.wave_last_all else campaign.wave_quota


def has_next_wave(campaign, total, s):
    nxt = quota_for(campaign.wave + 1, campaign, total, s)
    return nxt > campaign.wave_quota
