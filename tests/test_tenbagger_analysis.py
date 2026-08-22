import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from tenbagger_analysis import evaluate_tenbagger


class TenbaggerAnalysisTest(unittest.TestCase):
    def test_growth_acceleration_is_ranked_high(self):
        result = evaluate_tenbagger({
            "market_cap": 8_000_000_000, "revenue_cagr_3y": .25,
            "operating_income_cagr_3y": .45, "quarterly_revenue_growth": .30,
            "operating_margin": .14, "operating_margin_change": .035,
            "net_cash_ratio": .5, "per": 12, "pbr": .9,
            "operating_cash_flow": 800_000_000, "net_income": 500_000_000,
            "distance_from_52w_high": -.05, "return_52w": .35,
            "volume_ratio_20d": 1.8,
        })
        self.assertGreaterEqual(result["tenbagger_score"], 75)
        self.assertEqual(result["tenbagger_type"], "変身型")

    def test_cash_rich_value_stock_is_kiyohara_type(self):
        result = evaluate_tenbagger({
            "market_cap": 6_000_000_000, "net_cash_ratio": 1.2,
            "per": 7, "pbr": .6, "operating_cash_flow": 300_000_000,
            "net_income": 200_000_000,
        })
        self.assertEqual(result["tenbagger_type"], "清原型")

    def test_cash_burn_is_flagged(self):
        result = evaluate_tenbagger({
            "market_cap": 5_000_000_000, "net_cash_ratio": -.2,
            "operating_cash_flow": -100_000_000, "net_income": -50_000_000,
        })
        self.assertIn("営業キャッシュフローが赤字", result["tenbagger_risks"])
        self.assertLess(result["tenbagger_score"], 45)


if __name__ == "__main__":
    unittest.main()
