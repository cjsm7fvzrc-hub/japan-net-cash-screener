from __future__ import annotations

import math


def _number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _add(reasons: list[str], points: int, reason: str) -> int:
    reasons.append(reason)
    return points


def evaluate_tenbagger(row: dict) -> dict:
    """Candidate-discovery score. It ranks research priority, not future returns."""
    score = 0
    reasons: list[str] = []
    risks: list[str] = []
    cap = _number(row.get("market_cap"))
    revenue_cagr = _number(row.get("revenue_cagr_3y"))
    operating_cagr = _number(row.get("operating_income_cagr_3y"))
    quarterly_growth = _number(row.get("quarterly_revenue_growth"))
    margin = _number(row.get("operating_margin"))
    margin_change = _number(row.get("operating_margin_change"))
    ratio = _number(row.get("net_cash_ratio"))
    per = _number(row.get("per"))
    pbr = _number(row.get("pbr"))
    ocf = _number(row.get("operating_cash_flow"))
    profit = _number(row.get("net_income"))
    high_distance = _number(row.get("distance_from_52w_high"))
    return_52w = _number(row.get("return_52w"))
    volume_ratio = _number(row.get("volume_ratio_20d"))

    if cap is not None:
        if 2_000_000_000 <= cap < 10_000_000_000:
            score += _add(reasons, 20, "時価総額100億円未満で成長余地が大きい")
        elif cap < 30_000_000_000:
            score += _add(reasons, 16, "時価総額300億円未満")
        elif cap < 50_000_000_000:
            score += _add(reasons, 11, "時価総額500億円未満")
        elif cap < 100_000_000_000:
            score += 5

    if revenue_cagr is not None:
        if revenue_cagr >= 0.20:
            score += _add(reasons, 15, "売上高3年CAGRが20%以上")
        elif revenue_cagr >= 0.10:
            score += _add(reasons, 10, "売上高3年CAGRが10%以上")
        elif revenue_cagr > 0:
            score += 4
        else:
            risks.append("3年間の売上高が縮小")
    if operating_cagr is not None:
        if operating_cagr >= 0.25:
            score += _add(reasons, 12, "営業利益3年CAGRが25%以上")
        elif operating_cagr >= 0.10:
            score += _add(reasons, 7, "営業利益が継続成長")
    if quarterly_growth is not None:
        if quarterly_growth >= 0.20:
            score += _add(reasons, 10, "直近四半期売上が前年同期比20%以上")
        elif quarterly_growth >= 0.10:
            score += 6
        elif quarterly_growth < 0:
            risks.append("直近四半期売上が前年同期比で減少")

    if margin is not None and margin >= 0.10:
        score += _add(reasons, 6, "営業利益率10%以上")
    if margin_change is not None:
        if margin_change >= 0.02:
            score += _add(reasons, 9, "営業利益率が2ポイント以上改善")
        elif margin_change <= -0.02:
            risks.append("営業利益率が2ポイント以上悪化")

    if ratio is not None:
        if ratio >= 1:
            score += _add(reasons, 12, "ネットキャッシュが時価総額以上")
        elif ratio >= 0.3:
            score += _add(reasons, 7, "ネットキャッシュによる安全余裕")
        elif ratio < 0:
            risks.append("ネットキャッシュがマイナス")
    if ocf is not None and ocf > 0:
        score += 5
    elif ocf is not None:
        score -= 8
        risks.append("営業キャッシュフローが赤字")
    if profit is not None and profit <= 0:
        score -= 8
        risks.append("最終利益が赤字")

    if per is not None and 0 < per <= 15:
        score += _add(reasons, 6, "PER15倍以下")
    if pbr is not None and 0 < pbr <= 1:
        score += 3
    if high_distance is not None and high_distance >= -0.15:
        score += _add(reasons, 5, "52週高値から15%以内")
    if return_52w is not None and return_52w > 0:
        score += 3
    if volume_ratio is not None and volume_ratio >= 1.5:
        score += _add(reasons, 4, "直近出来高が20日平均の1.5倍以上")

    asset = ratio is not None and ratio >= 1 and per is not None and 0 < per <= 10
    growth = ((revenue_cagr or 0) >= 0.10 or (quarterly_growth or 0) >= 0.15) and (margin_change or 0) >= 0
    transform = ((quarterly_growth or 0) >= 0.20 and (margin_change or 0) >= 0.02) or (
        operating_cagr is not None and operating_cagr >= 0.40
    )
    if transform:
        candidate_type = "変身型"
    elif growth:
        candidate_type = "成長初動型"
    elif asset:
        candidate_type = "清原型"
    else:
        candidate_type = "継続観察"

    score = max(0, min(100, round(score)))
    if score >= 75:
        verdict = "最優先で精査"
    elif score >= 60:
        verdict = "有力調査候補"
    elif score >= 45:
        verdict = "継続観察"
    else:
        verdict = "現時点では優先度低"
    return {
        "tenbagger_score": score,
        "tenbagger_type": candidate_type,
        "tenbagger_verdict": verdict,
        "tenbagger_reasons": reasons[:6],
        "tenbagger_risks": risks[:5],
    }
