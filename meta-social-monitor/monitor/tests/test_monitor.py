"""Rules, Salesforce adapter and sync record builder against the mock data. No network."""
import json
import unittest
from datetime import date
from pathlib import Path

import yaml

from monitor.anomalies import analyze
from monitor.mock import mock_data
from monitor.salesforce_report import build_salesforce_report
from sync.salesforce_social_sync import build_records

ROOT = Path(__file__).resolve().parents[2]
REPORT_DAY = date(2026, 10, 20)


def build():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    rows, posts = mock_data(REPORT_DAY, cfg["report"]["lookback_days"], cfg["report"]["post_window_days"])
    stats, flags = analyze(rows, posts, REPORT_DAY, cfg)
    report = build_salesforce_report(REPORT_DAY, stats, flags, rows, posts, "Check Facebook reach first.",
                                     generated_at="2026-10-21T12:00:00Z")
    return cfg, rows, posts, stats, flags, report


class RulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.rows, cls.posts, cls.stats, cls.flags, cls.report = build()
        cls.by_rule = {(f.account, f.rule): f for f in cls.flags}

    def test_planted_anomalies_fire(self):
        rules = {(f.account, f.rule) for f in self.flags}
        self.assertIn(("HiRoad (facebook)", "reach_drop"), rules)
        self.assertIn(("hiroad (instagram)", "unfollow_spike"), rules)
        self.assertIn(("hiroad (instagram)", "hot_post"), rules)
        self.assertEqual(self.by_rule[("HiRoad (facebook)", "reach_drop")].severity, "critical")
        self.assertEqual(self.by_rule[("hiroad (instagram)", "hot_post")].severity, "info")

    def test_no_false_positives(self):
        rules = {(f.account, f.rule) for f in self.flags}
        for bad in (("hiroad (instagram)", "reach_drop"), ("HiRoad (facebook)", "unfollow_spike"),
                    ("HiRoad (facebook)", "posting_gap"), ("hiroad (instagram)", "data_gap")):
            self.assertNotIn(bad, rules)

    def test_missing_metric_is_a_data_gap_not_a_drop(self):
        rows = [dict(r, reach=None) if (r["platform"] == "instagram" and r["date"] == REPORT_DAY) else r for r in self.rows]
        _, flags = analyze(rows, self.posts, REPORT_DAY, self.cfg)
        rules = {(f.account, f.rule) for f in flags}
        self.assertIn(("hiroad (instagram)", "data_gap"), rules)
        self.assertNotIn(("hiroad (instagram)", "reach_drop"), rules)

    def test_stats_basics(self):
        fb = next(s for s in self.stats if s.platform == "facebook")
        self.assertEqual(len(fb.reach_series), 35)
        self.assertIsNotNone(fb.followers)
        self.assertGreater(fb.reach_baseline, 1000)
        self.assertLess(fb.vs_baseline_pct, -0.5)


class SalesforceReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.rows, cls.posts, cls.stats, cls.flags, cls.report = build()
        cls.recs = build_records(cls.report)

    def test_contract_and_records(self):
        r = self.report
        self.assertEqual(set(r), {"report_date", "generated_at", "summary", "accounts", "posts"})
        self.assertEqual(len(r["accounts"]), 2)
        self.assertEqual(len(r["posts"]), 12)
        json.dumps(r)  # serializable: dates already strings
        metrics = {m["Platform__c"]: m for m in self.recs["metrics"]}
        self.assertEqual(metrics["Facebook"]["Alert_Level__c"], "Critical")
        self.assertEqual(metrics["Instagram"]["Alert_Level__c"], "Warning")   # unfollow spike; hot post is info only
        self.assertEqual(metrics["Facebook"]["Metric_Key__c"], "2026-10-20|facebook|1000001")
        self.assertEqual(metrics["Facebook"]["Run__r"], {"Run_Key__c": "2026-10-20"})
        self.assertEqual(len(json.loads(metrics["Facebook"]["Daily_Reach__c"])), 35)
        self.assertIsNotNone(metrics["Instagram"]["Website_Clicks__c"])
        self.assertIsNone(metrics["Facebook"]["Website_Clicks__c"])
        run = self.recs["run"]
        self.assertEqual(run["Overall_Status__c"], "Critical")
        self.assertEqual(run["Critical_Alerts__c"], sum(1 for f in self.flags if f.severity == "critical"))
        self.assertEqual(run["Warning_Alerts__c"], sum(1 for f in self.flags if f.severity == "warning"))
        self.assertEqual(run["Accounts__c"], 2)
        self.assertEqual(run["Posts_In_Window__c"], 12)
        post = self.recs["posts"][0]
        self.assertTrue(post["Post_Key__c"].startswith(("facebook|", "instagram|")))
        self.assertRegex(post["Published_At__c"], r"Z$")
        self.assertLessEqual(len(post["Name"]), 80)

    def test_no_identities(self):
        text = json.dumps(self.report).lower()
        for needle in ("commenter", "subscriberkey", "@example.com", "user_id"):
            self.assertNotIn(needle, text)

    def test_bad_platform_rejected(self):
        bad = dict(self.report, accounts=[dict(self.report["accounts"][0], platform="tiktok")])
        with self.assertRaises(ValueError):
            build_records(bad)


if __name__ == "__main__":
    unittest.main()
