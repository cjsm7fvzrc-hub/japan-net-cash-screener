from __future__ import annotations

import io
import json
import math
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "stocks.db"
STATUS_PATH = DATA / "status.json"
RESULTS_PATH = DATA / "results.json"
JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
BATCH_SIZE = max(1, int(os.getenv("BATCH_SIZE", "200")))
RESET_CURSOR = os.getenv("RESET_CURSOR", "false").lower() == "true"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_status() -> dict:
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return {"next_cursor": 0}


def fetch_jpx() -> list[dict]:
    response = requests.get(JPX_URL, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content), dtype=str)
    code_col = next(c for c in frame.columns if "コード" in str(c))
    name_col = next(c for c in frame.columns if "銘柄名" in str(c))
    market_col = next(c for c in frame.columns if "市場・商品区分" in str(c))
    rows = []
    for _, row in frame.iterrows():
        code = str(row[code_col]).strip()
        if not code or code == "nan":
            continue
        rows.append({
            "code": code,
            "ticker": f"{code}.T",
            "name": str(row[name_col]).strip(),
            "market": str(row[market_col]).strip(),
        })
    return rows


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
          code TEXT PRIMARY KEY, name TEXT NOT NULL, market TEXT NOT NULL,
          price REAL, market_cap REAL, per REAL, pbr REAL,
          current_assets REAL, investment_securities REAL, liabilities REAL,
          net_cash REAL, net_cash_ratio REAL, passed INTEGER NOT NULL DEFAULT 0,
          financial_date TEXT, error TEXT, fetched_at TEXT NOT NULL
        )
    """)
    conn.commit()


def statement_value(sheet: pd.DataFrame, names: list[str]):
    if sheet is None or sheet.empty:
        return None
    for name in names:
        if name in sheet.index:
            values = sheet.loc[name]
            if hasattr(values, "iloc"):
                for value in values:
                    parsed = finite(value)
                    if parsed is not None:
                        return parsed
            return finite(values)
    return None


def price_map(stocks: list[dict]) -> dict[str, float | None]:
    tickers = [s["ticker"] for s in stocks]
    try:
        frame = yf.download(tickers, period="5d", interval="1d", group_by="ticker", threads=True, progress=False)
    except Exception:
        return {}
    result = {}
    for ticker in tickers:
        try:
            series = frame[ticker]["Close"] if len(tickers) > 1 else frame["Close"]
            series = series.dropna()
            result[ticker] = finite(series.iloc[-1]) if not series.empty else None
        except Exception:
            result[ticker] = None
    return result


def collect(stock: dict, prices: dict[str, float | None]) -> dict:
    ticker = yf.Ticker(stock["ticker"])
    error = ""
    try:
        info = ticker.get_info()
        sheet = ticker.quarterly_balance_sheet
        if sheet is None or sheet.empty:
            sheet = ticker.balance_sheet
        price = prices.get(stock["ticker"]) or finite(info.get("currentPrice")) or finite(info.get("regularMarketPrice"))
        shares = finite(info.get("sharesOutstanding"))
        cap = finite(info.get("marketCap")) or (price * shares if price and shares else None)
        per = finite(info.get("trailingPE"))
        pbr = finite(info.get("priceToBook"))
        current_assets = statement_value(sheet, ["Current Assets", "Total Current Assets"])
        securities = statement_value(sheet, ["Investmentin Financial Assets", "Available For Sale Securities", "Other Investments"])
        securities = securities or 0.0
        liabilities = statement_value(sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
        net_cash = current_assets + securities * 0.7 - liabilities if current_assets is not None and liabilities is not None else None
        ratio = net_cash / cap if net_cash is not None and cap and cap > 0 else None
        passed = bool(
            ratio is not None and ratio >= 1
            and per is not None and 0 < per <= 10
            and pbr is not None and 0 < pbr <= 1
            and cap is not None and 2_000_000_000 <= cap < 50_000_000_000
            and current_assets is not None and liabilities is not None and current_assets > liabilities
        )
        financial_date = str(sheet.columns[0].date()) if sheet is not None and not sheet.empty else None
    except Exception as exc:
        price = cap = per = pbr = current_assets = liabilities = net_cash = ratio = None
        securities = None
        passed = False
        financial_date = None
        error = f"{type(exc).__name__}: {str(exc)[:180]}"
    return {**stock, "price": price, "market_cap": cap, "per": per, "pbr": pbr,
            "current_assets": current_assets, "investment_securities": securities,
            "liabilities": liabilities, "net_cash": net_cash, "net_cash_ratio": ratio,
            "passed": passed, "financial_date": financial_date, "error": error,
            "fetched_at": now()}


def save(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute("""
      INSERT INTO stocks VALUES (:code,:name,:market,:price,:market_cap,:per,:pbr,
        :current_assets,:investment_securities,:liabilities,:net_cash,:net_cash_ratio,
        :passed,:financial_date,:error,:fetched_at)
      ON CONFLICT(code) DO UPDATE SET
        name=excluded.name, market=excluded.market, price=excluded.price,
        market_cap=excluded.market_cap, per=excluded.per, pbr=excluded.pbr,
        current_assets=excluded.current_assets, investment_securities=excluded.investment_securities,
        liabilities=excluded.liabilities, net_cash=excluded.net_cash,
        net_cash_ratio=excluded.net_cash_ratio, passed=excluded.passed,
        financial_date=excluded.financial_date, error=excluded.error, fetched_at=excluded.fetched_at
    """, row)


def export(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM stocks ORDER BY net_cash_ratio DESC")]
    for row in rows:
        row["passed"] = bool(row["passed"])
    write_json(RESULTS_PATH, {"generated_at": now(), "stocks": rows})
    return rows


def main() -> None:
    DATA.mkdir(exist_ok=True)
    universe = fetch_jpx()
    total = len(universe)
    previous = load_status()
    cursor = 0 if RESET_CURSOR else int(previous.get("next_cursor") or 0)
    if cursor >= total:
        cursor = 0
    end = min(cursor + BATCH_SIZE, total)
    target = universe[cursor:end]
    status = {"state": "running", "message": "銘柄データを収集中", "total": total,
              "processed": cursor, "success": 0, "failed": 0, "passed": 0,
              "progress": round(cursor / total * 100, 1) if total else 0,
              "started_at": now(), "updated_at": now(), "completed_at": previous.get("completed_at"),
              "next_cursor": cursor}
    write_json(STATUS_PATH, status)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    if cursor == 0:
        conn.execute("CREATE TEMP TABLE current_universe (code TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO current_universe(code) VALUES (?)", [(s["code"],) for s in universe])
        conn.execute("DELETE FROM stocks WHERE code NOT IN (SELECT code FROM current_universe)")
        conn.commit()
    prices = price_map(target)
    successes = failures = 0
    for index, stock in enumerate(target, start=cursor + 1):
        row = collect(stock, prices)
        save(conn, row)
        conn.commit()
        failures += bool(row["error"])
        successes += not bool(row["error"])
        status.update({"processed": index, "success": successes, "failed": failures,
                       "progress": round(index / total * 100, 1), "updated_at": now(),
                       "next_cursor": 0 if index >= total else index})
        write_json(STATUS_PATH, status)
        time.sleep(0.35)
    rows = export(conn)
    completed = end >= total
    all_failed = sum(1 for r in rows if r["error"])
    all_success = len(rows) - all_failed
    status.update({"state": "completed" if completed else "running",
                   "message": "全上場銘柄の更新が完了しました" if completed else "次回の自動処理へ継続します",
                   "success": all_success, "failed": all_failed,
                   "passed": sum(1 for r in rows if r["passed"]),
                   "completed_at": now() if completed else previous.get("completed_at"),
                   "updated_at": now(), "next_cursor": 0 if completed else end})
    write_json(STATUS_PATH, status)
    conn.close()


if __name__ == "__main__":
    main()
