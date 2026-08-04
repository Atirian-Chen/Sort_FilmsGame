from pathlib import Path
import unittest

from analytics import build_experiment_metrics
from experiments import get_experiment, list_experiments


ROOT = Path(__file__).resolve().parents[1]


class AbTestV310Tests(unittest.TestCase):
    def test_all_active_experiments_have_one_clear_primary_metric(self):
        allowed_metrics = {
            "exposed_builtin_card_open_rate",
            "exposed_start_rate",
            "exposed_completion_rate",
            "exposed_share_or_poster_rate",
        }
        active = list_experiments(active_only=True)
        self.assertEqual(len(active), 5)
        for experiment in active:
            self.assertIn(experiment["primary_metric"], allowed_metrics)
            self.assertEqual(experiment["traffic_allocation"], 1.0)
            self.assertEqual(len(experiment["variants"]), 2)
            self.assertTrue(experiment["started_at"])

    def test_home_card_experiment_uses_exposed_card_open_rate(self):
        payload = {
            "experiment_id": "home_card_cta_copy_v1",
            "variant_id": "rank_top_n",
            "experiments": {"home_card_cta_copy_v1": "rank_top_n"},
        }
        events = [
            {
                "event_name": "experiment_exposed",
                "session_id": "s1",
                "created_at": "2026-08-05T00:00:00Z",
                "payload": payload,
            },
            {
                "event_name": "experiment_exposed",
                "session_id": "s2",
                "created_at": "2026-08-05T00:00:01Z",
                "payload": payload,
            },
            {
                "event_name": "list_opened",
                "session_id": "s1",
                "created_at": "2026-08-05T00:01:00Z",
                "payload": {**payload, "entry_surface": "home_builtin_card"},
            },
            {
                "event_name": "list_opened",
                "session_id": "s2",
                "created_at": "2026-08-05T00:01:01Z",
                "payload": {**payload, "entry_surface": "other_surface"},
            },
        ]
        row = build_experiment_metrics(events)[0]
        self.assertEqual(row["exposed_builtin_card_opened_sessions"], 1)
        self.assertEqual(row["exposed_builtin_card_open_rate"], 0.5)

    def test_v310_docs_and_readme_describe_the_release(self):
        version_doc = (ROOT / "docs" / "version_updates" / "version3.10.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("home_card_cta_copy_v1", version_doc)
        self.assertIn("result_share_cta_copy_v1", version_doc)
        self.assertIn("v3.10", readme)


if __name__ == "__main__":
    unittest.main()
