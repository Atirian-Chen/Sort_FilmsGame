from pathlib import Path
import unittest

from analytics import build_experiment_metrics
from experiments import get_experiment, list_experiments


ROOT = Path(__file__).resolve().parents[1]


class AbTestV38Tests(unittest.TestCase):
    def test_previous_active_experiments_are_closed_with_decisions(self):
        expected_decisions = {
            "post_render_hero_value_v1": "outcome_preview",
            "quick_list_card_framing_v1": "control",
            "douban_collect_entry_cta_v1": "control",
            "home_zero_decision_start_v1": "control",
            "home_duel_teaser_v1": "control",
        }
        for experiment_id, decision_variant_id in expected_decisions.items():
            experiment = get_experiment(experiment_id)
            self.assertEqual(experiment["status"], "paused")
            self.assertEqual(experiment["decision_variant_id"], decision_variant_id)
            self.assertTrue(experiment["ended_at"])

    def test_v38_has_four_active_funnel_stage_experiments(self):
        active_ids = {
            experiment["experiment_id"]
            for experiment in list_experiments(active_only=True)
        }
        self.assertEqual(
            active_ids,
            {
                "home_featured_quick_start_v1",
                "heavy_default_start_v1",
                "sorting_scope_rescue_v1",
                "result_share_bundle_v1",
            },
        )

    def test_experiment_metrics_cover_each_v38_primary_outcome(self):
        experiment_payload = {
            "experiment_id": "result_share_bundle_v1",
            "variant_id": "quick_share_bundle",
            "experiments": {"result_share_bundle_v1": "quick_share_bundle"},
        }
        events = [
            {
                "event_name": "experiment_exposed",
                "session_id": "s1",
                "created_at": "2026-07-24T10:00:00Z",
                "payload": experiment_payload,
            },
            {
                "event_name": "experiment_exposed",
                "session_id": "s2",
                "created_at": "2026-07-24T10:00:01Z",
                "payload": experiment_payload,
            },
            {
                "event_name": "list_selected",
                "session_id": "s1",
                "created_at": "2026-07-24T10:01:00Z",
                "payload": experiment_payload,
            },
            {
                "event_name": "sorting_started",
                "session_id": "s1",
                "created_at": "2026-07-24T10:02:00Z",
                "payload": experiment_payload,
            },
            {
                "event_name": "ranking_completed",
                "session_id": "s1",
                "created_at": "2026-07-24T10:03:00Z",
                "payload": experiment_payload,
            },
            {
                "event_name": "poster_downloaded",
                "session_id": "s1",
                "created_at": "2026-07-24T10:04:00Z",
                "payload": experiment_payload,
            },
        ]
        row = build_experiment_metrics(events)[0]
        self.assertEqual(row["exposed_sessions"], 2)
        self.assertEqual(row["exposed_action_sessions"], 1)
        self.assertEqual(row["exposed_started_sessions"], 1)
        self.assertEqual(row["exposed_completed_sessions"], 1)
        self.assertEqual(row["exposed_share_or_poster_sessions"], 1)
        self.assertEqual(row["exposed_action_rate"], 0.5)
        self.assertEqual(row["exposed_start_rate"], 0.5)
        self.assertEqual(row["exposed_completion_rate"], 0.5)
        self.assertEqual(row["exposed_share_or_poster_rate"], 0.5)

    def test_schema_and_migration_allow_strict_exposure_and_v38_events(self):
        schema = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        migration = (
            ROOT / "supabase" / "migrations" / "20260724_abtest_v38_events.sql"
        ).read_text(encoding="utf-8")
        for event_name in (
            "experiment_exposed",
            "heavy_config_viewed",
            "default_start_clicked",
            "sorting_scope_reduced",
            "result_share_prompt_clicked",
        ):
            self.assertIn(f"'{event_name}'", schema)
            self.assertIn(f"'{event_name}'", migration)


if __name__ == "__main__":
    unittest.main()
