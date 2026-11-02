def cart(request):
    session = getattr(request, "session", None)   # خطای پیش از میان‌افزار نشست: صفحهٔ خطا هم باید باز شود
    data = (session.get("cart") if session is not None else None) or {}
    return {"cart_count": sum(int(v) for v in data.values())}
