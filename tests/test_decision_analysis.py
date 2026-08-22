import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from decision_analysis import evaluate_decision


class DecisionAnalysisTests(unittest.TestCase):
    def test_high_quality_candidate_with_low_risk(self):
        row = {
            "tenbagger_score": 82, "catalyst_score": 75, "market_cap": 20e9,
            "per": 14, "pbr": 1.2, "net_cash_ratio": 0.8,
            "operating_cash_flow": 20, "net_income": 18,
            "current_assets": 100, "liabilities": 40,
            "revenue_cagr_3y": 0.18, "quarterly_revenue_growth": 0.24,
            "quarterly_operating_income_growth": 0.35, "operating_margin_change": 0.03,
            "forward_eps_growth": 0.22, "forward_eps": 120, "volume_ratio_20d": 1.5,
        }
        result = evaluate_decision(row)
        self.assertGreaterEqual(result["investment_score"], 70)
        self.assertEqual(result["risk_level"], "低")
        self.assertEqual(result["investment_decision"], "重点調査候補")

    def test_cash_burn_and_weak_balance_sheet_raise_risk(self):
        result = evaluate_decision({
            "operating_cash_flow": -10, "net_income": 5,
            "current_assets": 50, "liabilities": 90, "net_cash_ratio": -0.4,
            "quarterly_revenue_growth": -0.2,
            "quarterly_operating_income_growth": -0.3,
            "operating_margin_change": -0.05,
        })
        self.assertGreaterEqual(result["risk_score"], 55)
        self.assertEqual(result["risk_level"], "高")

    def test_low_coverage_requires_more_data(self):
        result = evaluate_decision({"tenbagger_score": 90, "catalyst_score": 90})
        self.assertEqual(result["investment_decision"], "データ補完を優先")


if __name__ == "__main__":
    unittest.main()
