from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "ai_review.json"


def save(value: dict) -> None:
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("CLAUDE_MODEL", "").strip()
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not key or not model:
        save({
            "generated_at": generated, "status": "未設定", "provider": "Claude", "model": model or None,
            "summary": "Claude連携は任意です。APIキーとモデル名を設定するまで、通常の判定・更新には影響しません。",
            "agreements": [], "objections": [], "proposals": [],
        })
        return
    review = json.loads((DATA / "model_review.json").read_text(encoding="utf-8"))
    payload = {
        "model": model,
        "max_tokens": 1800,
        "system": "あなたは日本株スクリーナーの独立監査役です。売買を推奨せず、データ品質、検証設計、過剰適合、反証材料を厳格に点検してください。基準を直接変更してはいけません。必ずJSONだけを返してください。",
        "messages": [{
            "role": "user",
            "content": "次の検証結果を監査し、summary（文字列）、agreements（文字列配列）、objections（文字列配列）、proposals（title/evidence/riskを持つ配列）を返してください。\n" + json.dumps(review, ensure_ascii=False),
        }],
    }
    response = requests.post(
        "https://api.anthropic.com/v1/messages", timeout=90,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    body = response.json()
    text = "".join(item.get("text", "") for item in body.get("content", []) if item.get("type") == "text")
    if text.strip().startswith("```"):
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(text[text.find("{"):text.rfind("}") + 1])
    save({
        "generated_at": generated, "status": "監査完了", "provider": "Claude", "model": model,
        "summary": str(parsed.get("summary") or ""),
        "agreements": [str(item) for item in parsed.get("agreements", [])][:10],
        "objections": [str(item) for item in parsed.get("objections", [])][:10],
        "proposals": parsed.get("proposals", [])[:10],
    })


if __name__ == "__main__":
    main()
