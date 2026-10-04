import re

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def latin_digits(s):
    return str(s or "").translate(FA)


def normalize_mobile(value):
    """هر شکلی از شمارهٔ موبایل ایران ← 09xxxxxxxxx ؛ نامعتبر ← ''"""
    d = re.sub(r"\D", "", latin_digits(value))
    if d.startswith("0098"):
        d = d[4:]
    elif d.startswith("98") and len(d) == 12:
        d = d[2:]
    if len(d) == 10 and d.startswith("9"):
        d = "0" + d
    return d if re.fullmatch(r"09\d{9}", d) else ""
