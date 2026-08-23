from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
POLICY_PATH = ROOT / "config" / "model_policy.json"
RESULTS_PATH = DATA / "results.json"
STATUS_PATH = DATA / "status.json"
HISTORY_PATH = DATA / "evaluation_history.json"
REVIEW_PATH = DATA / "model_review.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def week_key(value: datetime) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def compact(stock: dict) -> dict:
    return {
        "code": str(stock.get("code") or ""),
        "name": str(stock.get("name") or ""),
        "price": number(stock.get("price")),
        "investment_score": int(stock.get("investment_score") or 0),
        "tenbagger_score": int(stock.get("tenbagger_score") or 0),
        "risk_score": int(stock.get("risk_score") or 0),
        "type": str(stock.get("tenbagger_type") or ""),
    }


def deterministic_control(stocks: list[dict], key: str, limit: int, threshold: int) -> list[dict]:
    eligible = [s for s in stocks if number(s.get("price")) and int(s.get("tenbagger_score") or 0) < threshold]
    eligible.sort(key=lambda s: hashlib.sha256(f"{key}:{s.get('code')}".encode()).hexdigest())
    return [compact(s) for s in eligible[:limit]]


def add_snapshot(history: dict, results: dict, status: dict, policy: dict, current: datetime) -> None:
    if status.get("state") != "completed":
        return
    key = week_key(current)
    snapshots = history.setdefault("snapshots", [])
    if any(item.get("key") == key for item in snapshots):
        return
    stocks = results.get("stocks") or []
    rules = policy["review_rules"]
    threshold = int(policy.get("active_criteria", {}).get("tenbagger_candidate_score_min", 45))
    candidate_limit = int(rules.get("candidate_limit", 120))
    candidates = [s for s in stocks if number(s.get("price")) and int(s.get("tenbagger_score") or 0) >= threshold]
    candidates.sort(key=lambda s: (int(s.get("tenbagger_score") or 0), int(s.get("investment_score") or 0)), reverse=True)
    snapshots.append({
        "key": key,
        "captured_at": iso(current),
        "policy_version": policy.get("version", 1),
        "candidates": [compact(s) for s in candidates[:candidate_limit]],
        "control": deterministic_control(stocks, key, int(rules.get("control_limit", 120)), threshold),
        "outcomes": {},
    })
    limit = int(rules.get("history_limit_weeks", 110))
    history["snapshots"] = snapshots[-limit:]


def record_outcomes(history: dict, results: dict, policy: dict, current: datetime) -> None:
    current_prices = {
        str(stock.get("code")): number(stock.get("price"))
        for stock in results.get("stocks") or []
        if number(stock.get("price"))
    }
    for snapshot in history.get("snapshots") or []:
        try:
            captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        age = (current - captured).total_seconds() / 86400
        outcomes = snapshot.setdefault("outcomes", {})
        for horizon in policy["review_rules"].get("horizons_days", [30, 90, 180, 365]):
            key = str(horizon)
            if age < horizon or key in outcomes:
                continue
            groups = {}
            for group in ("candidates", "control"):
                returns = {}
                for item in snapshot.get(group) or []:
                    start = number(item.get("price"))
                    latest = current_prices.get(str(item.get("code")))
                    if start and latest:
                        returns[str(item["code"])] = round(latest / start - 1, 6)
                groups[group] = returns
            outcomes[key] = {"measured_at": iso(current), **groups}


def stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "average_return": None, "median_return": None, "gain_30_rate": None, "loss_20_rate": None}
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {
        "count": len(values),
        "average_return": round(sum(values) / len(values), 6),
        "median_return": round(median, 6),
        "gain_30_rate": round(sum(value >= 0.30 for value in values) / len(values), 6),
        "loss_20_rate": round(sum(value <= -0.20 for value in values) / len(values), 6),
    }


def aggregate(history: dict, policy: dict) -> tuple[list[dict], list[dict]]:
    horizons = []
    band_values = {"70点以上": [], "55～69点": [], "45～54点": []}
    for horizon in policy["review_rules"].get("horizons_days", [30, 90, 180, 365]):
        candidate_values, control_values = [], []
        for snapshot in history.get("snapshots") or []:
            outcome = (snapshot.get("outcomes") or {}).get(str(horizon))
            if not outcome:
                continue
            candidate_values.extend(outcome.get("candidates", {}).values())
            control_values.extend(outcome.get("control", {}).values())
            if horizon == 90:
                scores = {str(item.get("code")): int(item.get("tenbagger_score") or 0) for item in snapshot.get("candidates") or []}
                for code, value in outcome.get("candidates", {}).items():
                    score = scores.get(code, 0)
                    band = "70点以上" if score >= 70 else "55～69点" if score >= 55 else "45～54点"
                    band_values[band].append(value)
        candidate_stats, control_stats = stats(candidate_values), stats(control_values)
        excess = None
        if candidate_stats["average_return"] is not None and control_stats["average_return"] is not None:
            excess = round(candidate_stats["average_return"] - control_stats["average_return"], 6)
        horizons.append({"days": horizon, "candidates": candidate_stats, "control": control_stats, "excess_return": excess})
    bands = [{"label": label, **stats(values)} for label, values in band_values.items()]
    return horizons, bands


def quality(stocks: list[dict]) -> dict:
    fields = ["price", "market_cap", "per", "pbr", "net_cash_ratio", "revenue_cagr_3y", "technical_score"]
    total = len(stocks)
    coverage = {
        field: round(sum(stock.get(field) is not None for stock in stocks) / total * 100, 1) if total else 0
        for field in fields
    }
    anomalies = []
    for stock in stocks:
        code, name = str(stock.get("code") or ""), str(stock.get("name") or "")
        dividend = number(stock.get("dividend_yield"))
        price = number(stock.get("price"))
        if dividend is not None and (dividend < 0 or dividend > 25):
            anomalies.append({"code": code, "name": name, "field": "配当利回り", "value": dividend, "reason": "想定範囲外"})
        if price is not None and price <= 0:
            anomalies.append({"code": code, "name": name, "field": "株価", "value": price, "reason": "0以下"})
    return {
        "stock_count": total,
        "failed_count": sum(bool(stock.get("error")) for stock in stocks),
        "coverage_percent": coverage,
        "anomalies": anomalies[:30],
    }


def proposals(horizons: list[dict], bands: list[dict], current_quality: dict, minimum: int) -> list[dict]:
    output = []
    if current_quality["anomalies"]:
        output.append({
            "id": "data-quality-outliers", "status": "承認待ち", "title": "異常値の取得時検証を強化",
            "evidence": f"想定範囲外の数値を{len(current_quality['anomalies'])}件検出しました。",
            "change": "単位・桁を検証し、疑わしい値は判定から除外する案です。", "risk": "正常な特殊値を除外する可能性があります。",
        })
    ninety = next((item for item in horizons if item["days"] == 90), None)
    count = ninety["candidates"]["count"] if ninety else 0
    if count < minimum:
        output.append({
            "id": "keep-current-until-sample", "status": "観測中", "title": "現行基準を維持",
            "evidence": f"90日評価は{count}件です。改善判断には最低{minimum}件を必要とします。",
            "change": "判定基準は変更せず、標本を蓄積します。", "risk": "短期的な改善機会を見送る可能性があります。",
        })
    elif ninety.get("excess_return") is not None and ninety["excess_return"] <= 0:
        output.append({
            "id": "review-score-weights", "status": "承認待ち", "title": "候補スコア配点を再検証",
            "evidence": "90日成績で候補群が対照群を上回っていません。",
            "change": "各評価項目の寄与度を検証し、新配点を試験運用する案です。", "risk": "過去データへの過剰適合を招く可能性があります。",
        })
    if all(band["count"] >= minimum for band in bands):
        averages = [band["average_return"] for band in bands]
        if any(value is None for value in averages) or not (averages[0] >= averages[1] >= averages[2]):
            output.append({
                "id": "score-monotonicity", "status": "承認待ち", "title": "スコア順位の有効性を再検証",
                "evidence": "高得点帯ほど90日成績が高い関係を確認できません。",
                "change": "現行スコアと代替スコアを並行表示する案です。", "risk": "短期間の相場環境に左右される可能性があります。",
            })
    return output


def run(results_path=RESULTS_PATH, status_path=STATUS_PATH, history_path=HISTORY_PATH,
        review_path=REVIEW_PATH, policy_path=POLICY_PATH, current: datetime | None = None) -> dict:
    current = current or utc_now()
    policy = load_json(Path(policy_path), {})
    results = load_json(Path(results_path), {"stocks": []})
    status = load_json(Path(status_path), {})
    history = load_json(Path(history_path), {"schema_version": 1, "snapshots": []})
    add_snapshot(history, results, status, policy, current)
    record_outcomes(history, results, policy, current)
    horizons, bands = aggregate(history, policy)
    current_quality = quality(results.get("stocks") or [])
    minimum = int(policy["review_rules"].get("minimum_observations_for_proposal", 30))
    review = {
        "generated_at": iso(current),
        "status": "検証運用中" if history.get("snapshots") else "観測準備中",
        "policy_version": policy.get("version", 1),
        "snapshot_count": len(history.get("snapshots") or []),
        "current_quality": current_quality,
        "horizons": horizons,
        "score_bands": bands,
        "proposals": proposals(horizons, bands, current_quality, minimum),
        "safety": {"automatic_changes": False, "human_approval_required": True},
    }
    save_json(Path(history_path), history)
    save_json(Path(review_path), review)
    return review


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run()
