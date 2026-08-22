from __future__ import annotations

import math
import statistics


def _finite(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def evaluate_prices(values: list) -> dict:
    closes = [x for value in values if (x := _finite(value)) is not None]
    if not closes:
        return {}

    def average(period: int):
        return sum(closes[-period:]) / period if len(closes) >= period else None

    ma20, ma50, ma200 = average(20), average(50), average(200)
    rsi14 = None
    if len(closes) >= 15:
        changes = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
        gains = sum(max(change, 0) for change in changes) / 14
        losses = sum(max(-change, 0) for change in changes) / 14
        rsi14 = 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)

    returns = [closes[i] / closes[i - 1] - 1 for i in range(max(1, len(closes) - 60), len(closes)) if closes[i - 1]]
    volatility = statistics.stdev(returns) * math.sqrt(252) if len(returns) >= 2 else None
    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        max_drawdown = min(max_drawdown, close / peak - 1)

    return summarize_technicals({
        "price": closes[-1], "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "rsi14": rsi14, "volatility_60d": volatility,
        "max_drawdown_1y": max_drawdown,
    })


def summarize_technicals(row: dict) -> dict:
    price = _finite(row.get("price"))
    ma20 = _finite(row.get("ma20"))
    ma50 = _finite(row.get("ma50"))
    ma200 = _finite(row.get("ma200"))
    rsi = _finite(row.get("rsi14"))
    volatility = _finite(row.get("volatility_60d"))
    drawdown = _finite(row.get("max_drawdown_1y"))
    if all(value is None for value in (price, ma20, ma50, ma200, rsi, volatility, drawdown)):
        return {
            "technical_score": None, "technical_trend": "未取得",
            "technical_signals": [], "technical_cautions": ["チャートデータが未取得"],
            "ma20": None, "ma50": None, "ma200": None, "rsi14": None,
            "volatility_60d": None, "max_drawdown_1y": None,
        }
    score = 50
    signals: list[str] = []
    cautions: list[str] = []

    if price is not None and ma20 is not None:
        if price > ma20:
            score += 8
            signals.append("株価が20日移動平均を上回る")
        else:
            score -= 8
            cautions.append("株価が20日移動平均を下回る")
    if price is not None and ma50 is not None:
        score += 10 if price > ma50 else -10
        (signals if price > ma50 else cautions).append(
            "株価が50日移動平均を上回る" if price > ma50 else "株価が50日移動平均を下回る"
        )
    if ma50 is not None and ma200 is not None:
        score += 12 if ma50 > ma200 else -12
        (signals if ma50 > ma200 else cautions).append(
            "50日線が200日線を上回る" if ma50 > ma200 else "50日線が200日線を下回る"
        )
    if rsi is not None:
        if rsi >= 75:
            score -= 8
            cautions.append("RSIが75以上で短期過熱")
        elif 45 <= rsi <= 70:
            score += 7
            signals.append("RSIが健全な上昇帯")
        elif rsi <= 30:
            cautions.append("RSIが30以下で下落圧力に注意")
    if volatility is not None and volatility >= 0.60:
        score -= 8
        cautions.append("60日ボラティリティが高い")
    if drawdown is not None and drawdown <= -0.40:
        score -= 8
        cautions.append("1年最大ドローダウンが40%超")

    score = max(0, min(100, round(score)))
    trend = "上昇" if score >= 68 else "中立" if score >= 43 else "下降"
    return {
        "technical_score": score, "technical_trend": trend,
        "technical_signals": signals[:6], "technical_cautions": cautions[:6],
        "ma20": ma20, "ma50": ma50, "ma200": ma200, "rsi14": rsi,
        "volatility_60d": volatility, "max_drawdown_1y": drawdown,
    }
