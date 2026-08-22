import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from technical_analysis import evaluate_prices, summarize_technicals


class TechnicalAnalysisTests(unittest.TestCase):
    def test_uptrend_is_detected(self):
        prices = [100 + i * 0.6 for i in range(220)]
        result = evaluate_prices(prices)
        self.assertEqual(result["technical_trend"], "上昇")
        self.assertGreater(result["ma50"], result["ma200"])
        self.assertGreaterEqual(result["technical_score"], 68)

    def test_downtrend_and_drawdown_are_flagged(self):
        result = summarize_technicals({
            "price": 60, "ma20": 70, "ma50": 80, "ma200": 100,
            "rsi14": 25, "volatility_60d": 0.7, "max_drawdown_1y": -0.45,
        })
        self.assertEqual(result["technical_trend"], "下降")
        self.assertIn("1年最大ドローダウンが40%超", result["technical_cautions"])


if __name__ == "__main__":
    unittest.main()
