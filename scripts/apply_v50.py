# -*- coding: utf-8 -*-
"""Apply the debate-board patch (v56) to index.html.

Run by .github/workflows/apply-v50.yml (workflow_dispatch).
Every needle must appear EXACTLY once in index.html; otherwise the
script aborts and nothing is written, so a drifted file can't be
half-patched. Safe to re-run: if the board is already in, exits 0.

The build-comment edit and the entity-view insertion are anchored
structurally (regex / position) so they survive unrelated version
bumps like the v55 AdSense change.
"""

import io
import re
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

STAGE3_JS = r'''/* ---------------- stage3: stance filter + rail debate + CEO profiles + home ---------------- */
let STANCE_FILTER = null, STANCE_FILTER_KEY = null;
function stanceFilterTap(k){
  STANCE_FILTER = (STANCE_FILTER === k) ? null : k;
  STANCE_FILTER_KEY = ENTITY_VIEW;
  renderFeed(false);
}
function railStanceTap(key, k){
  STANCE_FILTER = k; STANCE_FILTER_KEY = key;
  entityFeedView(key);
  const f = document.getElementById("feed");
  if (f && f.scrollIntoView) f.scrollIntoView({ behavior: "smooth", block: "start" });
}
function goHome(ev){
  if (ev && ev.preventDefault) ev.preventDefault();
  SERIES_VIEW = null; ENTITY_VIEW = null; TAB = "all";
  QUERY = ""; BM_ONLY = false; UNREAD_ONLY = false; FREE_ONLY = false;
  STANCE_FILTER = null;
  const inp = document.getElementById("searchInput"); if (inp) inp.value = "";
  render();
  try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
  return false;
}
/* compact debate bar inside the right-rail entity panel */
function railDebateEnhance(key){
  try {
    const panel = document.getElementById("entityRailPanel");
    if (!panel) return;
    const head = panel.querySelector(".entity-head");
    if (!head) return;
    if (!head.querySelector(".debate-bar")){
      const items = ITEMS.filter(i => itemEntities(i).has(key));
      const counts = { bull: 0, bear: 0, watch: 0 };
      items.forEach(i => { counts[itemStance(i) || "watch"]++; });
      if (counts.bull + counts.bear + counts.watch > 0){
        const safe = key.replace(/'/g, "\\'");
        const bar = document.createElement("div");
        bar.className = "debate-bar rail-debate";
        bar.innerHTML = '<div class="debate-title">' + STRINGS[LANG].debateTitle + '</div>'
          + '<div class="debate-track">'
          + ["bull", "bear", "watch"].map(k => counts[k]
              ? '<div class="debate-seg ds-' + k + '" style="flex:' + counts[k] + '" onclick="railStanceTap(\'' + safe + '\',\'' + k + '\')"><span>' + stanceMeta(k).label + '</span><b>' + counts[k] + '</b></div>'
              : "").join("")
          + '</div>';
        const slot = head.querySelector(".eh-desc") || head.querySelector(".eh-sub") || head.querySelector(".eh-top");
        if (slot && slot.nextSibling) head.insertBefore(bar, slot.nextSibling);
        else head.appendChild(bar);
      }
    }
    ceoEnhance(head);
  } catch (e) {}
}
/* ---- CEO mini-profiles: hover = one-liner, click/tap = detail ---- */
const CEO_HINT = { en: "Tap again for details", ko: "한 번 더 탭하면 상세 설명", ja: "もう一度タップで詳細" };
const CEO_INFO = {
  "곽노정": { d: { ko: "SK하이닉스 CEO. 엔지니어 출신으로 HBM을 AI 메모리 1위로 키웠다.", en: "SK hynix CEO; the engineer who drove its HBM lead in AI memory.", ja: "SKハイニックスCEO。HBMをAIメモリ首位に導いた技術者出身。" }, l: { ko: "1994년 입사 후 제조·기술 총괄을 거쳐 2022년 대표이사에 올랐다. 엔비디아향 HBM 공급을 주도해 AI 슈퍼사이클의 중심에 회사를 올려놨다.", en: "Joined in 1994, rose through manufacturing and technology, and became CEO in 2022. Led the Nvidia HBM supply push that put the company at the center of the AI supercycle.", ja: "1994年入社、製造・技術統括を経て2022年CEO就任。NVIDIA向けHBM供給を主導しAIスーパーサイクルの中心に会社を押し上げた。" } },
  "전영현": { d: { ko: "삼성전자 DS(반도체)부문장 겸 부회장. 메모리의 구원투수로 복귀했다.", en: "Samsung vice chairman leading the semiconductor (DS) division.", ja: "サムスン電子DS(半導体)部門トップの副会長。" }, l: { ko: "삼성 메모리 전성기를 이끌었던 베테랑으로, HBM 경쟁력 회복이라는 특명을 받고 2024년 반도체 부문 수장으로 돌아왔다.", en: "A veteran of Samsung's memory heyday, brought back in 2024 to lead the chip division and rebuild its HBM competitiveness.", ja: "サムスンメモリ全盛期を率いたベテラン。HBM競争力回復の特命を受け2024年に半導体部門トップへ復帰。" } },
  "한종희": { d: { ko: "삼성전자 DX(디바이스경험)부문장 겸 부회장. TV·가전·모바일 총괄.", en: "Samsung vice chairman running the device (DX) division.", ja: "サムスン電子DX部門トップの副会長。" }, l: { ko: "TV 개발 엔지니어 출신으로 삼성 TV의 15년 연속 세계 1위를 이끌었고, 지금은 세트 사업 전체를 총괄한다.", en: "A TV engineer who led Samsung's 15-year run as the world's top TV maker; now oversees all consumer devices.", ja: "テレビ開発技術者出身でサムスンTVの15年連続世界首位を牽引。セット事業全体を統括する。" } },
  "젠슨 황": { d: { ko: "엔비디아 창업자 겸 CEO. AI 칩 시대를 연 장본인.", en: "Nvidia founder-CEO; the man behind the AI chip era.", ja: "NVIDIA創業者兼CEO。AIチップ時代の立役者。" }, l: { ko: "1993년 엔비디아를 창업해 GPU를 게임용 부품에서 AI의 심장으로 바꿔놨다. 가죽 재킷과 '더 사면 더 아낀다'는 어록으로도 유명하다.", en: "Founded Nvidia in 1993 and turned the GPU from a gaming part into the heart of AI. Famous for the leather jacket and 'the more you buy, the more you save.'", ja: "1993年にNVIDIAを創業し、GPUをゲーム用部品からAIの心臓に変えた。革ジャンと「買えば買うほど得」の名言でも有名。" } },
  "웨이저자": { d: { ko: "TSMC 회장 겸 CEO. 세계 최대 파운드리의 사령탑.", en: "TSMC chairman & CEO, at the helm of the world's largest foundry.", ja: "TSMC会長兼CEO。世界最大ファウンドリの司令塔。" }, l: { ko: "2024년 회장에 올라 창업자 모리스 창 이후 시대를 이끈다. 애플·엔비디아의 최첨단 칩 생산과 미국·일본 공장 확장을 지휘한다.", en: "Took the chair in 2024, steering the post-Morris Chang era: leading-edge chips for Apple and Nvidia plus fab expansion in the US and Japan.", ja: "2024年会長就任。アップル・NVIDIAの最先端チップ生産と米日工場拡大を指揮する。" } },
  "사티아 나델라": { d: { ko: "마이크로소프트 CEO. 클라우드·AI 전환을 이끈 3대 수장.", en: "Microsoft's third CEO; architect of its cloud and AI transformation.", ja: "マイクロソフト3代目CEO。クラウド・AI転換の設計者。" }, l: { ko: "2014년 취임해 윈도 중심 회사를 애저와 AI 중심으로 재편했고, 오픈AI 최대 후원 계약을 주도했다.", en: "CEO since 2014; rebuilt the company around Azure and AI and drove the landmark OpenAI partnership.", ja: "2014年就任。会社をAzureとAI中心に再編し、OpenAIとの大型提携を主導した。" } },
  "마크 저커버그": { d: { ko: "메타 창업자 겸 CEO. 오픈 웨이트 AI와 초대형 컴퓨트에 베팅 중.", en: "Meta founder-CEO, betting on open-weight AI and massive compute.", ja: "メタ創業者兼CEO。オープンウェイトAIと超大型コンピュートに賭ける。" }, l: { ko: "2004년 페이스북을 창업했고, 지금은 라마 모델과 AI 데이터센터에 연 수백억 달러를 쏟는다.", en: "Founded Facebook in 2004; now pours tens of billions a year into Llama models and AI datacenters.", ja: "2004年にFacebookを創業。現在はLlamaとAIデータセンターに年数百億ドルを投じる。" } },
  "팀 쿡": { d: { ko: "애플 CEO. 공급망의 마술사에서 미국 리쇼어링의 지휘자로.", en: "Apple CEO; the supply-chain maestro now steering US reshoring.", ja: "アップルCEO。サプライチェーンの名手から米国回帰の指揮者へ。" }, l: { ko: "2011년 잡스의 뒤를 이어 애플을 세계 최고 가치 기업으로 키웠고, 최근엔 반도체 공급망의 미국 이전을 진두지휘한다.", en: "Succeeded Jobs in 2011 and built Apple into the world's most valuable company; now leads moving its chip supply chain onto US soil.", ja: "2011年ジョブズの後任となりアップルを世界最高価値企業に育成。現在は半導体供給網の米国移転を指揮。" } },
  "데미스 하사비스": { d: { ko: "딥마인드 창업자 겸 CEO, 노벨화학상 수상자. 알파고의 아버지.", en: "DeepMind founder-CEO and Nobel laureate; father of AlphaGo.", ja: "ディープマインド創業者兼CEO、ノーベル賞受賞者。アルファ碁の父。" }, l: { ko: "체스 신동 출신으로 2010년 딥마인드를 세웠고, 알파폴드로 노벨화학상을 받았다. 구글 제미나이 개발을 총괄한다.", en: "A chess prodigy who founded DeepMind in 2010 and won a Nobel for AlphaFold; now oversees Google's Gemini.", ja: "チェス神童出身で2010年DeepMind創業。AlphaFoldでノーベル化学賞を受賞し、Gemini開発を統括。" } },
  "샘 올트먼": { d: { ko: "오픈AI CEO. 챗GPT로 생성형 AI 붐을 연 인물.", en: "OpenAI CEO; sparked the generative-AI boom with ChatGPT.", ja: "OpenAIのCEO。ChatGPTで生成AIブームに火を付けた。" }, l: { ko: "와이콤비네이터 사장을 거쳐 오픈AI를 이끌며, 수천억 달러 규모의 컴퓨트 확보 경쟁의 중심에 서 있다.", en: "Former Y Combinator president; now leads OpenAI at the center of the race to secure hundreds of billions in compute.", ja: "元Yコンビネーター社長。数千億ドル規模のコンピュート確保競争の中心に立つ。" } },
  "순다르 피차이": { d: { ko: "구글·알파벳 CEO. 검색 제국의 AI 전환을 지휘한다.", en: "CEO of Google and Alphabet, steering the search empire's AI pivot.", ja: "グーグル・アルファベットCEO。検索帝国のAI転換を指揮。" }, l: { ko: "크롬·안드로이드를 키운 뒤 2015년 구글 CEO에 올랐다. 제미나이와 자체 TPU로 AI 풀스택 전략을 밀고 있다.", en: "Rose through Chrome and Android to become Google CEO in 2015; pushing the full-stack AI strategy with Gemini and TPUs.", ja: "ChromeとAndroidを育て2015年CEO就任。GeminiとTPUでAIフルスタック戦略を推進。" } },
  "일론 머스크": { d: { ko: "테슬라 CEO. 전기차·로봇·자율주행에 회사의 미래를 걸었다.", en: "Tesla CEO betting the company on EVs, robots and self-driving.", ja: "テスラCEO。EV・ロボット・自動運転に会社の未来を賭ける。" }, l: { ko: "스페이스X·테슬라·xAI를 이끄는 연쇄 창업가. 로보택시와 휴머노이드 옵티머스를 다음 성장 스토리로 내세운다.", en: "Serial founder behind SpaceX, Tesla and xAI; pitches robotaxis and the Optimus humanoid as the next act.", ja: "SpaceX・テスラ・xAIを率いる連続起業家。ロボタクシーとOptimusを次の成長物語に掲げる。" } },
  "혹 탄": { d: { ko: "브로드컴 CEO. 인수합병으로 AI 반도체 2위 제국을 만들었다.", en: "Broadcom CEO; built the #2 AI-chip empire through M&A.", ja: "ブロードコムCEO。M&AでAI半導体2位の帝国を築いた。" }, l: { ko: "말레이시아 출신으로 2006년부터 회사를 이끌며 공격적 인수로 성장시켰다. 구글·메타의 맞춤형 AI 칩(ASIC)을 도맡는다.", en: "Malaysian-born, CEO since 2006; grew the company through aggressive M&A and now runs custom AI ASICs for Google and Meta.", ja: "マレーシア出身、2006年からCEO。積極的買収で成長させ、グーグル・メタのカスタムAIチップを担う。" } },
  "립부 탄": { d: { ko: "인텔 CEO. 파운드리 재건이라는 구원 등판 임무를 맡았다.", en: "Intel CEO, brought in to rescue and rebuild the foundry business.", ja: "インテルCEO。ファウンドリ再建の救援登板。" }, l: { ko: "반도체 벤처캐피털의 전설이자 케이던스 CEO 출신으로, 2025년 인텔 지휘봉을 잡았다.", en: "A legendary chip VC and former Cadence CEO who took Intel's helm in 2025.", ja: "半導体VCの伝説でケイデンス元CEO。2025年にインテルの指揮を執る。" } },
  "산제이 메흐로트라": { d: { ko: "마이크론 CEO. 미국 유일 메모리 대기업의 수장.", en: "Micron CEO, leading America's only major memory maker.", ja: "マイクロンCEO。米国唯一の大手メモリ企業を率いる。" }, l: { ko: "샌디스크 공동창업자 출신으로 2017년부터 마이크론을 이끌며 HBM 시장 진입과 대형 장기공급계약(LTA)을 성사시켰다.", en: "Co-founded SanDisk before taking Micron's helm in 2017; drove its HBM entry and major long-term supply agreements.", ja: "サンディスク共同創業者出身。2017年からマイクロンを率い、HBM参入と大型LTAを実現。" } },
  "아르카디 볼로즈": { d: { ko: "네비우스 창업자 겸 CEO. 얀덱스를 만든 기술 기업가.", en: "Nebius founder-CEO; the entrepreneur who built Yandex.", ja: "ネビウス創業者兼CEO。ヤンデックスを作った起業家。" }, l: { ko: "'러시아의 구글' 얀덱스를 창업했고, 2024년 해외 자산을 재편해 AI 인프라 기업 네비우스로 재출발했다.", en: "Founded Yandex, 'Russia's Google,' then relaunched its international assets in 2024 as AI-infrastructure firm Nebius.", ja: "「ロシアのグーグル」ヤンデックスを創業し、2024年に海外資産をAIインフラ企業ネビウスとして再出発させた。" } },
  "KR 스리다": { d: { ko: "블룸에너지 창업자 겸 CEO. NASA 화성 프로젝트 출신.", en: "Bloom Energy founder-CEO, a NASA Mars program veteran.", ja: "ブルームエナジー創業者兼CEO。NASA火星計画出身。" }, l: { ko: "화성에서 산소를 만드는 기술을 지구의 연료전지로 뒤집어 2001년 블룸에너지를 세웠다. AI 데이터센터 전력난의 수혜 기업으로 키웠다.", en: "Flipped his Mars oxygen-generation tech into terrestrial fuel cells, founding Bloom in 2001 — now a beneficiary of the AI datacenter power crunch.", ja: "火星で酸素を作る技術を地上の燃料電池に転換し2001年に創業。AIデータセンター電力難の受益企業に育てた。" } },
  "퐁 레": { d: { ko: "스트래티지(구 마이크로스트래티지) CEO. 비트코인 재무전략의 실무 총괄.", en: "CEO of Strategy (ex-MicroStrategy), running the bitcoin treasury playbook.", ja: "ストラテジーCEO。ビットコイン財務戦略の実務を統括。" }, l: { ko: "CFO 출신으로 2022년 CEO에 올라, 세일러 의장이 설계한 비트코인 매집 전략의 집행을 맡는다.", en: "A former CFO who became CEO in 2022, executing the bitcoin-accumulation strategy designed by chairman Saylor.", ja: "CFO出身で2022年CEO就任。セイラー会長設計のビットコイン買い集め戦略を執行する。" } },
  "마이클 세일러": { d: { ko: "스트래티지 창업자 겸 회장. 기업 비트코인 매집 전략의 원조.", en: "Strategy's founder-chairman; pioneer of the corporate bitcoin treasury.", ja: "ストラテジー創業者兼会長。企業ビットコイン買いの元祖。" }, l: { ko: "2020년부터 회사 자금과 차입으로 비트코인을 사 모으는 전략을 밀어붙여, 주가를 비트코인의 레버리지 프록시로 만들었다.", en: "Since 2020 has piled corporate cash and debt into bitcoin, turning the stock into a leveraged BTC proxy.", ja: "2020年から社債まで使いBTCを買い集め、株価をビットコインのレバレッジ・プロキシに変えた。" } },
  "러셀 엘완거": { d: { ko: "타워세미컨덕터 CEO. 니치 아날로그 파운드리의 장수 CEO.", en: "Tower Semiconductor's long-serving CEO in specialty analog foundry.", ja: "タワーセミコンダクターの長期CEO。" }, l: { ko: "2005년부터 회사를 이끌며 광통신·전력 반도체 등 틈새 공정 강자로 키웠다. AI 데이터센터용 실리콘 포토닉스가 새 성장축이다.", en: "CEO since 2005; built strength in niche processes like optics and power chips, with silicon photonics for AI datacenters as the new growth leg.", ja: "2005年からCEO。光通信・パワー半導体などニッチ工程の強者に育て、AI向けシリコンフォトニクスが新成長軸。" } },
  "톰슨 린": { d: { ko: "어플라이드 옵토일렉트로닉스 창업자 겸 CEO.", en: "Founder-CEO of Applied Optoelectronics.", ja: "アプライド・オプトエレクトロニクス創業者兼CEO。" }, l: { ko: "1997년 회사를 세워 데이터센터용 광트랜시버 전문 기업으로 키웠다. AI 클러스터의 800G 수요가 성장 동력이다.", en: "Founded the company in 1997 and built it into a datacenter optical-transceiver specialist riding 800G AI demand.", ja: "1997年創業。データセンター向け光トランシーバー専業に育て、AIの800G需要が成長動力。" } },
  "아시시쿠마르 차우한": { d: { ko: "인도국립증권거래소(NSE) CEO. 인도 증시 전산화의 주역.", en: "CEO of India's NSE; a key architect of India's electronic markets.", ja: "インドNSEのCEO。電子取引化の立役者。" }, l: { ko: "NSE 창립 멤버로 인도 증시의 전산 거래를 설계했고, 세계 최대 파생상품 거래소가 된 NSE의 상장을 이끈다.", en: "A founding team member who helped design India's electronic trading; now steering the IPO of the world's busiest derivatives exchange.", ja: "NSE創設メンバーとして電子取引を設計。世界最大デリバティブ取引所となったNSEの上場を主導する。" } },
  "우융밍": { d: { ko: "알리바바 CEO. 창업 멤버로 AI·클라우드 재건을 이끈다.", en: "Alibaba CEO; a co-founder now leading its AI and cloud reboot.", ja: "アリババCEO。創業メンバーでAI・クラウド再建を主導。" }, l: { ko: "1999년 창업 멤버로 합류했고 2023년 CEO에 올랐다. 오픈소스 Qwen 모델과 클라우드를 회사의 새 성장축으로 밀고 있다.", en: "Joined as a founding member in 1999 and became CEO in 2023, pushing the open-source Qwen models and cloud as the new growth engine.", ja: "1999年創業メンバー、2023年CEO就任。オープンソースQwenとクラウドを新成長軸に推進。" } },
  "량원펑": { d: { ko: "딥시크 창업자 겸 CEO. 헤지펀드로 번 돈으로 AI 연구소를 세웠다.", en: "DeepSeek founder-CEO; funded the AI lab with hedge-fund profits.", ja: "ディープシーク創業者兼CEO。ヘッジファンドの利益でAIラボを設立。" }, l: { ko: "퀀트 헤지펀드 하이플라이어를 만든 뒤 2023년 딥시크를 세웠고, 초저가 고성능 모델로 'AI 스푸트니크 모멘트'를 일으켰다.", en: "Built quant fund High-Flyer, founded DeepSeek in 2023, and triggered the 'AI Sputnik moment' with ultra-cheap high-performing models.", ja: "クオンツファンドHigh-Flyerを築いた後2023年に創業。超低価格・高性能モデルで「AIスプートニク・モーメント」を起こした。" } }
};
function ceoTipHtml(name){
  const info = CEO_INFO[name];
  return '<span class="entity-tip"><span class="tip-sector">CEO</span>' + (info.d[LANG] || info.d.ko)
    + '<span class="tip-hint">' + (CEO_HINT[LANG] || CEO_HINT.en) + '</span></span>';
}
function ceoEnhance(root){
  try {
    root.querySelectorAll(".eh-facts .f").forEach(cell => {
      if (cell.dataset.ceoDone) return;
      const lab = cell.querySelector("b");
      if (!lab) return;
      const t = lab.textContent.trim();
      if (t !== "CEO" && t !== "대표") return;
      let html = cell.innerHTML;
      let touched = false;
      Object.keys(CEO_INFO).forEach(name => {
        if (cell.textContent.indexOf(name) === -1) return;
        const wrapped = '<span class="ceo-link has-tip" onclick="ceoTap(this, \'' + name + '\')">' + name + ceoTipHtml(name) + '</span>';
        html = html.split(name).join(wrapped);
        touched = true;
      });
      if (touched) cell.innerHTML = html;
      cell.dataset.ceoDone = "1";
    });
  } catch (e) {}
}
function ceoTap(el, name){
  const hoverable = window.matchMedia && window.matchMedia("(hover: hover)").matches;
  if (!hoverable && !el.classList.contains("show")){
    document.querySelectorAll(".has-tip.show").forEach(x => x.classList.remove("show"));
    el.classList.add("show");
    return;
  }
  el.classList.remove("show");
  const info = CEO_INFO[name];
  const facts = el.closest(".eh-facts");
  if (!info || !facts) return;
  const host = facts.parentNode;
  const old = host.querySelector(".ceo-detail");
  if (old){
    const same = old.dataset.name === name;
    old.remove();
    if (same) return;
  }
  const box = document.createElement("div");
  box.className = "ceo-detail";
  box.dataset.name = name;
  box.innerHTML = '<b>' + name + '</b>' + (info.l[LANG] || info.l.ko);
  if (facts.nextSibling) host.insertBefore(box, facts.nextSibling);
  else host.appendChild(box);
}
'''

DEBATE_CALL = '''    renderEntityDebate(list, items, S);
    hydrateImages();
    applyEngageCounts();
    setupViewObserver();
    return;
'''

BUILD_COMMENT = "<!-- STACKS BUILD v56 :: bull/bear debate board on entity pages (stance grouping + scoreboard); company chips/filter open the debate page -->"


def structural_edits(html):
    """Build-comment bump + entity-view insertion, anchored structurally."""
    # a) top-of-file build comment: replace whatever version is there
    html, n = re.subn(r"<!-- STACKS BUILD v\d+ :: [^\n]*-->", BUILD_COMMENT, html, count=1)
    if n != 1:
        raise SystemExit("[ABORT] build comment not found")
    # b) entity view: insert the debate render just before the closing
    #    brace of the ENTITY_VIEW block (anchored on entityHeadEl call)
    anchor = "list.appendChild(entityHeadEl(ENTITY_VIEW"
    i = html.find(anchor)
    if i < 0:
        raise SystemExit("[ABORT] entityHeadEl anchor not found")
    if html.find(anchor, i + 1) >= 0:
        raise SystemExit("[ABORT] entityHeadEl anchor is not unique")
    close = html.find("\n  }\n", i)
    if close < 0 or close - i > 800:
        raise SystemExit("[ABORT] ENTITY_VIEW closing brace not found near anchor")
    html = html[:close + 1] + DEBATE_CALL + html[close + 1:]
    return html


OPTIONAL_EDITS = [
]

STAGE3_EDITS = [
    # a) debate segs become stance filters (feed view)
    ('''    + ["bull", "bear", "watch"].map(k => counts[k]
        ? '<div class="debate-seg ds-' + k + '" style="flex:' + counts[k] + '"><span>' + stanceMeta(k).label + '</span><b>' + counts[k] + '</b></div>'
        : "").join("")''',
     '''    + ["bull", "bear", "watch"].map(k => counts[k]
        ? '<div class="debate-seg ds-' + k + (STANCE_FILTER ? (STANCE_FILTER === k ? " on" : " dim") : "") + '" style="flex:' + counts[k] + '" onclick="stanceFilterTap(\\'' + k + '\\')"><span>' + stanceMeta(k).label + '</span><b>' + counts[k] + '</b></div>'
        : "").join("")'''),
    # b) active filter hides the other groups
    ('''  ["bull", "bear", "watch"].forEach(k => {
    if (!groups[k].length) return;''',
     '''  ["bull", "bear", "watch"].forEach(k => {
    if (STANCE_FILTER && k !== STANCE_FILTER) return;
    if (!groups[k].length) return;'''),
    # c) reset a stale filter when the entity changes
    ('''function renderEntityDebate(list, items, S){
  if (!items.length){''',
     '''function renderEntityDebate(list, items, S){
  if (STANCE_FILTER && STANCE_FILTER_KEY !== ENTITY_VIEW) STANCE_FILTER = null;
  if (!items.length){'''),
    # d) CEO enhancer runs on the feed entity view
    ('''  } else {
    list.appendChild(bar);
  }''',
     '''  } else {
    list.appendChild(bar);
  }
  ceoEnhance(list);'''),
    # e) stage-3 function block, anchored on chipHtml (still unique)
    ("function chipHtml(tag){", STAGE3_JS + "function chipHtml(tag){"),
    # f) rail panel gets the compact debate bar + CEO links
    ("function showEntityRail(key){",
     '''function showEntityRail(key){
  showEntityRailOrig(key);
  railDebateEnhance(key);
}
function showEntityRailOrig(key){'''),
    # g) brand = home button
    ('<a class="brand" href="#">',
     '<a class="brand" href="#" onclick="return goHome(event)">'),
    # h) CSS for filters, rail bar, CEO links
    (".entity-head .debate-bar{background:var(--bg);margin:14px 0 2px;}",
     """.entity-head .debate-bar{background:var(--bg);margin:14px 0 2px;}
.debate-seg{cursor:pointer;transition:transform .12s ease,box-shadow .12s ease,opacity .12s ease;}
.debate-seg:hover{transform:translateY(-1px);}
.debate-seg.dim{opacity:.35;}
.debate-seg.on{box-shadow:0 0 0 2px var(--text);}
.rail-debate{margin:12px 0 2px;padding:10px 12px;}
.rail-debate .debate-track{height:34px;}
.ceo-link{cursor:pointer;font-weight:600;text-decoration:underline dotted;text-underline-offset:2px;text-decoration-color:var(--muted);}
.ceo-link:hover{color:var(--accent);text-decoration-color:var(--accent);}
.ceo-detail{margin-top:12px;background:var(--bg-soft);border:1px solid var(--line);border-radius:12px;padding:11px 13px;font-size:13px;line-height:1.62;}
.ceo-detail b{display:block;margin-bottom:3px;}
.entity-head .ceo-detail{background:var(--bg);}
html[data-lang="ko"] .ceo-detail{font-family:"Pretendard Variable",sans-serif;}"""),
]


STAGE4_EDITS = [
    # a) chip / cover-label tap: desktop -> right panel (as before), mobile -> entity feed
    ('''  el.classList.remove("show");
  if (ENTITIES[tag]){
    /* known company/person/term -> open its debate/entity page */
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";
    const inp1 = document.getElementById("searchInput"); if (inp1) inp1.value = "";
    ENTITY_VIEW = tag;
    renderFeed(true);
  } else {''',
     '''  el.classList.remove("show");
  if (ENTITIES[tag]){
    /* stage4 */
    /* known company/person/term: desktop -> right panel, mobile -> entity feed */
    if (window.matchMedia && window.matchMedia("(min-width:1024px)").matches && typeof showEntityRail === "function"){
      showEntityRail(tag);
      return;
    }
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";
    const inp1 = document.getElementById("searchInput"); if (inp1) inp1.value = "";
    ENTITY_VIEW = tag;
    renderFeed(true);
  } else {'''),
    # b) company dropdown: same desktop/mobile split
    ('''  if (name && ENTITIES[name] && ENTITIES[name].kind === "company"){
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";''',
     '''  if (name && ENTITIES[name] && ENTITIES[name].kind === "company"){
    if (window.matchMedia && window.matchMedia("(min-width:1024px)").matches && typeof showEntityRail === "function"){
      const sel = document.getElementById("companyFilter"); if (sel) sel.value = "";
      showEntityRail(name);
      return;
    }
    SERIES_VIEW = null; BM_ONLY = false; QUERY = "";'''),
    # c) Korean fact label: 대표 -> CEO
    ('fCeo: "대표"', 'fCeo: "CEO"'),
]


STAGE5_EDITS = [
    # a) body-text company/person/term links: desktop click -> right panel
    ("function entityTap(el, key){",
     '''function entityTap(el, key){
  /* stage5 */
  if (window.matchMedia && window.matchMedia("(min-width:1024px)").matches
      && typeof showEntityRail === "function" && ENTITIES[key]){
    document.querySelectorAll(".has-tip.show").forEach(x => x.classList.remove("show"));
    showEntityRail(key);
    return;
  }
  entityTapOrig(el, key);
}
function entityTapOrig(el, key){'''),
    # b) show the group chief for the Korean giants (like Jensen Huang / Tim Cook)
    ("  buildEntityMatcher();",
     '''  /* top-figure override: the group chief, not the operating CEO */
  try {
    if (ENTITIES["SK HYNIX"]) ENTITIES["SK HYNIX"].ceo = "최태원 (Chey Tae-won)";
    if (ENTITIES["SAMSUNG ELECTRONICS"]) ENTITIES["SAMSUNG ELECTRONICS"].ceo = "이재용 (Jay Y. Lee)";
  } catch (e) {}
  buildEntityMatcher();'''),
    # c) profiles for the two chiefs
    ("const CEO_INFO = {",
     '''const CEO_INFO = {
  "최태원": { d: { ko: "SK그룹 회장이자 SK하이닉스 이사회 의장. 그룹 전체의 최고 결정권자.", en: "Chairman of SK Group and of SK hynix's board — the group's top decision-maker.", ja: "SKグループ会長、SKハイニックス取締役会議長。グループ最高の意思決定者。" }, l: { ko: "1998년부터 SK그룹을 이끄는 총수. 2012년 하이닉스 인수를 결단해 오늘의 AI 메모리 1위 기반을 만들었다. 일상 경영은 곽노정 CEO가 맡고, 최 회장은 그룹 차원의 대규모 투자를 결정한다.", en: "SK Group's chief since 1998. His 2012 decision to acquire Hynix laid the foundation for today's AI-memory leadership; day-to-day operations are run by CEO Kwak Noh-jung while the chairman calls the group-level investments.", ja: "1998年からSKグループを率いる総帥。2012年のハイニックス買収を決断し、今日のAIメモリ首位の基盤を作った。日常経営は郭魯正CEOが担い、崔会長はグループ次元の大型投資を決める。" } },
  "이재용": { d: { ko: "삼성전자 회장. 삼성그룹의 총수.", en: "Executive Chairman of Samsung Electronics; head of the Samsung group.", ja: "サムスン電子会長。サムスングループの総帥。" }, l: { ko: "이건희 회장의 아들로 2022년 회장에 취임했다. 반도체·바이오·AI를 삼성의 3대 성장축으로 이끌며, HBM 반격과 파운드리 재건이 당면 과제다.", en: "Son of Lee Kun-hee, he took the chairmanship in 2022. Leads Samsung's push in chips, bio and AI — with the HBM comeback and foundry rebuild as the immediate tests.", ja: "李健熙会長の息子で2022年会長就任。半導体・バイオ・AIを3大成長軸に率い、HBM巻き返しとファウンドリ再建が当面の課題。" } },'''),
    # d) newsletter consent "내용 보기" -> real privacy policy
    ('\' · <a href="\' + STIBEE_PAGE + \'" target="_blank" rel="noopener">\'',
     '\' · <a href="privacy.html" target="_blank" rel="noopener">\''),
]

STAGE5_OPTIONAL = [
    # footer link to the privacy policy
    ('<a href="feed.xml">RSS</a>',
     '<a href="feed.xml">RSS</a> · <a href="privacy.html">개인정보처리방침</a>'),
]


def stage5(html):
    problems = []
    for i, (needle, _) in enumerate(STAGE5_EDITS, 1):
        n = html.count(needle)
        if n != 1:
            problems.append("stage5 edit %d: needle found %d times: %r" % (i, n, needle[:70]))
    if problems:
        for p in problems:
            print("[ABORT] " + p)
        return 1
    for needle, repl in STAGE5_EDITS:
        html = html.replace(needle, repl, 1)
    for needle, repl in STAGE5_OPTIONAL:
        if html.count(needle) == 1:
            html = html.replace(needle, repl, 1)
        else:
            print("[warn] optional stage5 edit skipped: %r" % needle[:50])
    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("stage-5 applied: rail-first body links, group-chief names, privacy links")
    return 0


def stage4(html):
    problems = []
    for i, (needle, _) in enumerate(STAGE4_EDITS, 1):
        n = html.count(needle)
        if n != 1:
            problems.append("stage4 edit %d: needle found %d times: %r" % (i, n, needle[:70]))
    if problems:
        for p in problems:
            print("[ABORT] " + p)
        return 1
    for needle, repl in STAGE4_EDITS:
        html = html.replace(needle, repl, 1)
    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("stage-4 applied: rail-first entity taps + CEO label")
    return 0


def stage3(html):
    problems = []
    for i, (needle, _) in enumerate(STAGE3_EDITS, 1):
        n = html.count(needle)
        if n != 1:
            problems.append("stage3 edit %d: needle found %d times: %r" % (i, n, needle[:70]))
    if problems:
        for p in problems:
            print("[ABORT] " + p)
        return 1
    for needle, repl in STAGE3_EDITS:
        html = html.replace(needle, repl, 1)
    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("stage-3 applied: rail debate bar, stance filters, CEO profiles, home button")
    return 0


def main():
    with io.open(PATH, encoding="utf-8") as f:
        html = f.read()

    if "const STANCE" in html and "renderEntityDebate" in html:
        # stage 2: move the scoreboard to the top of the entity header
        # (right under the company description, above the chart) so it is
        # visible without scrolling, especially on phones.
        if "/* debate-bar placement fix */" in html:
            if "function goHome(" in html:
                if "/* stage4 */" in html:
                    if "/* stage5 */" in html:
                        print("stage 5 already applied; nothing to do")
                        return 0
                    return stage5(html)
                return stage4(html)
            return stage3(html)
        n1 = html.count("  list.appendChild(bar);")
        n2 = html.count(".ds-watch{background:linear-gradient(135deg,#9BA1B0,#6B7280);}")
        if n1 != 1 or n2 != 1:
            print("[ABORT] stage-2 anchors not unique (bar=%d, css=%d)" % (n1, n2))
            return 1
        html = html.replace(
            "  list.appendChild(bar);",
            """  /* debate-bar placement fix */
  const ehd = list.querySelector(".entity-head");
  if (ehd){
    const slot = ehd.querySelector(".eh-desc") || ehd.querySelector(".eh-top");
    if (slot && slot.nextSibling) ehd.insertBefore(bar, slot.nextSibling);
    else ehd.appendChild(bar);
  } else {
    list.appendChild(bar);
  }""", 1)
        html = html.replace(
            ".ds-watch{background:linear-gradient(135deg,#9BA1B0,#6B7280);}",
            ".ds-watch{background:linear-gradient(135deg,#9BA1B0,#6B7280);}\n"
            ".entity-head .debate-bar{background:var(--bg);margin:14px 0 2px;}", 1)
        with io.open(PATH, "w", encoding="utf-8") as f:
            f.write(html)
        print("stage-2 placement fix applied")
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
    html = structural_edits(html)

    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("debate-board patch applied: %d text edits + 2 structural" % len(EDITS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
