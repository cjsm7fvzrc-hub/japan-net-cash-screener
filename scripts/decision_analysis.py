from __future__ import annotations

import math


def _number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def evaluate_decision(row: dict) -> dict:
    """Combine opportunity, catalyst, downside risk and data coverage."""
    risks: list[str] = []
    protections: list[str] = []
    risk_score = 0

    revenue_growth = _number(row.get("quarterly_revenue_growth"))
    operating_growth = _number(row.get("quarterly_operating_income_growth"))
    margin_change = _number(row.get("operating_margin_change"))
    ocf = _number(row.get("operating_cash_flow"))
    profit = _number(row.get("net_income"))
    current_assets = _number(row.get("current_assets"))
    liabilities = _number(row.get("liabilities"))
    net_cash_ratio = _number(row.get("net_cash_ratio"))
    per = _number(row.get("per"))
    pbr = _number(row.get("pbr"))
    market_cap = _number(row.get("market_cap"))

    if ocf is not None and ocf <= 0:
        risk_score += 22
        risks.append("営業キャッシュフローが赤字")
    elif ocf is not None and profit is not None and profit > 0 and ocf / profit < 0.7:
        risk_score += 12
        risks.append("利益に対して営業キャッシュフローが弱い")
    elif ocf is not None and ocf > 0:
        protections.append("営業キャッシュフローが黒字")

    if current_assets is not None and liabilities is not None:
        if current_assets <= liabilities:
            risk_score += 18
            risks.append("流動資産が負債を下回る")
        else:
            protections.append("流動資産が負債を上回る")
    if net_cash_ratio is not None:
        if net_cash_ratio < 0:
            risk_score += 18
            risks.append("ネットキャッシュがマイナス")
        elif net_cash_ratio >= 0.5:
            protections.append("ネットキャッシュの安全余裕")
    if revenue_growth is not None and revenue_growth < -0.10:
        risk_score += 15
        risks.append("四半期売上が10%以上減少")
    if operating_growth is not None and operating_growth < 0:
        risk_score += 15
        risks.append("四半期営業利益が減少または赤字化")
    if margin_change is not None and margin_change <= -0.03:
        risk_score += 12
        risks.append("営業利益率が3ポイント以上悪化")
    if per is not None and per > 35:
        risk_score += 8
        risks.append("PERが35倍超")
    if pbr is not None and pbr > 5:
        risk_score += 5
        risks.append("PBRが5倍超")
    if market_cap is not None and market_cap < 2_000_000_000:
        risk_score += 8
        risks.append("時価総額20億円未満で流動性に注意")

    coverage_fields = (
        "market_cap", "per", "pbr", "net_cash_ratio", "operating_cash_flow",
        "net_income", "revenue_cagr_3y", "quarterly_revenue_growth",
        "quarterly_operating_income_growth", "operating_margin_change",
        "forward_eps_growth", "volume_ratio_20d",
    )
    available = sum(_number(row.get(field)) is not None for field in coverage_fields)
    data_quality_score = round(available / len(coverage_fields) * 100)
    if row.get("error"):
        data_quality_score = max(0, data_quality_score - 20)
        risks.append("直近取得でエラーあり")

    risk_score = max(0, min(100, round(risk_score)))
    risk_level = "高" if risk_score >= 55 else "中" if risk_score >= 30 else "低"
    tenbagger = _number(row.get("tenbagger_score")) or 0
    catalyst = _number(row.get("catalyst_score")) or 0
    raw_score = tenbagger * 0.55 + catalyst * 0.30 + (100 - risk_score) * 0.15
    coverage_factor = 0.75 + data_quality_score / 400
    investment_score = max(0, min(100, round(raw_score * coverage_factor)))

    if data_quality_score < 40:
        decision = "データ補完を優先"
    elif investment_score >= 70 and risk_score < 45:
        decision = "重点調査候補"
    elif investment_score >= 55:
        decision = "有力候補"
    elif investment_score >= 40:
        decision = "継続監視"
    else:
        decision = "優先度低"

    base_eps = _number(row.get("forward_eps")) or _number(row.get("trailing_eps"))
    expected_growth = (
        _number(row.get("forward_eps_growth"))
        or _number(row.get("revenue_cagr_3y"))
        or 0.05
    )
    expected_growth = max(-0.20, min(0.40, expected_growth))
    target_per = 12 if expected_growth < 0.08 else 15 if expected_growth < 0.15 else 20

    return {
        "investment_score": investment_score,
        "investment_decision": decision,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_reasons": risks[:6],
        "risk_protections": protections[:5],
        "data_quality_score": data_quality_score,
        "scenario_base_eps": base_eps,
        "scenario_growth_default": expected_growth,
        "scenario_per_default": target_per,
    }
