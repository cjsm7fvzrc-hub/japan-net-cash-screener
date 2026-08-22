import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from catalyst_analysis import evaluate_catalysts


class CatalystAnalysisTests(unittest.TestCase):
    def test_strong_change_signal(self):
        result = evaluate_catalysts({
            "quarterly_revenue_growth": 0.28,
            "revenue_cagr_3y": 0.12,
            "quarterly_operating_income_growth": 0.55,
            "operating_income_cagr_3y": 0.18,
            "operating_margin_change": 0.04,
            "forward_eps_growth": 0.30,
            "volume_ratio_20d": 1.8,
            "return_52w": 0.15,
            "net_cash_ratio": 0.5,
        })
        self.assertGreaterEqual(result["catalyst_score"], 70)
        self.assertEqual(result["revision_signal"], "上方修正兆候・強")
        self.assertEqual(result["transformation_signal"], "利益構造が変化")

    def test_does_not_claim_revision_without_signals(self):
        result = evaluate_catalysts({
            "quarterly_revenue_growth": -0.05,
            "quarterly_operating_income_growth": -0.2,
            "forward_eps_growth": -0.1,
            "operating_margin_change": -0.04,
        })
        self.assertEqual(result["revision_signal"], "明確な兆候なし")
        self.assertIn("直近四半期売上が前年同期比で減少", result["catalyst_checks"])

    def test_operating_profit_turnaround_is_detected(self):
        result = evaluate_catalysts({"operating_profit_turnaround": True})
        self.assertEqual(result["transformation_signal"], "営業黒字へ転換")
        self.assertIn("直近四半期の営業利益が黒字転換", result["catalyst_signals"])

    def test_acceleration_is_calculated_against_long_term_growth(self):
        result = evaluate_catalysts({
            "quarterly_revenue_growth": 0.18,
            "revenue_cagr_3y": 0.08,
            "quarterly_operating_income_growth": 0.25,
            "operating_income_cagr_3y": 0.10,
        })
        self.assertAlmostEqual(result["revenue_acceleration"], 0.10)
        self.assertAlmostEqual(result["operating_income_acceleration"], 0.15)


if __name__ == "__main__":
    unittest.main()
