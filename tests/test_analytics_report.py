import unittest
from datetime import date
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.analytics_report import aggregate_hits, api_url, build_report, event_path_ids, parse_entity_path


class AnalyticsReportTests(unittest.TestCase):
    def test_api_url_uses_goatcounter_hit_limit(self):
        query = parse_qs(urlparse(api_url("https://stacks.goatcounter.com", date(2026, 8, 1), date(2026, 8, 8))).query)
        self.assertEqual(query["limit"], ["100"])

    def test_api_url_repeats_include_paths(self):
        query = parse_qs(urlparse(api_url(
            "https://stacks.goatcounter.com",
            date(2026, 8, 1),
            date(2026, 8, 8),
            [101, 202],
        )).query)
        self.assertEqual(query["include_paths"], ["101", "202"])
        self.assertEqual(query["limit"], ["100"])

    def test_event_path_ids_select_entity_events_only(self):
        self.assertEqual(event_path_ids([
            {"id": 101, "event": True, "path": "entity/click/inline/company/nvidia"},
            {"id": 102, "event": True, "path": "read/article-1"},
            {"id": 103, "event": False, "path": "entity/click/inline/company/apple"},
            {"id": 104, "path": "entity/click/inline/company/tesla"},
        ]), [101])

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
