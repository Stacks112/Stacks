"""Regression contracts for the static feed/detail shell.

These checks intentionally stay dependency-free: the production UI is a static
HTML app and the repository does not require a browser runner to validate the
rendering contracts that caused the recent regressions.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
V82 = (ROOT / "assets" / "v82.js").read_text(encoding="utf-8")


class FrontendContracts(unittest.TestCase):
    def test_card_factory_owns_entity_indexing(self):
        start = INDEX.index("function cardEl(")
        end = INDEX.index("/* ---------------- real X embed", start)
        card_factory = INDEX[start:end]

        self.assertIn("linkifyEntities(el);", card_factory)
        self.assertLess(
            card_factory.index("linkifyEntities(el);"),
            card_factory.rindex("return el;"),
        )
        self.assertNotIn("linkifyEntities(_ac)", INDEX)
        self.assertNotIn("linkifyEntities(resultCard)", INDEX)
        self.assertNotIn("linkifyEntities(plain)", INDEX)

    def test_reader_facing_evidence_blocks_are_indexed(self):
        self.assertIn(
            'h3, .gist, .why p, .srcq, .xemb-body, .gradec, .srcs-list',
            INDEX,
        )
        self.assertIn('track("entity/click/"', INDEX)
        self.assertIn('trackEntityClick(tag, "chip")', INDEX)
        self.assertIn('trackEntityClick(key, "inline")', INDEX)
        self.assertIn('trackEntityClick(key, "glossary")', INDEX)
        self.assertIn("entityClickFeed", INDEX)
        self.assertIn("debate", INDEX)

    def test_all_detail_paths_use_the_card_factory(self):
        detail = INDEX[INDEX.index("/* v83.3: single-article page"):]
        self.assertIn("if (!_ac) _ac = cardEl(_it, S, 0);", detail)
        self.assertIn("list.appendChild(_ac);", detail)

        self.assertIn("window.v82OpenCard = function(id)", V82)
        self.assertIn("if (el){ openDetail(el); return; }", V82)
        self.assertIn("body.appendChild(card);", V82)

    def test_article_deep_link_round_trip(self):
        view_url = INDEX[INDEX.index("function viewUrl"):INDEX.index("function stkSyncUrl")]
        capture = INDEX[INDEX.index("function captureView"):INDEX.index("var CUR_VIEW")]
        deep_start = INDEX.index("function handleDeepLink(){")
        deep_link = INDEX[deep_start:INDEX.index("/* 모바일 상세", deep_start)]

        self.assertIn('if (it) return stkOne("c", it);', view_url)
        self.assertIn("mitem: stkMobileItem()", capture)
        self.assertIn('const c = get("c");', deep_link)
        self.assertIn("openFromCard(c)", deep_link)
        self.assertIn("?c=", (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
