"""Regression contracts for the static feed/detail shell.

These checks intentionally stay dependency-free: the production UI is a static
HTML app and the repository does not require a browser runner to validate the
rendering contracts that caused the recent regressions.
"""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
V82 = (ROOT / "assets" / "v82.js").read_text(encoding="utf-8")
V82_CSS = (ROOT / "assets" / "v82.css").read_text(encoding="utf-8")
ITEMS = json.loads((ROOT / "items.json").read_text(encoding="utf-8"))
SECURITY_POLICY = json.loads(
    (ROOT / "ops" / "cloudflare-response-headers.json").read_text(encoding="utf-8")
)


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

    def test_x_embed_keeps_a_hidden_slot_when_live_widget_fails(self):
        self.assertIn('const slot = host.querySelector(".xreal-slot") || document.createElement("div");', INDEX)
        self.assertIn("slot.replaceChildren();", INDEX)
        self.assertIn('.xreal.x-on > .xemb{display:none;}', INDEX)
        pages = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        self.assertIn('.xreal.x-on>.xemb{display:none}', pages)

        app_x_iframe_css = next(
            line for line in INDEX.splitlines()
            if line.startswith('.xreal.x-on>.xreal-slot iframe{')
        )
        static_x_iframe_css = next(
            line for line in pages.splitlines()
            if line.startswith('.xreal.x-on>.xreal-slot iframe{')
        )
        self.assertNotIn('height:auto', app_x_iframe_css.replace(' ', ''))
        self.assertNotIn('height:auto', static_x_iframe_css.replace(' ', ''))
        self.assertIn('position:absolute', INDEX)
        self.assertIn('position:absolute', pages)

    def test_feed_x_cards_render_widget_not_source_teaser(self):
        start = INDEX.index("function srcBlockHtml(item, full)")
        end = INDEX.index("window.expandArticleSource", start)
        source_block = INDEX[start:end]
        self.assertLess(
            source_block.index("if (e && (e.lines || []).length)"),
            source_block.index("if (!full && !picked)"),
        )
        self.assertIn('class="xreal"', source_block)
        self.assertIn('class="srcq srcq-teaser"', source_block)
        self.assertIn(
            'html.v83 #feedList .card-body > [data-source-shell]{ order:10; }',
            INDEX,
        )
        self.assertIn(
            '.card .card-body > [data-source-shell]{order:10;}',
            V82_CSS,
        )

    def test_feed_source_quotes_render_without_detail_mode(self):
        start = INDEX.index("function srcBlockHtml(item, full)")
        end = INDEX.index("window.expandArticleSource", start)
        source_block = INDEX[start:end]
        self.assertLess(
            source_block.index("const picked = q && quoteLines(q.lines, LANG, slang);"),
            source_block.index("if (!full && !picked)"),
        )
        self.assertIn("if (picked){", source_block)

    def test_x_embed_binds_rendered_before_create(self):
        start = INDEX.index("async function xEmbedMount(host)")
        end = INDEX.index("setInterval(xEmbedScan", start)
        app_embed = INDEX[start:end]
        self.assertLess(
            app_embed.index('tw.events.bind("rendered"'),
            app_embed.index("await tw.widgets.createTweet"),
        )
        self.assertIn("slot.contains(e.target)", app_embed)
        self.assertIn('if (!el || !slot.querySelector("iframe")) { abandon(); return; }\n    reveal();', app_embed)
        self.assertIn('slot.querySelector(".twitter-tweet-rendered")', app_embed)
        self.assertIn('frame.getBoundingClientRect().height <= 1', app_embed)
        self.assertIn('frame.style.visibility = "visible"', app_embed)
        self.assertNotIn('frame.style.removeProperty("height")', app_embed)

        pages = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        start = pages.index("X_LIVE_SCRIPT =")
        static_embed = pages[start:pages.index("\n\n\ndef x_embed_block", start)]
        self.assertLess(
            static_embed.index("twttr.events.bind('rendered'"),
            static_embed.index("Promise.resolve(twttr.widgets.createTweet"),
        )
        self.assertIn("slot.contains(e.target)", static_embed)
        self.assertIn("if (!node || !slot.querySelector('iframe')) { abandon(); return; }\n          reveal();", static_embed)
        self.assertIn("slot.querySelector('.twitter-tweet-rendered')", static_embed)
        self.assertIn("frame.getBoundingClientRect().height <= 1", static_embed)
        self.assertIn("frame.style.visibility = 'visible'", static_embed)
        self.assertNotIn("frame.style.removeProperty('height')", static_embed)

    def test_judgment_record_filter_and_evidence_contracts(self):
        self.assertIn('.jr-quick', INDEX)
        self.assertIn('data-jr-quick', INDEX)
        self.assertIn('s[0]', INDEX)
        self.assertIn("aria-pressed=\"'+(quickFilter===s[0]?'true':'false')+'\"", INDEX)
        self.assertIn("var quickPool=function(key)", INDEX)
        self.assertIn('data-jr-search="', INDEX)
        self.assertIn('class="jr-evidence"', INDEX)
        self.assertIn("Array.isArray(i.outcome.evidence)", INDEX)
        self.assertIn("safeUrl(e.url)", INDEX)
        self.assertIn("var byTopic={};", INDEX)
        self.assertIn("var topicRows=topics.map", INDEX)
        self.assertIn('class="jr-breakdown-title"', INDEX)
        self.assertIn("topicBreakdown", INDEX)
        self.assertIn("var byMonth={};", INDEX)
        self.assertIn("var trendMarkup=function", INDEX)
        self.assertIn('class="jr-trend"', INDEX)
        self.assertIn("trendSub", INDEX)
        self.assertIn("gradedDateLabel", INDEX)
        self.assertIn("i.outcome.gradedOn", INDEX)

    def test_linkify_queue_prioritizes_visible_cards_during_idle_time(self):
        self.assertIn("requestIdleCallback(linkifyDrain", INDEX)
        self.assertIn("__linkifyPending", INDEX)
        self.assertIn("linkifyDistance", INDEX)
        self.assertIn("getBoundingClientRect", INDEX)

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

    def test_sitemap_contains_canonical_week_url_only(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("https://stacksdaily.com/this-week.html", sitemap)
        self.assertIn("https://stacksdaily.com/week/", sitemap)

    def test_thin_hub_pages_are_kept_for_navigation_but_not_indexed(self):
        pages = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")

        self.assertIn("RECORD_MIN_ARTICLES = 3", pages)
        self.assertIn("THEME_MIN_ARTICLES = 3", pages)
        self.assertIn("theme_written", pages)
        self.assertIn("record_written", pages)
        self.assertIn('robots=None if theme_indexable else "noindex,follow"', pages)
        self.assertIn('robots=None if record_indexable else "noindex,follow"', pages)
        self.assertIn('robots_meta = (f\'<meta name="robots" content="{E(robots)}">\' if robots else "")', pages)
        self.assertIn("theme_indexable = len(t_items) >= THEME_MIN_ARTICLES", pages)
        self.assertIn("if record_indexable:", pages)

    def test_investor_rail_gate_matches_render_dispatch(self):
        self.assertIn("function invViewActive()", INDEX)
        self.assertIn('if (invViewActive()){ renderInvestors(list,S);', INDEX)
        self.assertIn('_railEl.classList.toggle("inv-rail-hide", invViewActive())', INDEX)
        self.assertIn('document.documentElement.classList.toggle("inv-wide", invViewActive())', INDEX)
        self.assertIn('serviceWorkers: "block"', (ROOT / "tests" / "feed-detail.spec.mjs").read_text(encoding="utf-8"))

    def test_mobile_calendar_toggle_contract(self):
        self.assertIn('id = "v82cal-h"', V82)
        self.assertIn('class="v82cal-month-btn"', V82)
        self.assertIn('"v82cal-month-mode"', V82)
        self.assertIn('v82CalPickDay(tcalYmd(new Date()), "auto");', V82)

    def test_home_accessibility_contracts(self):
        self.assertIn('<main class="wrap">', INDEX)
        self.assertIn('id="eg-view-${item.id}"', INDEX)
        self.assertIn('function egLabel(buttonId, label, val)', INDEX)
        self.assertIn('aria-label="${esc(S.views + (VIEW_COUNTS[item.id] ?', INDEX)
        self.assertIn('egLabel("lk-" + id, (STRINGS[LANG] || STRINGS.en).like', INDEX)
        self.assertIn('egLabel("eg-view-" + id, (STRINGS[LANG] || STRINGS.en).views', INDEX)
        self.assertIn('var requested = langParam();', INDEX)
        self.assertIn('.prediction-result-verdict span{font-size:10.5px;opacity:1;}', INDEX)
        self.assertIn('class="foot-copy" style="margin-top:8px;font-size:11px;opacity:1"', INDEX)
        self.assertIn('html.v83 #railFoot .rf-c{ display:block; margin-top:3px; opacity:1; }', INDEX)
        self.assertIn('.since .since-p.up{color:#06703D;}', INDEX)
        self.assertIn("+ '<b class=\"since-p ' + (up ? \"up\" : \"down\") + '\">'", INDEX)


    def test_paywall_disclosure_and_keyboard_contracts(self):
        self.assertIn("paywallPreviewNote", INDEX)
        self.assertIn("function hasPublicExcerpt(item)", INDEX)
        self.assertIn("function paywallDisclosure(item, S)", INDEX)
        self.assertIn('role="button" tabindex="0" aria-label=', INDEX)
        self.assertIn('onkeydown="togglePaywallBadge(this, event)"', INDEX)
        self.assertIn("function togglePaywallBadge(el, e)", INDEX)

    def test_paywall_editorial_gate_contract(self):
        editorial = (ROOT / "scripts" / "check_editorial.py").read_text(encoding="utf-8")
        self.assertIn("def paywall_gate(items, strict=False):", editorial)
        self.assertIn("--paywall-strict", editorial)
        self.assertIn("quote.lines가 없다", editorial)

    def test_entity_websites_are_absolute_and_generated_links_are_safe(self):
        for key, entity in (ITEMS.get("entities") or {}).items():
            website = entity.get("website")
            if website:
                self.assertRegex(website, r"^https?://", key)

        pages = list((ROOT / "e").glob("**/*morgan-stanley.html"))
        self.assertEqual(len(pages), 3)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertNotIn('href="morganstanley.com"', html)
            self.assertIn('href="https://morganstanley.com"', html)

    def test_runtime_avatar_path_skips_unavatar(self):
        self.assertIn("function isUnavatarUrl(url)", INDEX)
        self.assertIn('return isUnavatarUrl(raw) ? "" : raw;', INDEX)
        self.assertIn("&& !isUnavatarUrl(av)", INDEX)
        self.assertNotIn("https://unavatar.io/", INDEX)

    def test_keyboard_and_form_accessibility_contracts(self):
        self.assertIn("function activateKey(e)", INDEX)
        self.assertIn('span.setAttribute("role", "button")', INDEX)
        self.assertIn('span.setAttribute("tabindex", "0")', INDEX)
        self.assertIn('span.setAttribute("onkeydown", "activateKey(event)")', INDEX)
        self.assertIn('role="button" tabindex="0" onkeydown="activateKey(event)"', INDEX)
        self.assertIn('id="v83Search"', INDEX)
        self.assertIn('aria-label="Search"', INDEX)
        self.assertIn('aria-label="Email"', INDEX)
        self.assertIn("data-nle aria-label=\"'+t.ph+'\"", (ROOT / "assets" / "v83tw.js").read_text(encoding="utf-8"))
        self.assertIn("@media (min-width:1024px){ .engage .eg{min-width:44px;min-height:44px;justify-content:center;} }", INDEX)

    def test_lighthouse_a11y_regressions_have_static_guards(self):
        self.assertIn("color:#005FCC;border:1px solid #005FCC", INDEX)
        self.assertIn('html[data-theme="dark"] .new-pill{color:#6CAEFF;border-color:#6CAEFF;}', INDEX)
        self.assertIn(".card.v82c.v82clip .gist .gcardw{display:none;}", V82_CSS)

    def test_onesignal_tags_retry_and_reconcile(self):
        self.assertIn("const OS_TAG_DELAYS = [300, 1000, 3000]", INDEX)
        self.assertIn("async function osApplyTag(OS, key, on)", INDEX)
        self.assertIn("await OS.User.addTag(key, \"1\")", INDEX)
        self.assertIn("await OS.User.removeTag(key)", INDEX)
        self.assertIn('await osApplyTag(OneSignal, "daily", true)', INDEX)
        self.assertIn('for (const key of WATCH)', INDEX)

    def test_initial_data_is_chunked_and_idle_loaded(self):
        self.assertIn("let ITEM_BY_ID = new Map()", INDEX)
        self.assertIn("async function loadGists(maxChunks = 1)", INDEX)
        self.assertIn("scheduleGistPrefetch();", INDEX)
        self.assertIn("requestIdleCallback(run", INDEX)
        self.assertIn("const neededChunk = Math.floor", INDEX)
        self.assertIn('dataUrl("entities.json")', INDEX)
        self.assertIn('dataUrl("events.json")', INDEX)
        core = json.loads((ROOT / "data" / "core.json").read_text(encoding="utf-8"))
        self.assertNotIn("entities", core)
        self.assertNotIn("events", core)
        self.assertTrue((ROOT / "data" / "entities.json").exists())
        self.assertTrue((ROOT / "data" / "events.json").exists())

    def test_static_pages_have_main_landmarks(self):
        pages = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        self.assertEqual(pages.count("<main>"), 6)
        self.assertEqual(pages.count("</main>"), 6)
        for path in (
            ROOT / "about.html",
            ROOT / "privacy.html",
            ROOT / "week" / "2026-w29.html",
            ROOT / "week" / "2026-w30.html",
            ROOT / "week" / "2026-w31.html",
        ):
            html = path.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"<main(?:\s|>)", html)), 1, path.name)
            self.assertEqual(len(re.findall(r"<h1(?:\s|>)", html)), 1, path.name)

    def test_cloudflare_security_policy_is_complete(self):
        headers = SECURITY_POLICY["headers"]
        for name in (
            "Strict-Transport-Security",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Content-Security-Policy-Report-Only",
        ):
            self.assertIn(name, headers)
        self.assertIn("http_response_headers_transform", (ROOT / "scripts" / "apply_cloudflare_response_headers.mjs").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
