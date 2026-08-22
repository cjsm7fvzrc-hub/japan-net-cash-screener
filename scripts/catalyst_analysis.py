from __future__ import annotations

import math


def _number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _add(items: list[str], points: int, label: str) -> int:
    items.append(label)
    return points


def evaluate_catalysts(row: dict) -> dict:
    """Rank observable change signals; do not assert an official forecast revision."""
    score = 0
    signals: list[str] = []
    checks: list[str] = []

    revenue_yoy = _number(row.get("quarterly_revenue_growth"))
    revenue_cagr = _number(row.get("revenue_cagr_3y"))
    operating_yoy = _number(row.get("quarterly_operating_income_growth"))
    operating_cagr = _number(row.get("operating_income_cagr_3y"))
    margin_change = _number(row.get("operating_margin_change"))
    forward_eps_growth = _number(row.get("forward_eps_growth"))
    earnings_growth = _number(row.get("earnings_growth"))
    volume_ratio = _number(row.get("volume_ratio_20d"))
    return_52w = _number(row.get("return_52w"))
    net_cash_ratio = _number(row.get("net_cash_ratio"))
    operating_profit_turnaround = bool(row.get("operating_profit_turnaround"))

    revenue_acceleration = (
        revenue_yoy - revenue_cagr
        if revenue_yoy is not None and revenue_cagr is not None
        else None
    )
    operating_acceleration = (
        operating_yoy - operating_cagr
        if operating_yoy is not None and operating_cagr is not None
        else None
    )

    if revenue_yoy is not None:
        if revenue_yoy >= 0.20:
            score += _add(signals, 16, "直近四半期売上が前年同期比20%以上")
        elif revenue_yoy >= 0.10:
            score += _add(signals, 10, "直近四半期売上が前年同期比10%以上")
        elif revenue_yoy < 0:
            checks.append("直近四半期売上が前年同期比で減少")

    if operating_profit_turnaround:
        score += _add(signals, 20, "直近四半期の営業利益が黒字転換")
    elif operating_yoy is not None:
        if operating_yoy >= 0.30:
            score += _add(signals, 18, "直近四半期営業利益が前年同期比30%以上")
        elif operating_yoy >= 0.10:
            score += _add(signals, 11, "直近四半期営業利益が前年同期比10%以上")
        elif operating_yoy < 0:
            checks.append("直近四半期営業利益が前年同期比で減少")

    if revenue_acceleration is not None and revenue_acceleration >= 0.05:
        score += _add(signals, 10, "足元の売上成長が3年平均を5ポイント以上上回る")
    if operating_acceleration is not None and operating_acceleration >= 0.10:
        score += _add(signals, 12, "足元の利益成長が3年平均を10ポイント以上上回る")

    if margin_change is not None:
        if margin_change >= 0.03:
            score += _add(signals, 14, "営業利益率が3ポイント以上改善")
        elif margin_change >= 0.01:
            score += _add(signals, 8, "営業利益率が改善")
        elif margin_change <= -0.03:
            checks.append("営業利益率が3ポイント以上悪化")

    forecast_signal = forward_eps_growth if forward_eps_growth is not None else earnings_growth
    if forecast_signal is not None:
        if forecast_signal >= 0.25:
            score += _add(signals, 16, "予想EPSまたは利益成長率が25%以上")
        elif forecast_signal >= 0.10:
            score += _add(signals, 10, "予想EPSまたは利益成長率が10%以上")
        elif forecast_signal < 0:
            checks.append("予想EPSまたは利益成長率がマイナス")
    else:
        checks.append("予想値データが未取得")

    if volume_ratio is not None and volume_ratio >= 1.5:
        score += _add(signals, 8, "出来高が20日平均の1.5倍以上")
    if return_52w is not None and return_52w > 0:
        score += 4
    if net_cash_ratio is not None and net_cash_ratio >= 0.3:
        score += 4

    score = max(0, min(100, round(score)))
    if score >= 70:
        revision_signal = "上方修正兆候・強"
    elif score >= 50:
        revision_signal = "上方修正兆候あり"
    elif score >= 30:
        revision_signal = "変化を継続確認"
    else:
        revision_signal = "明確な兆候なし"

    if operating_profit_turnaround:
        transformation_signal = "営業黒字へ転換"
    elif (operating_yoy or 0) >= 0.30 and (margin_change or 0) >= 0.02:
        transformation_signal = "利益構造が変化"
    elif (revenue_yoy or 0) >= 0.20 and (operating_yoy or 0) >= 0.20:
        transformation_signal = "高成長が顕在化"
    elif (revenue_acceleration or 0) >= 0.05 or (operating_acceleration or 0) >= 0.10:
        transformation_signal = "成長が加速"
    else:
        transformation_signal = "変化を観察"

    return {
        "catalyst_score": score,
        "revision_signal": revision_signal,
        "transformation_signal": transformation_signal,
        "revenue_acceleration": revenue_acceleration,
        "operating_income_acceleration": operating_acceleration,
        "catalyst_signals": signals[:6],
        "catalyst_checks": checks[:5],
    }
