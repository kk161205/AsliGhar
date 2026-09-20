def inr(amount: int) -> str:
    """Rupees with Indian digit grouping: ₹12,34,567 (last three digits, then pairs)."""
    digits = str(amount)
    if len(digits) <= 3:
        return f"₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    pairs.insert(0, head)
    return "₹" + ",".join([*pairs, tail])
