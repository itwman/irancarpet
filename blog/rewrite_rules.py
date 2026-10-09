"""قاعده‌های بازنویسی مقاله‌ها — بدون وابستگی به جنگو تا نویسنده (کار زمان‌بندی‌شده) هم بتواند اجرا کند:

    python3 blog/rewrite_rules.py content/rewrites/posts/0001.json

خروجی: خطاها (مانع انتشار) و هشدارها. سایت هنگام دریافت فایل همین بررسی را تکرار می‌کند.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

SITE = "irancarpet.net"
PHONE = "09125347596"
ALLOWED_PHONES = {PHONE, "03155340038"}
BANNED = ("شهر فرش", "آقای فرش", "مهد فرش", "فرش وزرا", "وزرا فرش")
SHORTCODES = {"installment_calc", "installment_prices", "installment_plans", "installment_steps", "installment_faq",
              "price_updated", "size_prices", "size_faq", "shipping_info", "city_faq", "reeds_compare", "price_table",
              "city_notice", "reeds_links", "contact_info", "contact_form"}
BLOCK_TAGS = ("div", "section", "table", "ul", "ol", "details", "blockquote", "figure", "p")
FORBIDDEN_TAGS = ("script", "style", "iframe", "form", "input", "h1", "object", "embed")
LIMITS = {"title": (10, 80), "seo_title": (20, 70), "seo_description": (90, 170), "excerpt": (40, 400)}
MIN_WORDS = {"city": 700, "price": 600, "installment": 600, "guide": 700}


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.links, self.imgs, self.text, self.h2 = [], [], [], [], [], 0
        self.faq_q = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in FORBIDDEN_TAGS:
            self.errors.append(f"تگ <{tag}> مجاز نیست")
        if tag in BLOCK_TAGS:
            self.stack.append(tag)
        if tag == "a":
            self.links.append(a.get("href") or "")
        if tag == "img":
            self.imgs.append(a)
        if tag == "h2":
            self.h2 += 1
        if tag == "summary":
            self.faq_q += 1

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            if tag in self.stack:
                while self.stack:
                    t = self.stack.pop()
                    if t == tag:
                        break
                    if t != "p":
                        self.errors.append(f"<{t}> بسته نشده است")
            elif tag != "p":
                self.errors.append(f"</{tag}> اضافه است")

    def handle_data(self, data):
        self.text.append(data)


def words(html):
    return len(re.sub(r"<[^>]+>", " ", html or "").split())


def check(data, known_urls=None, kind=""):
    """(خطاها، هشدارها)"""
    errors, warns = [], []
    if not isinstance(data, dict):
        return ["فایل باید یک شیء JSON باشد"], []
    if not (data.get("slug") or "").strip():
        errors.append("slug خالی است")
    if data.get("action") == "skip":
        if not (data.get("skip_reason") or "").strip():
            errors.append("برای skip دلیل (skip_reason) لازم است")
        return errors, warns
    for f, (lo, hi) in LIMITS.items():
        v = (data.get(f) or "").strip()
        if not v:
            errors.append(f"{f} خالی است")
        elif not lo <= len(v) <= hi:
            (errors if len(v) > hi + 20 or len(v) < lo // 2 else warns).append(f"طول {f} {len(v)} حرف است (بهتر: {lo} تا {hi})")
    content = data.get("content") or ""
    if not content.strip():
        errors.append("content خالی است")
        return errors, warns
    all_text = " ".join(str(data.get(k) or "") for k in ("title", "seo_title", "seo_description", "excerpt", "content"))
    for b in BANNED:
        if b in all_text:
            errors.append(f"نام فروشگاه دیگر («{b}») نباید بیاید")
    latin = re.sub(r"[۰-۹]", lambda x: str("۰۱۲۳۴۵۶۷۸۹".index(x.group())), re.sub(r"<[^>]+>", " ", all_text))
    for m in set(re.findall(r"(?<!\d)(?:\+98|0098|0)?9\d{9}(?!\d)", latin)):
        if "0" + m[-10:] not in ALLOWED_PHONES:
            errors.append(f"شمارهٔ موبایل {m} مجاز نیست؛ فقط {PHONE}")
    for m in set(re.findall(r"(?<!\d)0[1-8]\d[\s-]?\d{8}(?!\d)", latin)):
        if re.sub(r"\D", "", m) not in ALLOWED_PHONES:
            warns.append(f"شمارهٔ تلفن {m} — مطمئن شوید شمارهٔ ایران کارپت است")
    for sc in re.findall(r"\[([a-z_]+)[^\]]*\]", content):
        if sc not in SHORTCODES:
            errors.append(f"بلوک ناشناخته [{sc}]")
    p = _Tags()
    try:
        p.feed(content)
        p.close()
    except Exception as e:  # noqa: BLE001
        errors.append(f"HTML خراب است: {e}")
    errors += p.errors
    for t in p.stack:
        if t != "p":
            errors.append(f"<{t}> بسته نشده است")
    if p.h2 < 3:
        warns.append("کمتر از ۳ تیتر h2 دارد")
    n = words(content)
    need = MIN_WORDS.get(kind or data.get("kind") or "guide", 700)
    if n < need * 0.6:
        errors.append(f"متن خیلی کوتاه است ({n} کلمه؛ کمینه {need})")
    elif n < need:
        warns.append(f"متن کوتاه است ({n} کلمه؛ بهتر از {need} بیشتر)")
    internal = 0
    for href in p.links:
        h = href.strip()
        if not h or h.startswith("#") or h.startswith("tel:"):
            continue
        u = urlsplit(h)
        if u.netloc and u.netloc.replace("www.", "") != SITE:
            warns.append(f"پیوند بیرونی: {h[:80]}")
            continue
        internal += 1
        path = unquote(u.path or "/")
        if not path.endswith("/"):
            path += "/"
        if known_urls is not None and path not in known_urls:
            errors.append(f"پیوند داخلی ناموجود: {path}")
        if data.get("slug") and path.strip("/") == data["slug"].strip("/"):
            errors.append("مقاله نباید به خودش پیوند بدهد")
    if internal < 3:
        warns.append(f"فقط {internal} پیوند داخلی دارد (بهتر ۳ تا ۸)")
    for im in p.imgs:
        src = im.get("src") or ""
        if src and not (src.startswith("/") or urlsplit(src).netloc.replace("www.", "") == SITE):
            errors.append(f"تصویر از سایت دیگر: {src[:80]}")
        if not (im.get("alt") or "").strip():
            warns.append("تصویر بدون alt")
    kw = (data.get("focus_keyword") or "").strip()
    if not kw:
        warns.append("focus_keyword خالی است")
    elif kw not in (data.get("title") or "") and kw not in (data.get("seo_title") or ""):
        warns.append("کلمهٔ کلیدی در عنوان نیست")
    if p.faq_q and p.faq_q < 3:
        warns.append("پرسش‌های رایج کمتر از ۳ پرسش دارد")
    return errors, warns


def known_urls_from(path):
    if not os.path.exists(path):
        return None
    out = set()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            p = unquote(urlsplit(line).path or "/")
            out.add(p if p.endswith("/") else p + "/")
    return out


def main(argv):
    base = os.path.dirname(os.path.abspath(argv[0]))
    urls = known_urls_from(os.path.join(base, "..", "content", "rewrites", "urls.txt"))
    plan = {}
    plan_file = os.path.join(base, "..", "content", "rewrites", "plan.json")
    if os.path.exists(plan_file):
        plan = {p["slug"]: p for p in json.load(open(plan_file, encoding="utf-8"))}
    bad = 0
    for f in argv[1:]:
        data = json.load(open(f, encoding="utf-8"))
        kind = plan.get(data.get("slug"), {}).get("kind", "")
        errors, warns = check(data, urls, kind)
        print(f"== {f}: {words(data.get('content'))} کلمه")
        for e in errors:
            print("  خطا:", e)
        for w in warns:
            print("  هشدار:", w)
        bad += bool(errors)
        if not errors:
            print("  درست است.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
