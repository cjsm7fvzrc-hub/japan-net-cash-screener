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
from catalyst_analysis import evaluate_catalysts
from decision_analysis import evaluate_decision
from kiyohara_analysis import evaluate, load_documents_for_candidates
from technical_analysis import evaluate_prices, summarize_technicals
from tenbagger_analysis import evaluate_tenbagger
from universe_filter import eligible_market

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "stocks.db"
STATUS_PATH = DATA / "status.json"
RESULTS_PATH = DATA / "results.json"
JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
BATCH_SIZE = max(1, int(os.getenv("BATCH_SIZE", "200")))
RESET_CURSOR = os.getenv("RESET_CURSOR", "false").lower() == "true"
UNIVERSE_VERSION = 2


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
        market = str(row[market_col]).strip()
        if not code or code == "nan" or not eligible_market(market):
            continue
        rows.append({
            "code": code,
            "ticker": f"{code}.T",
            "name": str(row[name_col]).strip(),
            "market": market,
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
    additions = {
        "cash": "REAL", "inventory": "REAL", "receivables": "REAL",
        "operating_cash_flow": "REAL", "net_income": "REAL",
        "cash_neutral_per": "REAL", "kiyohara_score": "INTEGER",
        "kiyohara_verdict": "TEXT", "kiyohara_confidence": "TEXT",
        "kiyohara_summary": "TEXT", "kiyohara_positives": "TEXT",
        "kiyohara_cautions": "TEXT", "source_name": "TEXT",
        "source_date": "TEXT", "source_doc_id": "TEXT",
        "analysis_updated_at": "TEXT",
        "revenue": "REAL", "revenue_cagr_3y": "REAL",
        "operating_income": "REAL", "operating_income_cagr_3y": "REAL",
        "quarterly_revenue_growth": "REAL", "operating_margin": "REAL",
        "operating_margin_change": "REAL", "return_52w": "REAL",
        "distance_from_52w_high": "REAL", "volume_ratio_20d": "REAL",
        "quarterly_operating_income_growth": "REAL", "forward_eps_growth": "REAL",
        "operating_profit_turnaround": "INTEGER",
        "earnings_growth": "REAL", "trailing_eps": "REAL", "forward_eps": "REAL",
        "sector": "TEXT", "industry": "TEXT", "company_website": "TEXT",
        "free_cash_flow": "REAL", "return_on_equity": "REAL", "return_on_assets": "REAL",
        "gross_margin": "REAL", "debt_to_equity": "REAL", "dividend_yield": "REAL",
        "business_summary": "TEXT", "ma20": "REAL", "ma50": "REAL", "ma200": "REAL",
        "rsi14": "REAL", "volatility_60d": "REAL", "max_drawdown_1y": "REAL",
        "technical_score": "INTEGER", "technical_trend": "TEXT",
        "price_history_52w": "TEXT",
    }
    existing = {row[1] for row in conn.execute("PRAGMA table_info(stocks)")}
    for column, kind in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {column} {kind}")
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


def statement_series(sheet: pd.DataFrame, names: list[str]) -> list[float | None]:
    if sheet is None or sheet.empty:
        return []
    for name in names:
        if name in sheet.index:
            values = sheet.loc[name]
            if not hasattr(values, "iloc"):
                return [finite(values)]
            return [finite(value) for value in values]
    return []


def growth(latest, oldest, years: int):
    if latest is None or oldest is None or latest <= 0 or oldest <= 0 or years <= 0:
        return None
    return (latest / oldest) ** (1 / years) - 1


def price_map(stocks: list[dict]) -> dict[str, dict]:
    tickers = [s["ticker"] for s in stocks]
    try:
        frame = yf.download(tickers, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
    except Exception:
        return {}
    result = {}
    for ticker in tickers:
        try:
            stock_frame = frame[ticker] if len(tickers) > 1 else frame
            series = stock_frame["Close"].dropna()
            volume = stock_frame["Volume"].dropna()
            latest = finite(series.iloc[-1]) if not series.empty else None
            first = finite(series.iloc[0]) if not series.empty else None
            high = finite(series.max()) if not series.empty else None
            recent_volume = finite(volume.tail(5).mean()) if len(volume) >= 5 else None
            normal_volume = finite(volume.tail(20).mean()) if len(volume) >= 20 else None
            technical = evaluate_prices(series.tolist())
            weekly = series.resample("W").last().dropna().tail(52)
            result[ticker] = {
                "price": latest,
                "return_52w": latest / first - 1 if latest and first else None,
                "distance_from_52w_high": latest / high - 1 if latest and high else None,
                "volume_ratio_20d": recent_volume / normal_volume if recent_volume and normal_volume else None,
                **technical,
                "price_history_52w": json.dumps([round(float(value), 2) for value in weekly]),
            }
        except Exception:
            result[ticker] = {}
    return result


def collect(stock: dict, prices: dict[str, dict]) -> dict:
    ticker = yf.Ticker(stock["ticker"])
    error = ""
    try:
        info = ticker.get_info()
        sheet = ticker.quarterly_balance_sheet
        if sheet is None or sheet.empty:
            sheet = ticker.balance_sheet
        cashflow = ticker.quarterly_cashflow
        if cashflow is None or cashflow.empty:
            cashflow = ticker.cashflow
        income = ticker.quarterly_income_stmt
        if income is None or income.empty:
            income = ticker.income_stmt
        market = prices.get(stock["ticker"], {})
        price = market.get("price") or finite(info.get("currentPrice")) or finite(info.get("regularMarketPrice"))
        shares = finite(info.get("sharesOutstanding"))
        cap = finite(info.get("marketCap")) or (price * shares if price and shares else None)
        per = finite(info.get("trailingPE"))
        pbr = finite(info.get("priceToBook"))
        current_assets = statement_value(sheet, ["Current Assets", "Total Current Assets"])
        securities = statement_value(sheet, ["Investmentin Financial Assets", "Available For Sale Securities", "Other Investments"])
        securities = securities or 0.0
        liabilities = statement_value(sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
        cash = statement_value(sheet, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash"])
        inventory = statement_value(sheet, ["Inventory", "Inventories"])
        receivables = statement_value(sheet, ["Receivables", "Accounts Receivable", "Accounts Receivable Net"])
        operating_cash_flow = statement_value(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        net_income = statement_value(income, ["Net Income", "Net Income Common Stockholders", "Net Income Applicable To Common Shares"])
        annual_income = ticker.income_stmt
        revenues = statement_series(annual_income, ["Total Revenue", "Operating Revenue"])
        operating_incomes = statement_series(annual_income, ["Operating Income"])
        quarterly_revenues = statement_series(income, ["Total Revenue", "Operating Revenue"])
        quarterly_operating_incomes = statement_series(income, ["Operating Income"])
        revenue = revenues[0] if revenues else None
        operating_income = operating_incomes[0] if operating_incomes else None
        oldest_revenue_index = min(3, len(revenues) - 1) if revenues else 0
        oldest_operating_index = min(3, len(operating_incomes) - 1) if operating_incomes else 0
        revenue_cagr_3y = growth(revenue, revenues[oldest_revenue_index], oldest_revenue_index) if revenues else None
        operating_income_cagr_3y = growth(operating_income, operating_incomes[oldest_operating_index], oldest_operating_index) if operating_incomes else None
        quarterly_revenue_growth = (
            quarterly_revenues[0] / quarterly_revenues[4] - 1
            if len(quarterly_revenues) >= 5 and quarterly_revenues[0] and quarterly_revenues[4] else None
        )
        latest_quarterly_operating = quarterly_operating_incomes[0] if quarterly_operating_incomes else None
        prior_year_quarterly_operating = quarterly_operating_incomes[4] if len(quarterly_operating_incomes) >= 5 else None
        operating_profit_turnaround = bool(
            latest_quarterly_operating is not None and latest_quarterly_operating > 0
            and prior_year_quarterly_operating is not None and prior_year_quarterly_operating <= 0
        )
        if operating_profit_turnaround:
            quarterly_operating_income_growth = 1.0
        elif latest_quarterly_operating is not None and prior_year_quarterly_operating is not None:
            quarterly_operating_income_growth = (
                latest_quarterly_operating / prior_year_quarterly_operating - 1
                if latest_quarterly_operating > 0 and prior_year_quarterly_operating > 0
                else -1.0 if latest_quarterly_operating <= 0 < prior_year_quarterly_operating else None
            )
        else:
            quarterly_operating_income_growth = None
        operating_margin = operating_income / revenue if operating_income is not None and revenue else None
        previous_margin = (
            operating_incomes[1] / revenues[1]
            if len(operating_incomes) > 1 and len(revenues) > 1 and operating_incomes[1] is not None and revenues[1] else None
        )
        operating_margin_change = operating_margin - previous_margin if operating_margin is not None and previous_margin is not None else None
        trailing_eps = finite(info.get("trailingEps"))
        forward_eps = finite(info.get("forwardEps"))
        forward_eps_growth = (
            forward_eps / trailing_eps - 1
            if forward_eps is not None and trailing_eps is not None and trailing_eps > 0 else None
        )
        earnings_growth = finite(info.get("earningsGrowth"))
        sector = str(info.get("sector") or "")[:120]
        industry = str(info.get("industry") or "")[:160]
        company_website = str(info.get("website") or "")[:500]
        free_cash_flow = finite(info.get("freeCashflow"))
        return_on_equity = finite(info.get("returnOnEquity"))
        return_on_assets = finite(info.get("returnOnAssets"))
        gross_margin = finite(info.get("grossMargins"))
        debt_to_equity = finite(info.get("debtToEquity"))
        dividend_yield = finite(info.get("dividendYield"))
        business_summary = str(info.get("longBusinessSummary") or "")[:900]
        net_cash = current_assets + securities * 0.7 - liabilities if current_assets is not None and liabilities is not None else None
        ratio = net_cash / cap if net_cash is not None and cap and cap > 0 else None
        passed = bool(
            ratio is not None and ratio >= 1
            and per is not None and 0 < per <= 10
            and pbr is not None and 0 < pbr <= 1
            and cap is not None and cap >= 2_000_000_000
            and current_assets is not None and liabilities is not None and current_assets > liabilities
        )
        financial_date = str(sheet.columns[0].date()) if sheet is not None and not sheet.empty else None
    except Exception as exc:
        price = cap = per = pbr = current_assets = liabilities = net_cash = ratio = None
        securities = cash = inventory = receivables = operating_cash_flow = net_income = None
        revenue = revenue_cagr_3y = operating_income = operating_income_cagr_3y = None
        quarterly_revenue_growth = operating_margin = operating_margin_change = None
        quarterly_operating_income_growth = forward_eps_growth = earnings_growth = None
        operating_profit_turnaround = False
        trailing_eps = forward_eps = None
        sector = industry = company_website = ""
        business_summary = ""
        free_cash_flow = return_on_equity = return_on_assets = gross_margin = None
        debt_to_equity = dividend_yield = None
        market = {}
        passed = False
        financial_date = None
        error = f"{type(exc).__name__}: {str(exc)[:180]}"
    return {**stock, "price": price, "market_cap": cap, "per": per, "pbr": pbr,
            "current_assets": current_assets, "investment_securities": securities,
            "cash": cash, "inventory": inventory, "receivables": receivables,
            "operating_cash_flow": operating_cash_flow, "net_income": net_income,
            "liabilities": liabilities, "net_cash": net_cash, "net_cash_ratio": ratio,
            "revenue": revenue, "revenue_cagr_3y": revenue_cagr_3y,
            "operating_income": operating_income, "operating_income_cagr_3y": operating_income_cagr_3y,
            "quarterly_revenue_growth": quarterly_revenue_growth,
            "quarterly_operating_income_growth": quarterly_operating_income_growth,
            "operating_profit_turnaround": operating_profit_turnaround,
            "operating_margin": operating_margin, "operating_margin_change": operating_margin_change,
            "trailing_eps": trailing_eps, "forward_eps": forward_eps,
            "forward_eps_growth": forward_eps_growth, "earnings_growth": earnings_growth,
            "sector": sector, "industry": industry, "company_website": company_website,
            "free_cash_flow": free_cash_flow, "return_on_equity": return_on_equity,
            "return_on_assets": return_on_assets, "gross_margin": gross_margin,
            "debt_to_equity": debt_to_equity, "dividend_yield": dividend_yield,
            "business_summary": business_summary,
            "return_52w": market.get("return_52w"),
            "distance_from_52w_high": market.get("distance_from_52w_high"),
            "volume_ratio_20d": market.get("volume_ratio_20d"),
            "ma20": market.get("ma20"), "ma50": market.get("ma50"), "ma200": market.get("ma200"),
            "rsi14": market.get("rsi14"), "volatility_60d": market.get("volatility_60d"),
            "max_drawdown_1y": market.get("max_drawdown_1y"),
            "technical_score": market.get("technical_score"), "technical_trend": market.get("technical_trend"),
            "price_history_52w": market.get("price_history_52w"),
            "passed": passed, "financial_date": financial_date, "error": error,
            "fetched_at": now()}


def save(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute("""
      INSERT INTO stocks (code,name,market,price,market_cap,per,pbr,
        current_assets,investment_securities,liabilities,net_cash,net_cash_ratio,
        passed,financial_date,error,fetched_at,cash,inventory,receivables,operating_cash_flow,net_income,
        revenue,revenue_cagr_3y,operating_income,operating_income_cagr_3y,quarterly_revenue_growth,
        quarterly_operating_income_growth,operating_profit_turnaround,operating_margin,operating_margin_change,
        trailing_eps,forward_eps,forward_eps_growth,earnings_growth,sector,industry,company_website,
        free_cash_flow,return_on_equity,return_on_assets,gross_margin,debt_to_equity,dividend_yield,business_summary,
        return_52w,distance_from_52w_high,volume_ratio_20d,ma20,ma50,ma200,rsi14,volatility_60d,max_drawdown_1y,
        technical_score,technical_trend,price_history_52w)
      VALUES (:code,:name,:market,:price,:market_cap,:per,:pbr,
        :current_assets,:investment_securities,:liabilities,:net_cash,:net_cash_ratio,
        :passed,:financial_date,:error,:fetched_at,:cash,:inventory,:receivables,:operating_cash_flow,:net_income,
        :revenue,:revenue_cagr_3y,:operating_income,:operating_income_cagr_3y,:quarterly_revenue_growth,
        :quarterly_operating_income_growth,:operating_profit_turnaround,:operating_margin,:operating_margin_change,
        :trailing_eps,:forward_eps,:forward_eps_growth,:earnings_growth,:sector,:industry,:company_website,
        :free_cash_flow,:return_on_equity,:return_on_assets,:gross_margin,:debt_to_equity,:dividend_yield,:business_summary,
        :return_52w,:distance_from_52w_high,:volume_ratio_20d,:ma20,:ma50,:ma200,:rsi14,:volatility_60d,:max_drawdown_1y,
        :technical_score,:technical_trend,:price_history_52w)
      ON CONFLICT(code) DO UPDATE SET
        name=excluded.name, market=excluded.market, price=excluded.price,
        market_cap=excluded.market_cap, per=excluded.per, pbr=excluded.pbr,
        current_assets=excluded.current_assets, investment_securities=excluded.investment_securities,
        liabilities=excluded.liabilities, net_cash=excluded.net_cash,
        net_cash_ratio=excluded.net_cash_ratio, passed=excluded.passed,
        financial_date=excluded.financial_date, error=excluded.error, fetched_at=excluded.fetched_at
        ,cash=excluded.cash, inventory=excluded.inventory, receivables=excluded.receivables,
        operating_cash_flow=excluded.operating_cash_flow, net_income=excluded.net_income
        ,revenue=excluded.revenue, revenue_cagr_3y=excluded.revenue_cagr_3y,
        operating_income=excluded.operating_income, operating_income_cagr_3y=excluded.operating_income_cagr_3y,
        quarterly_revenue_growth=excluded.quarterly_revenue_growth,
        quarterly_operating_income_growth=excluded.quarterly_operating_income_growth,
        operating_profit_turnaround=excluded.operating_profit_turnaround,
        operating_margin=excluded.operating_margin, operating_margin_change=excluded.operating_margin_change,
        trailing_eps=excluded.trailing_eps, forward_eps=excluded.forward_eps,
        forward_eps_growth=excluded.forward_eps_growth, earnings_growth=excluded.earnings_growth,
        sector=excluded.sector, industry=excluded.industry, company_website=excluded.company_website,
        free_cash_flow=excluded.free_cash_flow, return_on_equity=excluded.return_on_equity,
        return_on_assets=excluded.return_on_assets, gross_margin=excluded.gross_margin,
        debt_to_equity=excluded.debt_to_equity, dividend_yield=excluded.dividend_yield,
        business_summary=excluded.business_summary,
        return_52w=excluded.return_52w, distance_from_52w_high=excluded.distance_from_52w_high,
        volume_ratio_20d=excluded.volume_ratio_20d
        ,ma20=excluded.ma20, ma50=excluded.ma50, ma200=excluded.ma200, rsi14=excluded.rsi14,
        volatility_60d=excluded.volatility_60d, max_drawdown_1y=excluded.max_drawdown_1y,
        technical_score=excluded.technical_score, technical_trend=excluded.technical_trend
        ,price_history_52w=excluded.price_history_52w
    """, row)


def save_analysis(conn: sqlite3.Connection, code: str, analysis: dict) -> None:
    conn.execute("""
      UPDATE stocks SET cash_neutral_per=:cash_neutral_per,
        kiyohara_score=:kiyohara_score, kiyohara_verdict=:kiyohara_verdict,
        kiyohara_confidence=:kiyohara_confidence, kiyohara_summary=:kiyohara_summary,
        kiyohara_positives=:kiyohara_positives, kiyohara_cautions=:kiyohara_cautions,
        source_name=:source_name, source_date=:source_date, source_doc_id=:source_doc_id,
        analysis_updated_at=:analysis_updated_at
      WHERE code=:code
    """, {**analysis, "code": code})


def export(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM stocks ORDER BY net_cash_ratio DESC")]
    for row in rows:
        row["passed"] = bool(row["passed"])
        for field in ("kiyohara_positives", "kiyohara_cautions"):
            try:
                row[field] = json.loads(row[field] or "[]")
            except (TypeError, json.JSONDecodeError):
                row[field] = []
        try:
            row["price_history_52w"] = json.loads(row.get("price_history_52w") or "[]")
        except (TypeError, json.JSONDecodeError):
            row["price_history_52w"] = []
        row.update(evaluate_tenbagger(row))
        row.update(evaluate_catalysts(row))
        row.update(evaluate_decision(row))
        row.update(summarize_technicals(row))
    write_json(RESULTS_PATH, {"generated_at": now(), "stocks": rows})
    return rows


def main() -> None:
    DATA.mkdir(exist_ok=True)
    universe = fetch_jpx()
    total = len(universe)
    previous = load_status()
    universe_changed = previous.get("universe_version") != UNIVERSE_VERSION
    cursor = 0 if RESET_CURSOR or universe_changed else int(previous.get("next_cursor") or 0)
    if cursor >= total:
        cursor = 0
    end = min(cursor + BATCH_SIZE, total)
    target = universe[cursor:end]
    status = {"state": "running", "message": "銘柄データを収集中", "total": total,
              "processed": cursor, "success": 0, "failed": 0, "passed": 0,
              "progress": round(cursor / total * 100, 1) if total else 0,
              "started_at": now(), "updated_at": now(), "completed_at": previous.get("completed_at"),
              "next_cursor": cursor, "universe_version": UNIVERSE_VERSION}
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
        save_analysis(conn, row["code"], evaluate(row))
        conn.commit()
        failures += bool(row["error"])
        successes += not bool(row["error"])
        status.update({"processed": index, "success": successes, "failed": failures,
                       "progress": round(index / total * 100, 1), "updated_at": now(),
                       "next_cursor": 0 if index >= total else index})
        write_json(STATUS_PATH, status)
        time.sleep(0.35)
    conn.row_factory = sqlite3.Row
    analysis_rows = [dict(r) for r in conn.execute("SELECT * FROM stocks")]
    for row in analysis_rows:
        row["passed"] = bool(row["passed"])
    documents = load_documents_for_candidates(analysis_rows, DATA)
    for row in analysis_rows:
        save_analysis(conn, row["code"], evaluate(row, documents.get(row["code"])))
    conn.commit()
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
