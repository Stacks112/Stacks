# -*- coding: utf-8 -*-
"""Apply the v50 debate-board patch to index.html.

Run by .github/workflows/apply-v50.yml (workflow_dispatch).
Every needle must appear EXACTLY once in index.html; otherwise the
script aborts and nothing is written, so a drifted file can't be
half-patched. Safe to re-run: if the file is already v50 it exits 0.
"""

import io
import sys

PATH = "index.html"

STANCE_BLOCK = '''let ITEMS = [];
let SERIES = {};
let EVENTS = [];
let ENTITIES = {};

/* ---------------- stance map (bull / bear / context) ----------------
   Which way each item leans on its main ticker. Drives the debate
   board on entity (company) pages. If an item in items.json carries
   its own "stance" field ("bull"|"bear"|"watch"), that wins; this map
   covers the back catalogue. */
const STANCE = {
  "serenity-meritz-memory":"bull","meru-adr-conv":"bull","hynix":"bull",
  "meru-battery-triple":"bull","ess":"bull","potus-datacenters":"bull",
  "doomberg-kilby":"bull","optics":"bull","cook-broadcom":"bull",
  "emin-korea":"bear","meru-leverage":"bear","doomberg-bloom":"bear",
  "netinterest-stretch":"bear",
  "meru-china-ai":"watch","meru-anthropic-alibaba":"watch","doomberg-sources":"watch",
  "karakama-nikkei":"watch","testa-nikkei":"watch","meru-redsea":"watch",
  "hassabis-framework":"watch","netinterest-nse":"watch","marks-privatecredit":"watch",
  "nbis":"watch","hormuz-meru":"watch","potus-hormuz":"watch","nadella":"watch","zuck":"watch"
};'''

CSS_BLOCK = '''/* ---------- stance pill + debate board ---------- */
.stance-pill{
  font-family:"Inter","Pretendard Variable",sans-serif;
  font-size:10px;font-weight:800;letter-spacing:.02em;
  border-radius:999px;padding:3px 9px;white-space:nowrap;
}
html[data-lang="ko"] .stance-pill{font-family:"Pretendard Variable",sans-serif;}
.sp-bull{color:#087443;background:rgba(18,183,106,.13);border:1px solid rgba(18,183,106,.35);}
.sp-bear{color:#B42318;background:rgba(240,68,56,.12);border:1px solid rgba(240,68,56,.32);}
.sp-watch{color:var(--muted);background:var(--bg-soft);border:1px solid var(--line);}
.debate-bar{background:var(--bg-soft);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-bottom:14px;}
.debate-title{
  font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;
}
html[data-lang="ko"] .debate-title,html[data-lang="ja"] .debate-title{
  font-family:inherit;letter-spacing:.01em;text-transform:none;font-size:12.5px;font-weight:800;color:var(--text);
}
.debate-track{display:flex;gap:6px;height:40px;}
.debate-seg{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  border-radius:10px;min-width:54px;color:#fff;line-height:1.05;padding:0 6px;
}
.debate-seg span{font-size:10px;font-weight:700;opacity:.95;}
.debate-seg b{font-size:15px;font-weight:800;}
.ds-bull{background:linear-gradient(135deg,#12B76A,#087443);}
.ds-bear{background:linear-gradient(135deg,#F04438,#B42318);}
.ds-watch{background:linear-gradient(135deg,#9BA1B0,#6B7280);}
.debate-group-head{display:flex;align-items:center;gap:8px;margin:20px 0 12px;font-size:15px;font-weight:800;letter-spacing:-.01em;}
.debate-group-head .dg-dot{width:10px;height:10px;border-radius:50%;flex:0 0 10px;}
.debate-group-head .dg-n{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:700;color:var(--muted);}
.dg-bull .dg-dot{background:#12B76A;} .dg-bear .dg-dot{background:#F04438;} .dg-watch .dg-dot{background:#9BA1B0;}
.dg-bull{color:#087443;} .dg-bear{color:#B42318;} .dg-watch{color:var(--muted);}
html[data-theme="dark"] .dg-bull{color:#34D399;} html[data-theme="dark"] .dg-bear{color:#FDA29B;}
html[data-theme="dark"] .sp-bull{color:#6EE7B7;} html[data-theme="dark"] .sp-bear{color:#FDA29B;}

/* ---------- dark mode ---------- */'''

HELPERS_BLOCK = '''/* ---------------- stance (bull / bear / context) ---------------- */
function stanceMeta(s){
  const S = STRINGS[LANG];
  if (s === "bull") return { key: "bull", label: S.stanceBull };
  if (s === "bear") return { key: "bear", label: S.stanceBear };
  return { key: "watch", label: S.stanceWatch };
}
/* item's own field wins; else the STANCE map; null = untagged */
function itemStance(item){
  const s = item.stance || STANCE[item.id];
  return (s === "bull" || s === "bear") ? s : (s ? "watch" : null);
}
function stancePillHtml(item){
  const s = itemStance(item);
  if (!s) return "";
  const m = stanceMeta(s);
  return '<span class="stance-pill sp-' + m.key + '">' + m.label + '</span>';
}
/* Entity debate board: scoreboard + bull/bear/context groups */
function renderEntityDebate(list, items, S){
  if (!items.length){
    const em = document.createElement("div");
    em.className = "empty";
    em.textContent = S.empty;
    list.appendChild(em);
    return;
  }
  const groups = { bull: [], bear: [], watch: [] };
  items.forEach(i => { groups[itemStance(i) || "watch"].push(i); });
  const counts = { bull: groups.bull.length, bear: groups.bear.length, watch: groups.watch.length };
  const bar = document.createElement("div");
  bar.className = "debate-bar";
  bar.innerHTML = '<div class="debate-title">' + S.debateTitle + '</div>'
    + '<div class="debate-track">'
    + ["bull", "bear", "watch"].map(k => counts[k]
        ? '<div class="debate-seg ds-' + k + '" style="flex:' + counts[k] + '"><span>' + stanceMeta(k).label + '</span><b>' + counts[k] + '</b></div>'
        : "").join("")
    + '</div>';
  list.appendChild(bar);
  ["bull", "bear", "watch"].forEach(k => {
    if (!groups[k].length) return;
    const gh = document.createElement("div");
    gh.className = "debate-group-head dg-" + k;
    gh.innerHTML = '<span class="dg-dot"></span>' + stanceMeta(k).label
      + '<span class="dg-n">' + groups[k].length + '</span>';
    list.appendChild(gh);
    groups[k].forEach((item, idx) => {
      const el = cardEl(item, S, idx);
      list.appendChild(el);
      linkifyEntities(el);
    });
  });
}
function chipHtml(tag){'''

PICK_COMPANY_NEW = '''function pickCompany(name){
  /* a known company opens its debate page; anything else is a text search */
  if (name && ENTITIES[name] && ENTITIES[name].kind === "company"){
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";
    const inp0 = document.getElementById("searchInput"); if (inp0) inp0.value = "";
    ENTITY_VIEW = name;
    renderFeed(true);
    return;
  }
  const inp = document.getElementById("searchInput");
  if (inp) inp.value = name;
  onSearch(name);
}'''

CHIPTAP_NEW = '''  el.classList.remove("show");
  if (ENTITIES[tag]){
    /* known company/person/term -> open its debate/entity page */
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";
    const inp1 = document.getElementById("searchInput"); if (inp1) inp1.value = "";
    ENTITY_VIEW = tag;
    renderFeed(true);
  } else {
    const inp = document.getElementById("searchInput");
    if (inp) inp.value = tag;
    onSearch(tag);
  }
  const f = document.getElementById("feed");
  if (f && f.scrollIntoView) f.scrollIntoView({ behavior: "smooth", block: "start" });
}'''

EDITS = [
    # 1. build comment
    ("<!-- STACKS BUILD v49 :: intro shows once; company profile page (logo, facts, long desc) + ranged Google-style chart -->",
     "<!-- STACKS BUILD v50 :: bull/bear debate board on entity pages (stance grouping + scoreboard); company chips/filter open the debate page -->"),
    # 2. STANCE map
    ("let ITEMS = [];\nlet SERIES = {};\nlet EVENTS = [];\nlet ENTITIES = {};",
     STANCE_BLOCK),
    # 3. strings en/ko/ja
    ('    sortHot: "Popular",',
     '    sortHot: "Popular",\n    stanceBull: "Bull", stanceBear: "Bear", stanceWatch: "Context",\n    debateTitle: "The debate",'),
    ('    sortHot: "인기순",',
     '    sortHot: "인기순",\n    stanceBull: "강세", stanceBear: "약세", stanceWatch: "관점",\n    debateTitle: "이 종목을 둘러싼 논쟁",'),
    ('    sortHot: "人気順",',
     '    sortHot: "人気順",\n    stanceBull: "強気", stanceBear: "弱気", stanceWatch: "視点",\n    debateTitle: "この銘柄をめぐる論争",'),
    # 4. CSS (anchored on the dark-mode banner)
    ("/* ---------- dark mode ---------- */", CSS_BLOCK),
    # 5. helpers (anchored on chipHtml)
    ("function chipHtml(tag){", HELPERS_BLOCK),
    # 6. stance pill on cards
    ('        <div class="chips">${item.tags.map(t=>chipHtml(t)).join("")}</div>',
     '        <div class="chips">${stancePillHtml(item)}${item.tags.map(t=>chipHtml(t)).join("")}</div>'),
    # 7. entity view renders the debate board and stops
    ('''    list.appendChild(h);
    if (isCo && e.ticker) ehqLoad(ENTITY_VIEW, "1mo");
  }''',
     '''    list.appendChild(h);
    if (isCo && e.ticker) ehqLoad(ENTITY_VIEW, "1mo");
    renderEntityDebate(list, items, S);
    hydrateImages();
    applyEngageCounts();
    setupViewObserver();
    return;
  }'''),
    # 8a. company filter opens the debate page
    ('''function pickCompany(name){
  const inp = document.getElementById("searchInput");
  if (inp) inp.value = name;
  onSearch(name);
}''', PICK_COMPANY_NEW),
    # 8b. chip tap opens the debate page
    ('''  el.classList.remove("show");
  const inp = document.getElementById("searchInput");
  if (inp) inp.value = tag;
  onSearch(tag);
  const f = document.getElementById("feed");
  if (f && f.scrollIntoView) f.scrollIntoView({ behavior: "smooth", block: "start" });
}''', CHIPTAP_NEW),
]

OPTIONAL_EDITS = [
    ("STACKS BUILD v36</p>", "STACKS BUILD v50</p>"),
]


def main():
    with io.open(PATH, encoding="utf-8") as f:
        html = f.read()

    if "STACKS BUILD v50" in html and "const STANCE" in html:
        print("already v50; nothing to do")
        return 0

    # dry-run: verify every needle occurs exactly once BEFORE touching anything
    problems = []
    for i, (needle, _) in enumerate(EDITS, 1):
        n = html.count(needle)
        if n != 1:
            problems.append("edit %d: needle found %d times (expected 1): %r" % (i, n, needle[:80]))
    if problems:
        for p in problems:
            print("[ABORT] " + p)
        return 1

    for needle, repl in EDITS:
        html = html.replace(needle, repl, 1)
    for needle, repl in OPTIONAL_EDITS:
        if html.count(needle) == 1:
            html = html.replace(needle, repl, 1)
        else:
            print("[warn] optional edit skipped: %r" % needle[:60])

    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("v50 patch applied: %d edits" % len(EDITS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
