import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_stocks import init_db, save


class UpdateStorageTests(unittest.TestCase):
    def test_phase2_fields_migrate_and_save(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        row = {
            "code": "9999", "name": "テスト", "market": "プライム",
            "price": 1000, "market_cap": 10_000_000_000, "per": 10, "pbr": 1,
            "current_assets": 20, "investment_securities": 0, "liabilities": 5,
            "net_cash": 15, "net_cash_ratio": 1.5, "passed": True,
            "financial_date": "2026-06-30", "error": "", "fetched_at": "2026-08-22T00:00:00Z",
            "cash": 10, "inventory": 1, "receivables": 2,
            "operating_cash_flow": 3, "net_income": 2,
            "revenue": 100, "revenue_cagr_3y": 0.1,
            "operating_income": 12, "operating_income_cagr_3y": 0.2,
            "quarterly_revenue_growth": 0.15,
            "quarterly_operating_income_growth": 0.3,
            "operating_profit_turnaround": False,
            "operating_margin": 0.12, "operating_margin_change": 0.02,
            "trailing_eps": 50, "forward_eps": 65, "forward_eps_growth": 0.3,
            "earnings_growth": 0.25, "sector": "Technology", "industry": "Software",
            "company_website": "https://example.com", "return_52w": 0.1,
            "distance_from_52w_high": -0.05, "volume_ratio_20d": 1.6,
            "free_cash_flow": 4, "return_on_equity": 0.15, "return_on_assets": 0.08,
            "gross_margin": 0.4, "debt_to_equity": 25, "dividend_yield": 0.02,
            "business_summary": "テスト事業", "ma20": 980, "ma50": 950, "ma200": 900,
            "rsi14": 60, "volatility_60d": 0.25, "max_drawdown_1y": -0.2,
            "technical_score": 80, "technical_trend": "上昇",
            "price_history_52w": "[900, 950, 1000]",
        }
        save(conn, row)
        stored = conn.execute(
            "SELECT quarterly_operating_income_growth, forward_eps_growth, company_website FROM stocks WHERE code='9999'"
        ).fetchone()
        self.assertEqual(stored, (0.3, 0.3, "https://example.com"))


if __name__ == "__main__":
    unittest.main()
