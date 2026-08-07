import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.analytics_report import aggregate_hits, build_report, parse_entity_path


class AnalyticsReportTests(unittest.TestCase):
    def test_parse_only_entity_click_paths(self):
        self.assertEqual(
            parse_entity_path("entity/click/inline/company/nvidia"),
            {"surface": "inline", "kind": "company", "slug": "nvidia"},
        )
        self.assertIsNone(parse_entity_path("read/article-1"))

    def test_aggregate_groups_entities_and_surfaces(self):
        rows, surfaces = aggregate_hits([
            {"path": "entity/click/inline/company/nvidia", "count": 4, "unique": 3},
            {"path": "entity/click/inline/company/nvidia", "count": 2, "unique": 2},
            {"path": "entity/click/chip/person/elon_musk", "count": 1, "unique": 1},
            {"path": "read/article-1", "count": 99, "unique": 99},
        ])
        self.assertEqual(rows[0], {"kind": "company", "slug": "nvidia", "clicks": 6, "visitors": 5})
        self.assertEqual(surfaces, [("inline", 6), ("chip", 1)])

    def test_report_has_ranked_dashboard_sections(self):
        rows, surfaces = aggregate_hits([
            {"path": "entity/click/inline/company/nvidia", "count": 4, "unique": 3},
        ])
        report = build_report(rows, surfaces, date(2026, 8, 1), date(2026, 8, 8), {"nvidia": "NVIDIA"})
        self.assertIn("인기 엔티티", report)
        self.assertIn("NVIDIA", report)
        self.assertIn("| inline | 4 |", report)


if __name__ == "__main__":
    unittest.main()
