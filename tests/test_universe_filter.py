import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from universe_filter import eligible_market


class UniverseFilterTests(unittest.TestCase):
    def test_pro_market_is_excluded(self):
        self.assertFalse(eligible_market("PRO Market"))
        self.assertFalse(eligible_market("TOKYO PRO Market"))
        self.assertFalse(eligible_market("  pro   market  "))

    def test_public_markets_remain_eligible(self):
        self.assertTrue(eligible_market("プライム（内国株式）"))
        self.assertTrue(eligible_market("スタンダード（内国株式）"))
        self.assertTrue(eligible_market("グロース（内国株式）"))


if __name__ == "__main__":
    unittest.main()
