def cart(request):
    data = request.session.get("cart") or {}
    return {"cart_count": sum(int(v) for v in data.values())}
