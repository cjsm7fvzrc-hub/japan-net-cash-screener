import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model_governance import run


class ModelGovernanceTests(unittest.TestCase):
    def test_snapshot_and_fixed_horizon_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = {
                "version": 1,
                "active_criteria": {"tenbagger_candidate_score_min": 45},
                "review_rules": {"horizons_days": [30, 90], "candidate_limit": 10, "control_limit": 10,
                                 "history_limit_weeks": 10, "minimum_observations_for_proposal": 2},
            }
            stocks = [
                {"code": "1001", "name": "候補", "price": 100, "tenbagger_score": 70, "investment_score": 65, "risk_score": 10},
                {"code": "1002", "name": "対照", "price": 100, "tenbagger_score": 20, "investment_score": 30, "risk_score": 20},
            ]
            paths = {name: root / name for name in ("results.json", "status.json", "history.json", "review.json", "policy.json")}
            paths["results.json"].write_text(json.dumps({"stocks": stocks}), encoding="utf-8")
            paths["status.json"].write_text(json.dumps({"state": "completed"}), encoding="utf-8")
            paths["policy.json"].write_text(json.dumps(policy), encoding="utf-8")
            start = datetime(2026, 1, 5, tzinfo=timezone.utc)
            run(paths["results.json"], paths["status.json"], paths["history.json"], paths["review.json"], paths["policy.json"], start)
            stocks[0]["price"], stocks[1]["price"] = 130, 105
            paths["results.json"].write_text(json.dumps({"stocks": stocks}), encoding="utf-8")
            review = run(paths["results.json"], paths["status.json"], paths["history.json"], paths["review.json"], paths["policy.json"], start + timedelta(days=31))
            self.assertEqual(review["snapshot_count"], 2)
            self.assertEqual(review["horizons"][0]["candidates"]["average_return"], 0.3)
            self.assertEqual(review["horizons"][0]["control"]["average_return"], 0.05)
            self.assertEqual(review["horizons"][0]["excess_return"], 0.25)
            history = json.loads(paths["history.json"].read_text(encoding="utf-8"))
            self.assertIn("30", history["snapshots"][0]["outcomes"])

    def test_quality_outlier_becomes_proposal_without_auto_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = {"version": 1, "active_criteria": {"tenbagger_candidate_score_min": 45},
                      "review_rules": {"horizons_days": [30], "candidate_limit": 5,
                      "control_limit": 5, "history_limit_weeks": 5, "minimum_observations_for_proposal": 2}}
            results = {"stocks": [{"code": "9999", "name": "異常", "price": 100,
                                    "tenbagger_score": 50, "dividend_yield": 99}]}
            for name, value in (("results.json", results), ("status.json", {"state": "running"}), ("policy.json", policy)):
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            review = run(root / "results.json", root / "status.json", root / "history.json",
                         root / "review.json", root / "policy.json", datetime(2026, 1, 5, tzinfo=timezone.utc))
            self.assertEqual(review["current_quality"]["anomalies"][0]["field"], "配当利回り")
            self.assertEqual(review["proposals"][0]["status"], "承認待ち")
            self.assertFalse(review["safety"]["automatic_changes"])


if __name__ == "__main__":
    unittest.main()
