from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

EDINET_LIST_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
EDINET_DOC_URL = "https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
POSITIVE_TERMS = {
    "自社株買い・自己株式取得": ("自己株式の取得", "自己株式取得", "自社株買い"),
    "増配・株主還元": ("増配", "株主還元", "配当性向"),
    "政策保有株式の縮減": ("政策保有株式の縮減", "政策保有株式を縮減", "保有意義が認められない"),
    "不採算事業の改善": ("不採算事業", "事業構造改革", "収益性改善"),
}
CAUTION_TERMS = {
    "継続企業に関する注意": ("継続企業の前提", "重要な疑義"),
    "減損・評価損": ("減損損失", "評価損"),
    "在庫・棚卸資産リスク": ("棚卸資産評価損", "滞留在庫", "陳腐化"),
    "希薄化・増資": ("第三者割当増資", "新株予約権", "株式の希薄化"),
    "重要な訴訟・偶発債務": ("重要な訴訟", "偶発債務"),
}


def _finite(value):
    try:
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _ratio(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def evaluate(row: dict, document: dict | None = None) -> dict:
    score = 0
    positives: list[str] = []
    cautions: list[str] = []
    ratio = _finite(row.get("net_cash_ratio"))
    per = _finite(row.get("per"))
    pbr = _finite(row.get("pbr"))
    cap = _finite(row.get("market_cap"))
    current = _finite(row.get("current_assets"))
    cash = _finite(row.get("cash"))
    securities = _finite(row.get("investment_securities")) or 0
    inventory = _finite(row.get("inventory"))
    receivables = _finite(row.get("receivables"))
    ocf = _finite(row.get("operating_cash_flow"))
    profit = _finite(row.get("net_income"))
    cn_per = None
    if per is not None and ratio is not None:
        cn_per = per * (1 - ratio)

    if ratio is not None and ratio >= 1:
        score += 30
        positives.append("ネットキャッシュが時価総額を上回る")
    elif ratio is not None and ratio >= 0.5:
        score += 20
        positives.append("ネットキャッシュ比率が比較的高い")
    elif ratio is not None and ratio >= 0.2:
        score += 10
    else:
        cautions.append("ネットキャッシュによる十分な安全余裕を確認できない")

    if per is not None and 0 < per <= 5:
        score += 20
        positives.append("PERが5倍以下")
    elif per is not None and 0 < per <= 10:
        score += 15
        positives.append("PERが10倍以下")
    else:
        cautions.append("利益に対する割安性が弱い、または利益データが不足")

    if pbr is not None and 0 < pbr <= 0.5:
        score += 10
        positives.append("PBRが0.5倍以下")
    elif pbr is not None and 0 < pbr <= 1:
        score += 7

    liquid_quality = _ratio((cash or 0) + securities * 0.7, current)
    inventory_ratio = _ratio(inventory, current)
    receivables_ratio = _ratio(receivables, current)
    if liquid_quality is not None and liquid_quality >= 0.5:
        score += 10
        positives.append("流動資産に占める現金性資産の割合が高い")
    if inventory_ratio is not None and inventory_ratio >= 0.35:
        score -= 10
        cautions.append("流動資産に占める棚卸資産の割合が高い")
    if receivables_ratio is not None and receivables_ratio >= 0.5:
        score -= 8
        cautions.append("流動資産に占める売上債権の割合が高い")

    if ocf is not None and ocf > 0:
        score += 8
        positives.append("営業キャッシュフローが黒字")
        conversion = _ratio(ocf, profit)
        if conversion is not None and conversion >= 0.8:
            score += 5
            positives.append("利益が営業キャッシュフローを伴っている")
    elif ocf is not None:
        score -= 12
        cautions.append("営業キャッシュフローが赤字")
    if profit is not None and profit <= 0:
        score -= 20
        cautions.append("最終利益が赤字")
    if cap is not None and cap < 10_000_000_000:
        score += 5
        positives.append("時価総額100億円未満の小型株")

    source_name = None
    source_date = None
    source_doc_id = None
    if document:
        positives.extend(x for x in document.get("positives", []) if x not in positives)
        cautions.extend(x for x in document.get("cautions", []) if x not in cautions)
        score += min(8, len(document.get("positives", [])) * 2)
        score -= min(15, len(document.get("cautions", [])) * 3)
        source_name = document.get("name")
        source_date = document.get("date")
        source_doc_id = document.get("doc_id")

    score = max(0, min(100, round(score)))
    if score >= 75:
        verdict = "有力候補"
    elif score >= 55:
        verdict = "調査価値あり"
    elif score >= 35:
        verdict = "慎重に精査"
    else:
        verdict = "割安の罠に注意"
    confidence = "資料確認済み" if document else "数値ベース"
    lead = positives[0] if positives else "明確な強みを確認できません"
    risk = cautions[0] if cautions else "現時点で大きな警戒項目は検出されていません"
    summary = f"{lead}。一方、{risk}。公開情報を追加確認したうえで判断すべき候補です。"
    return {
        "kiyohara_score": score,
        "kiyohara_verdict": verdict,
        "kiyohara_confidence": confidence,
        "kiyohara_summary": summary,
        "kiyohara_positives": json.dumps(positives[:6], ensure_ascii=False),
        "kiyohara_cautions": json.dumps(cautions[:6], ensure_ascii=False),
        "cash_neutral_per": cn_per,
        "source_name": source_name,
        "source_date": source_date,
        "source_doc_id": source_doc_id,
        "analysis_updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _term_hits(text: str, groups: dict[str, tuple[str, ...]]) -> list[str]:
    normalized = re.sub(r"\s+", "", text)
    return [label for label, terms in groups.items() if any(term in normalized for term in terms)]


def _download_document(api_key: str, info: dict) -> dict | None:
    response = requests.get(
        EDINET_DOC_URL.format(doc_id=info["doc_id"]),
        params={"type": 1, "Subscription-Key": api_key}, timeout=90,
    )
    response.raise_for_status()
    chunks = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith((".htm", ".html")) and "PublicDoc" in n]
        for name in names[:40]:
            chunks.append(BeautifulSoup(archive.read(name), "html.parser").get_text(" ", strip=True))
    text = " ".join(chunks)
    if not text:
        return None
    return {
        **info,
        "positives": _term_hits(text, POSITIVE_TERMS),
        "cautions": _term_hits(text, CAUTION_TERMS),
    }


def _build_index(api_key: str, cache_path: Path, lookback_days: int = 220) -> dict:
    index = {}
    today = date.today()
    for offset in range(lookback_days):
        target = today - timedelta(days=offset)
        response = requests.get(
            EDINET_LIST_URL,
            params={"date": target.isoformat(), "type": 2, "Subscription-Key": api_key},
            timeout=45,
        )
        if response.status_code != 200:
            continue
        for item in response.json().get("results", []):
            sec = str(item.get("secCode") or "")[:4]
            if not sec or item.get("docTypeCode") != "120" or str(item.get("withdrawalStatus")) == "1":
                continue
            if sec not in index:
                index[sec] = {
                    "doc_id": item.get("docID"),
                    "name": item.get("docDescription") or "有価証券報告書",
                    "date": str(item.get("submitDateTime") or "")[:10],
                }
    cache_path.write_text(json.dumps({"built_at": date.today().isoformat(), "documents": index}, ensure_ascii=False), encoding="utf-8")
    return index


def load_documents_for_candidates(rows: list[dict], data_dir: Path) -> dict[str, dict]:
    api_key = os.getenv("EDINET_API_KEY", "").strip()
    candidates = [r for r in rows if r.get("passed")]
    if not api_key or not candidates:
        return {}
    cache_path = data_dir / "edinet_index.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        built_at = cached.get("built_at")
        index = cached.get("documents", {})
        if not index or not built_at or date.fromisoformat(built_at) < date.today() - timedelta(days=7):
            index = _build_index(api_key, cache_path)
    except Exception:
        return {}
    documents = {}
    for row in candidates:
        info = index.get(str(row["code"])[:4])
        if not info:
            continue
        try:
            document = _download_document(api_key, info)
            if document:
                documents[row["code"]] = document
        except Exception:
            continue
    return documents
