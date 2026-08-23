from __future__ import annotations


def eligible_market(market: object) -> bool:
    """Return False for professional-investor-only TOKYO PRO Market rows."""
    normalized = " ".join(str(market or "").upper().split())
    return "PRO MARKET" not in normalized
