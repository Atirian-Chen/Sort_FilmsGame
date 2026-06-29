from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from launch_copy import FILM_CHALLENGE_TEMPLATES, get_template
from light_list_catalog import (
    DEFAULT_HOME_LIGHT_LIST_IDS,
    LIGHT_LIST_SEGMENTS,
    ROTATION_CANDIDATE_IDS,
    ROTATION_CANDIDATE_TEMPLATES,
)
from light_list_runtime import resolve_home_light_list_state


class LightListCatalogTests(unittest.TestCase):
    def test_catalog_counts_and_unique_ids(self) -> None:
        ids = [str(template["id"]) for template in FILM_CHALLENGE_TEMPLATES]
        self.assertEqual(32, len(ids))
        self.assertEqual(32, len(set(ids)))
        self.assertEqual(9, len(DEFAULT_HOME_LIGHT_LIST_IDS))
        self.assertEqual(24, len(ROTATION_CANDIDATE_IDS))
        self.assertEqual({"spielberg"}, set(DEFAULT_HOME_LIGHT_LIST_IDS) & set(ROTATION_CANDIDATE_IDS))

    def test_rotation_segments_are_balanced(self) -> None:
        segments = Counter(LIGHT_LIST_SEGMENTS[template_id] for template_id in ROTATION_CANDIDATE_IDS)
        self.assertEqual({"director": 8, "actor": 8, "category": 8}, dict(segments))

    def test_templates_have_valid_items_and_top_k(self) -> None:
        for template in FILM_CHALLENGE_TEMPLATES:
            template_id = str(template["id"])
            items = [str(item).strip() for item in template.get("items", [])]
            top_k = int(template.get("top_k", 0) or 0)
            self.assertGreaterEqual(len(items), 8, template_id)
            self.assertLessEqual(len(items), 50, template_id)
            self.assertEqual(len(items), len(set(items)), template_id)
            self.assertIn(top_k, {8, 10}, template_id)
            self.assertLessEqual(top_k, len(items), template_id)
            self.assertIsNotNone(get_template(template_id))

    def test_rotation_candidates_have_runtime_metadata(self) -> None:
        for priority, template in enumerate(ROTATION_CANDIDATE_TEMPLATES, 1):
            self.assertEqual(priority, int(template["pool_priority"]))
            self.assertEqual(LIGHT_LIST_SEGMENTS[str(template["id"])], template["rotation_segment"])

    def test_runtime_roster_requires_nine_known_unique_templates(self) -> None:
        known_ids = [str(template["id"]) for template in FILM_CHALLENGE_TEMPLATES]
        rows = [
            {"template_id": template_id, "display_rank": rank, "is_new": rank <= 3}
            for rank, template_id in enumerate(reversed(DEFAULT_HOME_LIGHT_LIST_IDS), 1)
        ]
        resolved = resolve_home_light_list_state({"rows": rows, "source": "maintenance"}, known_ids)
        self.assertEqual("maintenance", resolved["source"])
        self.assertEqual([row["template_id"] for row in rows], resolved["template_ids"])

        invalid = resolve_home_light_list_state(
            {"rows": rows[:-1] + [{"template_id": "missing", "display_rank": 9}], "source": "previous"},
            known_ids,
        )
        self.assertEqual("static_fallback", invalid["source"])
        self.assertEqual(DEFAULT_HOME_LIGHT_LIST_IDS, invalid["template_ids"])

    def test_rotation_migration_contract_and_schema_sync(self) -> None:
        root = Path(__file__).resolve().parents[1]
        migration = (root / "supabase" / "migrations" / "20260629_light_list_auto_rotation.sql").read_text(encoding="utf-8")
        schema = (root / "supabase_schema.sql").read_text(encoding="utf-8")
        self.assertIn(migration.strip(), schema)
        for required in [
            "pg_advisory_xact_lock",
            "timezone('Asia/Shanghai'",
            "count(distinct nullif(events.session_id, ''))",
            "on conflict on constraint light_list_daily_stats_pkey",
            "v_metric_date >= v_last_rotation_date + 3",
            "interval '24 hours'",
            "interval '21 days'",
            "array['director', 'actor', 'category']",
            "read_home_light_list_roster",
            "9 - count(*)",
            "v_last_metric_date < v_metric_date",
        ]:
            self.assertIn(required, migration)


if __name__ == "__main__":
    unittest.main()
