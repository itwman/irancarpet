"""یک unserialize ساده و امن برای داده‌های سریالایز‌شدهٔ PHP (متای وردپرس)."""


class PHPUnserializeError(ValueError):
    pass


def php_unserialize(data, default=None):
    """رشتهٔ سریالایز PHP را به dict/list/str/int/... تبدیل می‌کند.

    آرایه‌ها به dict برگردانده می‌شوند. در صورت خطا default برمی‌گردد.
    """
    if data is None:
        return default
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = bytes(data)
    if not raw or raw[:2] not in (b"a:", b"s:", b"i:", b"d:", b"b:", b"N;", b"O:"):
        return default
    try:
        value, _ = _parse(raw, 0)
        return value
    except (PHPUnserializeError, IndexError, ValueError):
        return default


def _read_until(raw, pos, ch):
    end = raw.index(ch, pos)
    return raw[pos:end], end + 1


def _parse(raw, pos):
    t = raw[pos:pos + 1]
    if t == b"N":
        return None, pos + 2
    if t in (b"i", b"d", b"b"):
        val, pos = _read_until(raw, pos + 2, b";")
        if t == b"i":
            return int(val), pos
        if t == b"d":
            return float(val), pos
        return val == b"1", pos
    if t == b"s":
        length, pos = _read_until(raw, pos + 2, b":")
        length = int(length)
        start = pos + 1  # skip opening quote
        val = raw[start:start + length]
        return val.decode("utf-8", errors="replace"), start + length + 2  # skip `";`
    if t == b"a":
        count, pos = _read_until(raw, pos + 2, b":")
        pos += 1  # skip {
        result = {}
        for _ in range(int(count)):
            k, pos = _parse(raw, pos)
            v, pos = _parse(raw, pos)
            result[k] = v
        return result, pos + 1  # skip }
    if t == b"O":
        _, pos = _read_until(raw, pos + 2, b":")  # class name length
        _, pos = _read_until(raw, pos, b":")  # class name
        count, pos = _read_until(raw, pos, b":")
        pos += 1
        result = {}
        for _ in range(int(count)):
            k, pos = _parse(raw, pos)
            v, pos = _parse(raw, pos)
            result[k] = v
        return result, pos + 1
    raise PHPUnserializeError(f"unknown type {t!r} at {pos}")


def as_list(value):
    """آرایهٔ PHP (dict با کلید عددی) را به لیست مقادیر تبدیل می‌کند."""
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]
