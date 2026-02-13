def size_order(quote_budget: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return quote_budget / price
