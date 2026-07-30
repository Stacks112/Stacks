/* ============ v82: Twitter-style mobile shell ============ */
(function(){
  "use strict";
  if (window.__V82) return; window.__V82 = true;
  /* gist 본문에는 소제목·확인블록 마커가 들어 있다(claude/prompts/publish-v4.3.md [4-E]).
     한 줄 스니펫에 마커가 그대로 나가면 안 되므로 index.html의 plainGist를 쓰되,
     로드 순서에 의존하지 않도록 없으면 원문을 그대로 돌려준다. */
  function v82Plain(t){
    return (typeof plainGist === "function") ? plainGist(t) : String(t || "");
  }

  var mq = window.matchMedia("(max-width:1023px)");
  /* ---- beta gate: opt-in until confirmed on real iOS ----
     ?v82beta enable (persisted) · ?v82off disable · else pre-v82 (v81). */
  try {
    if (/v82off/.test(location.search)) localStorage.setItem("stk_v82_off", "1");
    else if (/v82beta/.test(location.search)) localStorage.removeItem("stk_v82_off");
  } catch(e){}
  var V82ON = true;   /* v82 shipped as the default mobile shell — ?v82off opts out (persisted) */
  try { V82ON = localStorage.getItem("stk_v82_off") !== "1"; } catch(e){}
  if (!V82ON){
    var offCss = document.getElementById("v82css");
    if (offCss) offCss.disabled = true;
    return;
  }

  var V82S = {
    ko:{home:"홈",find:"찾기",explore:"탐색",cal:"캘린더",notif:"알림",post:"게시물",more:"더 보기",
        me:"내 정보",record:"적중 기록",alerts:"알림 설정",appearance:"화면 테마",events:"다가오는 이벤트",
        skewTitle:"지금 쏠린 곳",skewSub:"테마·종목별로 강세/약세 의견이 어디로 쏠려 있는지 한눈에 봅니다.",
        themesSec:"테마 논쟁",recordSec:"적중 기록",people:"논객",company:"회사",
        ntNew:"새 글",ntGrade:"채점",ntDebate:"오늘의 토론",ntSkew:"쏠림 알림",noAlerts:"새로운 알림이 없습니다.",
        bull:"강세",bear:"약세",openThemes:"테마 논쟁 보기",openRecord:"저자 적중 기록 보기",
        bm:"북마크",follows:"팔로우 내역",shares:"공유 내역",nlLabel:"이번 주 베스트 메일",
        community:"커뮤니티",communitySec:"커뮤니티",communitySoon:"준비 중",
        communityDesc:"특정 논객이나 회사를 함께 쫓는 커뮤니티를 만들거나 팔로우하고, 인용해서 덧글을 남기고, 직접 글도 쓰며 서로 소통하는 공간이에요. 곧 찾아옵니다.",
        emptyFollows:"아직 팔로우한 논객·회사·시리즈가 없어요.",emptyShares:"아직 공유한 글이 없어요.",
        followsPeople:"논객",followsCompany:"회사",followsSeries:"시리즈",
        nsTitle:"알림 설정",nsNew:"새 글 알림",nsDebate:"오늘의 토론 알림",nsFollow:"팔로우 새 글 알림",
        nsEvents:"다가오는 이벤트 알림",nsNoEvents:"예정된 이벤트가 없어요.",nsRecent:"최근 알림",nsEvSubEmpty:"알림 신청한 이벤트가 없어요. 이벤트의 종 버튼을 눌러 신청하세요.",
        recentQ:"최근 검색",recentClear:"전체 지우기",recentDel:"지우기"},
    en:{home:"Home",find:"Find",explore:"Explore",cal:"Calendar",notif:"Alerts",post:"Post",more:"More",
        me:"My page",record:"Track record",alerts:"Notifications",appearance:"Appearance",events:"Upcoming events",
        skewTitle:"Where the crowd is leaning",skewSub:"See at a glance which way bull/bear opinion tilts, by theme and ticker.",
        themesSec:"Theme debates",recordSec:"Track record",people:"Authors",company:"Companies",
        ntNew:"New",ntGrade:"Graded",ntDebate:"Today's debate",ntSkew:"Skew alert",noAlerts:"No new alerts.",
        bull:"Bull",bear:"Bear",openThemes:"Open theme debates",openRecord:"Open author track record",
        bm:"Bookmarks",follows:"Following",shares:"Share history",nlLabel:"Weekly best by email",
        community:"Community",communitySec:"Community",communitySoon:"Coming soon",
        communityDesc:"A space to create or follow communities around a given author or company, quote-and-comment, post your own takes, and talk with others. Coming soon.",
        emptyFollows:"You aren't following any authors, companies, or series yet.",emptyShares:"You haven't shared anything yet.",
        followsPeople:"Author",followsCompany:"Company",followsSeries:"Series",
        nsTitle:"Notification settings",nsNew:"New posts",nsDebate:"Today's debate",nsFollow:"New posts from who you follow",
        nsEvents:"Upcoming events",nsNoEvents:"No upcoming events.",nsRecent:"Recent alerts",nsEvSubEmpty:"No events subscribed yet. Tap the bell on an event to get alerts.",
        recentQ:"Recent searches",recentClear:"Clear all",recentDel:"Remove"},
    ja:{home:"ホーム",find:"探す",explore:"発見",cal:"カレンダー",notif:"通知",post:"投稿",more:"もっと見る",
        me:"マイページ",record:"的中記録",alerts:"通知設定",appearance:"テーマ",events:"今後のイベント",
        skewTitle:"今の傾き",skewSub:"テーマ・銘柄ごとに強気/弱気の意見がどちらに傾いているか一目で。",
        themesSec:"テーマ論争",recordSec:"的中記録",people:"論客",company:"企業",
        ntNew:"新着",ntGrade:"採点",ntDebate:"今日の論点",ntSkew:"傾きアラート",noAlerts:"新しい通知はありません。",
        bull:"強気",bear:"弱気",openThemes:"テーマ論争を見る",openRecord:"著者の的中記録を見る",
        bm:"ブックマーク",follows:"フォロー履歴",shares:"共有履歴",nlLabel:"今週のベストをメール",
        community:"コミュニティ",communitySec:"コミュニティ",communitySoon:"準備中",
        communityDesc:"特定の論客や企業を一緒に追うコミュニティを作ったりフォローし、引用してコメントを残し、自分でも投稿して交流できる場です。近日公開。",
        emptyFollows:"まだフォローした論客・企業・シリーズがありません。",emptyShares:"まだ共有した記事がありません。",
        followsPeople:"論客",followsCompany:"企業",followsSeries:"シリーズ",
        nsTitle:"通知設定",nsNew:"新着記事",nsDebate:"今日の論点",nsFollow:"フォロー中の新着",
        nsEvents:"今後のイベント",nsNoEvents:"予定されたイベントはありません。",nsRecent:"最近の通知",nsEvSubEmpty:"通知を登録したイベントはありません。イベントのベルを押して登録してください。",
        recentQ:"最近の検索",recentClear:"すべて消去",recentDel:"削除"}
  };
  function T(){ var l = (typeof LANG !== "undefined" && V82S[LANG]) ? LANG : "ko"; return V82S[l]; }
  function $(id){ return document.getElementById(id); }
  var SILENT = false;
  function silentBack(){ SILENT = true; try { history.back(); } catch(e){ SILENT = false; } }
  /* 2026-07-25 (june): 탐색의 지금쏠린곳/테마논쟁/적중기록을 X 모바일식 서브뷰로.
     HUB_SUB   = 허브 화면 안에서 콘텐츠만 바꾼 서브(지금은 "skew").
     EXPLORE_SUB = 피드에 렌더되는 서브(테마논쟁/적중기록). 이때는 허브 화면을 숨기고
                   nav를 ←+제목 바로 바꾼다(nav-sub). 뒤로가기는 허브로 되돌린다. */
  var HUB_SUB = null, EXPLORE_SUB = null;

  var ICONS = {
    home:'<svg viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5M5.5 10v9h13v-9"/></svg>',
    find:'<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
    explore:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m15.6 8.4-2.2 5-5 2.2 2.2-5z"/></svg>',
    cal:'<svg viewBox="0 0 24 24"><rect x="4" y="6" width="16" height="14" rx="2"/><path d="M4 10h16M8 4v4M16 4v4"/></svg>',
    notif:'<svg viewBox="0 0 24 24"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 19a2 2 0 0 0 4 0"/></svg>'
  };

  /* ---------- shell DOM ---------- */
  function buildShell(){
    if ($("v82nav")) return;
    var nav = document.createElement("div"); nav.id = "v82nav";
    nav.innerHTML =
      '<button data-v="home" class="on">' + ICONS.home + '<span></span></button>' +
      '<button data-v="find">' + ICONS.find + '<span></span></button>' +
      '<button data-v="explore">' + ICONS.explore + '<span></span></button>' +
      '<button data-v="cal">' + ICONS.cal + '<span></span></button>' +
      '<button data-v="notif">' + ICONS.notif + '<span></span></button>';
    document.body.appendChild(nav);
    var nbs = nav.querySelectorAll("button");
    for (var i = 0; i < nbs.length; i++) nbs[i].onclick = function(){ navGo(this.dataset.v); };

    var scrim = document.createElement("div"); scrim.id = "v82scrim";
    scrim.addEventListener("click", function(){ closeDrawer(); });
    document.body.appendChild(scrim);
    var dr = document.createElement("div"); dr.id = "v82drawer"; document.body.appendChild(dr);

    /* find (search + secondary filters + discovery modules) */
    var ex = document.createElement("div"); ex.id = "v82explore"; ex.className = "v82-screen"; document.body.appendChild(ex);
    addHead("v82explore", T().find);
    /* explore hub (skew diagram + theme debates + track record) */
    var hub = document.createElement("div"); hub.id = "v82hub"; hub.className = "v82-screen"; document.body.appendChild(hub);
    addHead("v82hub", T().explore);
    /* alerts */
    var nt = document.createElement("div"); nt.id = "v82notif"; nt.className = "v82-screen"; document.body.appendChild(nt);
    addHead("v82notif", T().notif);
    /* entity picker */
    var pk = document.createElement("div"); pk.id = "v82picker"; pk.className = "v82-screen"; document.body.appendChild(pk);
    addHead("v82picker", "");
    /* generic list screen (팔로우 내역 / 공유 내역) */
    var ls = document.createElement("div"); ls.id = "v82list"; ls.className = "v82-screen"; document.body.appendChild(ls);
    addHead("v82list", "");

    /* card detail */
    var dt = document.createElement("div"); dt.id = "v82detail";
    dt.innerHTML = '<div id="v82dhead"><button id="v82back" aria-label="back">←</button><span class="t"></span></div><div id="v82dbody"></div>';
    document.body.appendChild(dt);
    $("v82back").addEventListener("click", function(){ closeDetail(false); });

    var ni = document.querySelector(".nav-inner");
    if (ni && !$("v82av")){
      var av = document.createElement("button"); av.id = "v82av"; av.textContent = "👤";
      av.setAttribute("aria-label","menu"); av.setAttribute("type","button");
      av.onclick = openDrawer;
      ni.insertBefore(av, ni.firstChild);
    }
    /* community-slide tabs inside the sticky header */
    var navEl = document.querySelector("nav");
    if (navEl && !$("v82tabs")){
      var strip = document.createElement("div"); strip.className = "v82-tabs"; strip.id = "v82tabs";
      navEl.appendChild(strip);
    }
    /* 테마논쟁/적중기록 서브뷰용 ←+제목 헤더. nav 안에 넣어 nav.nav-sub 일 때만 보인다. */
    if (navEl && !$("v82subbar")){
      var sb = document.createElement("div"); sb.id = "v82subbar";
      sb.innerHTML = '<button class="bk" aria-label="back">←</button><span class="ti"></span>';
      sb.querySelector(".bk").onclick = function(){ if (EXPLORE_SUB) closeExploreSub(false); };
      navEl.appendChild(sb);
    }
    /* 테마/기록 콘텐츠 안의 "피드로 돌아가기" 링크는 THEME_VIEW/SB_VIEW만 끄고 서브 헤더는
       남긴다. 그걸 눌러 피드로 갔을 때 nav-sub도 같이 걷어낸다(특정 테마의 "전체 테마"는
       THEME_VIEW가 유지되므로 걸리지 않는다). */
    document.addEventListener("click", function(e){
      if (!mq.matches || !EXPLORE_SUB) return;
      if (!(e.target.closest && e.target.closest(".sb-header .series-close"))) return;
      setTimeout(function(){ if (EXPLORE_SUB && !THEME_VIEW && !SB_VIEW){ EXPLORE_SUB = null; hideSubbar(); } }, 0);
    }, true);
    var hr = $("hotRail"); var hs = hr && hr.closest("section");
    if (hs) hs.setAttribute("data-v82hot","");
    relabel();
  }
  function addHead(screenId, title){
    var h = document.createElement("div"); h.className = "v82-sh"; h.id = screenId + "-h";
    h.innerHTML = '<button class="bk" aria-label="back">←</button><span class="ti"></span>';
    h.querySelector(".ti").textContent = title;
    h.querySelector(".bk").onclick = function(){ navGo("home"); };
    document.body.appendChild(h);
  }
  function relabel(){
    var t = T(); var nav = $("v82nav"); if (!nav) return;
    var keys = ["home","find","explore","cal","notif"];
    var sp = nav.querySelectorAll("button span");
    for (var i = 0; i < sp.length; i++) sp[i].textContent = t[keys[i]];
    var dh = document.querySelector("#v82dhead .t"); if (dh) dh.textContent = t.post;
    setHeadTitle("v82explore", t.find); setHeadTitle("v82hub", t.explore); setHeadTitle("v82notif", t.notif);
  }
  function setHeadTitle(id, title){ var h = $(id + "-h"); if (h){ var ti = h.querySelector(".ti"); if (ti) ti.textContent = title; } }

  /* ---------- nav visibility (persist over sheets; hide on splash/detail/drawer) ---------- */
  function refreshNav(){
    var nav = $("v82nav"); if (!nav) return;
    var hide = false;
    var intro = $("intro"); if (intro && !intro.hidden && !intro.classList.contains("out")) hide = true;
    var ob = $("onboard"); if (ob && !ob.hidden) hide = true;
    var dt = $("v82detail"); if (dt && dt.classList.contains("on")) hide = true;
    var dr = $("v82drawer"); if (dr && dr.classList.contains("on")) hide = true;
    nav.classList.toggle("v82-off", hide);
  }

  /* ---------- drawer ---------- */
  function renderDrawer(){
    var t = T(); var dr = $("v82drawer"); if (!dr) return;
    var curLang = (typeof LANG !== "undefined") ? LANG : "ko";
    var _dwT = (typeof v83T === "function") ? v83T : function(k){ return (t[k] !== undefined ? t[k] : k); };
    function _dwItem(k, icon){ return '<button class="v82dw-item" data-act="' + k + '"><span class="ic">' + icon + '</span>' + _dwT(k) + '</button>'; }
    dr.innerHTML =
      '<button class="v82dw-x" aria-label="close">&times;</button>' +
      '<div class="v82dw-brand"><span style="font-size:20px">👤</span> Stacks</div>' +
      _dwItem("home", "🏠") + _dwItem("browse", "🧭") + _dwItem("skew", "📈") +
      _dwItem("themes", "💬") + _dwItem("record", "🎯") + _dwItem("cal", "📅") +
      _dwItem("bm", "🔖") + _dwItem("alerts", "🔔") +
      /* 2026-07-25 (june): 지금 모드를 보여준다 — 다크는 달, 라이트는 해 */
      _dwItem("appearance", (typeof THEME !== "undefined" && THEME === "dark") ? "🌙" : "☀️") +
      '<button class="v82dw-item v82dw-join" data-act="join"><span class="ic">🗳️</span>' + _dwT("join") + '</button>' +
      _dwItem("me", "👤") +
      '<div class="v82dw-nl" id="v82dwNl"><div class="v82dw-nlh"><span>📧</span>' + t.nlLabel + '</div></div>' +
      '<div class="v82dw-langs">' +
        '<button data-lang="ko" class="v82dw-lb ' + (curLang === "ko" ? "on" : "") + '">한국어</button>' +
        '<button data-lang="en" class="v82dw-lb ' + (curLang === "en" ? "on" : "") + '">English</button>' +
        '<button data-lang="ja" class="v82dw-lb ' + (curLang === "ja" ? "on" : "") + '">日本語</button>' +
      '</div>';
    dr.querySelector(".v82dw-x").onclick = function(){ closeDrawer(); };
    var acts = dr.querySelectorAll("[data-act]");
    for (var ai = 0; ai < acts.length; ai++){ acts[ai].onclick = function(){ drawerAct(this.dataset.act); }; }
    var lbs = dr.querySelectorAll(".v82dw-lb");
    for (var li = 0; li < lbs.length; li++){ lbs[li].onclick = function(){ closeDrawer(true); if (typeof setLang === "function") setLang(this.dataset.lang); }; }
    /* relocate the newsletter subscribe box into the profile drawer */
    try {
      var nl = $("nlSec"), holder = $("v82dwNl");
      if (nl && holder){
        nl.hidden = false;
        if (!nl.querySelector("form,iframe,input,button,a") && typeof renderNewsletter === "function") renderNewsletter();
        holder.appendChild(nl);
      }
    } catch(e){}
  }
  function drawerAct(act){
    if (act === "me"){ closeDrawer(true); if (typeof openMe === "function") openMe(); }
    else if (act === "home"){ closeDrawer(true); navGo("home"); }
    else if (act === "browse"){ closeDrawer(true); navGo("find"); }
    else if (act === "skew"){ closeDrawer(true); navGo("explore"); }
    else if (act === "themes"){ closeDrawer(true); if (typeof openThemes === "function") openThemes(); try { setActive(); } catch(e){} }
    else if (act === "record"){ closeDrawer(true); if (typeof openScoreboard === "function") openScoreboard(); try { setActive(); } catch(e){} }
    else if (act === "cal"){ closeDrawer(true); navGo("cal"); }
    else if (act === "alerts"){ closeDrawer(true); navGo("notif"); }
    else if (act === "appearance"){ closeDrawer(true); if (typeof toggleTheme === "function") toggleTheme(); }
    else if (act === "join"){ closeDrawer(true); if (typeof TODAY_ID !== "undefined" && TODAY_ID && typeof openCardById === "function") openCardById(TODAY_ID); else navGo("home"); }
    else if (act === "bm"){ closeDrawer(true); goHomeThen(function(){ try { SERIES_VIEW=null; ENTITY_VIEW=null; QUERY=""; BM_ONLY=true; renderFeed(false); } catch(e){} }); }
    else if (act === "follows"){ closeDrawer(true); openList("follows"); }
    else if (act === "shares"){ closeDrawer(true); openList("shares"); }
    else closeDrawer();
  }
  function openDrawer(){
    if (!mq.matches) return;
    renderDrawer();
    $("v82drawer").classList.add("on"); $("v82scrim").classList.add("on");
    refreshNav();
    if (typeof pushView === "function") pushView();
  }
  function closeDrawer(fromPop){
    var dr = $("v82drawer");
    if (!dr || !dr.classList.contains("on")) return false;
    dr.classList.remove("on"); $("v82scrim").classList.remove("on");
    refreshNav();
    if (!fromPop) silentBack();
    return true;
  }

  /* ---------- generic screen show/hide ---------- */
  function showScreen(id){
    var s = $(id), h = $(id + "-h");
    if (!s) return;
    s.classList.add("on"); if (h) h.classList.add("on");
    s.scrollTop = 0;
    document.body.style.overflow = "hidden";
    if (typeof pushView === "function") pushView();
  }
  function hideScreen(id){
    var s = $(id), h = $(id + "-h");
    if (!s || !s.classList.contains("on")) return false;
    s.classList.remove("on"); if (h) h.classList.remove("on");
    document.body.style.overflow = "";
    return true;
  }
  function anyScreenOpen(){
    return ["v82explore","v82hub","v82notif","v82picker","v82list"].some(function(id){ var s=$(id); return s && s.classList.contains("on"); });
  }

  /* ---------- FIND (search + secondary filters + discovery modules) ---------- */
  var EX_HOMES = null;
  function findNodes(){
    var hr = $("hotRail"); var hs = hr && hr.closest("section");
    /* todaySec now pins to the feed top; nlSec now lives in the profile drawer */
    return [$("searchBox"), $("eventBar"), hs, $("watchSec")].filter(Boolean);
  }
  /* ---------- 최근 검색 (2026-07-25, june 모바일 전수조사) ----------
     X는 검색창을 열면 최근 검색어부터 보여준다. 우리는 곧장 추천 목록이라
     방금 찾던 걸 다시 치려면 처음부터 타이핑해야 했다. 기기 로컬에만 남긴다. */
  var RQ_KEY = "stk_recentq", RQ_MAX = 8;
  function rqGet(){
    try { var v = JSON.parse(localStorage.getItem(RQ_KEY) || "[]"); return Array.isArray(v) ? v.slice(0, RQ_MAX) : []; }
    catch(e){ return []; }
  }
  function rqSave(list){ try { localStorage.setItem(RQ_KEY, JSON.stringify(list.slice(0, RQ_MAX))); } catch(e){} }
  function rqAdd(q){
    q = (q || "").trim(); if (q.length < 2) return;
    var l = rqGet().filter(function(x){ return x.toLowerCase() !== q.toLowerCase(); });
    l.unshift(q); rqSave(l);
  }
  function rqRender(ex){
    var box = $("v82recentQ");
    if (!box){ box = document.createElement("div"); box.id = "v82recentQ"; }
    if (box.parentNode !== ex) ex.appendChild(box);
    var list = rqGet(), t = T();
    if (!list.length){ box.innerHTML = ""; box.style.display = "none"; return box; }
    box.style.display = "";
    box.innerHTML = '<div class="v82rq-h"><h3>' + esc(t.recentQ) + '</h3>'
      + '<button type="button" class="v82rq-clr">' + esc(t.recentClear) + '</button></div>'
      + list.map(function(q){
          return '<div class="v82rq-row"><button type="button" class="v82rq-q" data-q="' + esc(q) + '">'
            + '<span class="v82rq-ic">🕘</span><span>' + esc(q) + '</span></button>'
            + '<button type="button" class="v82rq-x" data-del="' + esc(q) + '" aria-label="' + esc(t.recentDel) + '">&#x2715;</button></div>';
        }).join("");
    box.querySelector(".v82rq-clr").onclick = function(){ rqSave([]); rqRender(ex); };
    box.querySelectorAll(".v82rq-q").forEach(function(b){
      b.onclick = function(){
        var si = $("searchInput"); if (!si) return;
        si.value = this.dataset.q;
        si.dispatchEvent(new Event("input", { bubbles: true }));
      };
    });
    box.querySelectorAll(".v82rq-x").forEach(function(b){
      b.onclick = function(){
        var q = this.dataset.del;
        rqSave(rqGet().filter(function(x){ return x !== q; }));
        rqRender(ex);
      };
    });
    return box;
  }

  /* rbeta 찾기: 나를 위한 추천 / 인기 / 이번 주 핫한 읽을거리 (compact Twitter-style lists) */
  function buildFindDisco(ex){
    var dd = $("v82findDisco");
    if (!dd){ dd = document.createElement("div"); dd.id = "v82findDisco"; }
    ex.appendChild(dd);
    var S = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG] : {};
    var L = ({ ko:["나를 위한 추천","인기"], en:["For you","Popular"], ja:["あなたへのおすすめ","人気"] })[LANG] || ["나를 위한 추천","인기"];
    var score = function(i){ return (VIEW_COUNTS[i.id]||0) + (LIKE_COUNTS[i.id]||0)*3 + (COMMENT_COUNTS[i.id]||0)*2; };
    var used = {};
    var mine = [];
    try { mine = ITEMS.filter(function(i){ return mineReasons(i).length; }).sort(function(a,b){ return a.date<b.date?1:-1; }).slice(0,4); } catch(e){ mine = []; }
    if (!mine.length) mine = ITEMS.slice().sort(function(a,b){ return a.date<b.date?1:-1; }).slice(0,4);
    mine.forEach(function(i){ used[i.id]=1; });
    var pop = ITEMS.slice().sort(function(a,b){ return score(b)-score(a) || (a.date<b.date?1:-1); })
      .filter(function(i){ return !used[i.id]; }).slice(0,5);
    pop.forEach(function(i){ used[i.id]=1; });
    var cutoff = new Date(Date.now()-7*86400*1000).toISOString().slice(0,10);
    var hot = ITEMS.filter(function(i){ return i.hot || i.date>=cutoff; })
      .sort(function(a,b){ return a.date<b.date?1:-1; }).slice(0,8);
    function row(i){
      var v = VIEW_COUNTS[i.id]||0, c = COMMENT_COUNTS[i.id]||0;
      var meta = esc(dispName(i.source)) + " · " + fmt(i.date) + " · " + (S.views||"조회수") + " " + v + (c ? " · 💬 " + c : "");
      return '<button type="button" class="v82fd-row" data-id="' + i.id + '">'
        + '<span class="v82fd-t">' + esc(i.title[LANG]||i.title.en) + '</span>'
        + '<span class="v82fd-m">' + meta + '</span></button>';
    }
    function sec(title, list){ return list.length ? '<div class="v82fd-sec"><h3>' + esc(title) + '</h3>' + list.map(row).join("") + '</div>' : ""; }
    dd.innerHTML = sec(L[0], mine) + sec(L[1], pop) + sec(S.hot||"이번 주 핫한 읽을거리", hot);
    var rows = dd.querySelectorAll(".v82fd-row");
    for (var r = 0; r < rows.length; r++) rows[r].onclick = function(){ openCardById(this.dataset.id); };
  }
  function openFind(){
    if (!mq.matches) return;
    var ex = $("v82explore"); if (!ex) return;
    /* 이미 열려 있으면 최근 검색 목록만 갱신한다 — 결과를 탭해 상세로 갔다가
       돌아오면 화면은 그대로라서, 방금 친 검색어가 안 보이는 문제가 있었다 */
    if (ex.classList.contains("on")){ try { rqRender(ex); } catch(e){} return; }
    try {
      /* rbeta: Twitter-style discover — search on top, then 추천/인기/이번 주 핫한 읽을거리 */
      if (typeof RBETA !== "undefined" && RBETA){
        var sb0 = $("searchBox");
        EX_HOMES = sb0 ? [{ el: sb0, parent: sb0.parentNode, next: sb0.nextSibling }] : [];
        if (sb0) ex.appendChild(sb0);
        var res0 = $("v82findResults");
        if (!res0){ res0 = document.createElement("div"); res0.id = "v82findResults"; }
        res0.innerHTML = ""; res0.style.display = "none";
        ex.appendChild(res0);
        rqRender(ex);
        buildFindDisco(ex);
        var sif = $("searchInput"); if (sif) sif.focus();
        showScreen("v82explore");
        v82Search((typeof QUERY !== "undefined") ? QUERY : "");
        setActive();
        return;
      }
      var nodes = findNodes();
      EX_HOMES = nodes.map(function(el){ return { el: el, parent: el.parentNode, next: el.nextSibling }; });
      /* small filter-button row */
      var fr = document.createElement("div"); fr.className = "filter-row"; fr.id = "v82findFilters";
      ["sortBtn","bmFilter","freeFilter","unreadFilter"].forEach(function(bid){ var b=$(bid); if(b){ fr.appendChild(b); } });
      ex.appendChild($("searchBox"));
      ex.appendChild(fr);
      /* dedicated results list shown only while a query is active */
      var res = $("v82findResults");
      if (!res){ res = document.createElement("div"); res.id = "v82findResults"; }
      res.innerHTML = ""; res.style.display = "none";
      ex.appendChild(res);
      nodes.forEach(function(el){ if (el.id !== "searchBox") ex.appendChild(el); });
      var si = $("searchInput"); if (si) si.focus();
      showScreen("v82explore");
      v82Search((typeof QUERY !== "undefined") ? QUERY : "");
    } catch(err){ hideScreen("v82explore"); document.body.style.overflow=""; }
    setActive();
  }
  /* render search results inside the Find screen (the feed itself is on the
     home screen behind this overlay, so results must render here). */
  function v82Search(q){
    if (!mq.matches) return;
    var ex = $("v82explore"); if (!ex || !ex.classList.contains("on")) return;
    var res = $("v82findResults"); if (!res) return;
    q = (q || "").trim();
    var discovery = [];
    var ff = $("v82findFilters"); if (ff) discovery.push(ff);
    var rq = $("v82recentQ"); if (rq) discovery.push(rq);
    var dd = $("v82findDisco"); if (dd) discovery.push(dd);
    if (EX_HOMES) EX_HOMES.forEach(function(h){ if (h.el && h.el.id !== "searchBox") discovery.push(h.el); });
    if (!q){
      res.style.display = "none"; res.innerHTML = "";
      discovery.forEach(function(el){ el.style.display = ""; });
      rqRender(ex);   /* 목록이 비면 스스로 숨는다 */
      return;
    }
    discovery.forEach(function(el){ el.style.display = "none"; });
    var S = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG] : {};
    var hits = [];
    try { hits = ITEMS.filter(function(it){ return matchesQuery(it); }); } catch(e){ hits = []; }
    var html = "";
    if (!hits.length){ html = '<div class="v82-empty">' + (S.searchNone || "결과가 없어요.") + '</div>'; }
    else hits.slice(0, 60).forEach(function(it, i){
      var snip = (it.gist && it.gist[LANG]) ? v82Plain(it.gist[LANG]).slice(0, 90) : "";
      html += '<button class="v82-sr" data-id="' + esc(it.id) + '">'
        + '<div class="v82-sr-t">' + esc(it.title[LANG]) + '</div>'
        + '<div class="v82-sr-m">' + esc(dispName(it.source)) + '</div>'
        + (snip ? '<div class="v82-sr-s">' + esc(snip) + '…</div>' : "")
        + '</button>';
    });
    res.innerHTML = html; res.style.display = "block";
    var btns = res.querySelectorAll(".v82-sr");
    for (var b = 0; b < btns.length; b++){
      btns[b].onclick = function(){
        var id = this.dataset.id;
        var si = $("searchInput");                 /* 입력한 그대로(대소문자 보존) 저장 */
        rqAdd(si && si.value ? si.value : q);
        openCardById(id);
      };
    }
  }
  window.v82Search = v82Search;
  function closeFind(fromPop){
    var ex = $("v82explore");
    if (!ex || !ex.classList.contains("on")) return false;
    hideScreen("v82explore");
    /* restore filter buttons to the app filter-row, then relocated nodes home */
    var appFilter = document.querySelector("#feed .filter-row");
    ["sortBtn","bmFilter","freeFilter","unreadFilter"].forEach(function(bid){ var b=$(bid); if(b&&appFilter){ appFilter.appendChild(b); } });
    var ff = $("v82findFilters"); if (ff) ff.remove();
    try { var _si = $("searchInput"); if (_si) rqAdd(_si.value); } catch(e){}
    var rz = $("v82findResults"); if (rz){ rz.style.display = "none"; rz.innerHTML = ""; }
    if (EX_HOMES){
      EX_HOMES.forEach(function(h){ if (h.el) h.el.style.display = ""; }); /* clear search-mode hiding */
      for (var i = EX_HOMES.length - 1; i >= 0; i--){
        var h = EX_HOMES[i];
        if (h.el.parentNode === ex) continue;
        if (h.parent && h.parent.isConnected){
          if (h.next && h.next.parentNode === h.parent) h.parent.insertBefore(h.el, h.next);
          else h.parent.appendChild(h.el);
        }
      }
      /* searchBox/others may still be in ex if not caught above */
      EX_HOMES.forEach(function(h){ if (h.el.parentNode === ex && h.parent && h.parent.isConnected){ if(h.next&&h.next.parentNode===h.parent) h.parent.insertBefore(h.el,h.next); else h.parent.appendChild(h.el); } });
      EX_HOMES = null;
    }
    if (!fromPop) silentBack();
    setActive();
    return true;
  }

  /* ---------- EXPLORE hub (skew diagram + themes + record) ---------- */
  function skewData(){
    var out = [];
    try {
      Object.keys(THEMES).forEach(function(k){
        var t = stanceTally(themeItems(k)); var dir = t.bull + t.bear;
        if (dir < 1) return;
        out.push({ kind:"theme", key:k, label:THEMES[k].label[LANG], icon:THEMES[k].icon, bull:t.bull, bear:t.bear });
      });
      var byEnt = {};
      ITEMS.forEach(function(it){ if(!itemStance(it)) return; itemEntities(it).forEach(function(e){ if(ENTITIES[e]&&ENTITIES[e].kind==="company"){ (byEnt[e]=byEnt[e]||[]).push(it); } }); });
      Object.keys(byEnt).forEach(function(e){
        var t = stanceTally(byEnt[e]); var dir = t.bull + t.bear;
        if (dir < 3) return;
        out.push({ kind:"ent", key:e, label:entName(e), icon:"", bull:t.bull, bear:t.bear });
      });
    } catch(e){}
    out.forEach(function(o){ var d=o.bull+o.bear; o.pct = d? Math.max(o.bull,o.bear)/d : 0; o.side = o.bull>=o.bear?"bull":"bear"; });
    out.sort(function(a,b){ return (b.pct-a.pct) || ((b.bull+b.bear)-(a.bull+a.bear)); });
    return out;
  }
  function renderHub(){
    var hub = $("v82hub"); if (!hub) return;
    var t = T(), S = (typeof STRINGS!=="undefined"&&STRINGS[LANG])?STRINGS[LANG]:{};
    var rows = skewData();
    /* 2026-07-25 (june): 모바일에도 "내 브리핑"이 필요하다. 탐색 탭은 이미 전체 쏠림을
       보여주므로, 같은 성격의 개인 버전을 그 위에 둔다. 팔로우가 없으면 통째로 생략한다.
       판정 로직(watchWeekSignal/watchWeekSubjects)은 데스크톱과 완전히 공유한다. */
    var html = "";
    try {
      if (typeof WATCH !== "undefined" && typeof watchWeekSignal === "function"){
        /* WATCH는 Set이다 — slice.call 은 빈 배열을 돌려준다 */
        var mine = Array.from(WATCH).filter(function(k){ return ENTITIES[k]; })
          .map(function(k){ return { k: k, sig: watchWeekSignal(k) }; })
          .sort(function(a, b){
            return (a.sig.rank - b.sig.rank)
              || ((b.sig.bull + b.sig.bear) - (a.sig.bull + a.sig.bear))
              || a.k.localeCompare(b.k);
          });
        if (mine.length){
          html += '<div class="v82-skew-h">' + esc(S.briefTitle || "") + '</div>'
                + '<div class="v82-skew-sub">' + esc(S.briefSub || "") + '</div>';
          mine.forEach(function(o){
            var sig = o.sig;
            var isCo = !!(ENTITIES[o.k] && ENTITIES[o.k].kind === "company");
            /* 인물은 강세/약세 판정을 붙이지 않는다 — 소재에 방향성을 얹는 카테고리 오류라서 */
            var verdict = !isCo ? (S.briefThin || "").replace("{n}", sig.n)
              : sig.kind === "split" ? S.briefSplit
              : sig.kind === "bull" ? S.briefLeanBull
              : sig.kind === "bear" ? S.briefLeanBear
              : (S.briefThin || "").replace("{n}", sig.n);
            var subs = isCo ? [] : (typeof watchWeekSubjects === "function" ? watchWeekSubjects(o.k) : []);
            var dir = (isCo && sig.kind !== "thin") ? sig.bull + sig.bear : 0, bp = dir ? Math.round(sig.bull / dir * 100) : 0;
            html += '<button class="v82-skew-row v82-brief-row" data-brief="' + esc(o.k) + '">'
              + '<div class="v82-skew-top"><span class="v82-skew-name">' + esc(typeof entName === "function" ? entName(o.k) : o.k) + '</span>'
              + '<span class="v82-skew-lean ' + (sig.kind === "bear" ? "bear" : "bull") + '">' + esc(verdict) + '</span></div>'
              + (dir ? '<div class="v82-skew-track"><i class="b" style="width:' + bp + '%"></i><i class="r" style="width:' + (100 - bp) + '%"></i></div>' : "")
              + (subs.length ? '<div class="v82-brief-subj">' + esc((S.briefTopics || "{s}").replace("{s}", subs.join(" · "))) + '</div>' : "")
              + (dir ? '<div class="v82-skew-cts"><span>' + t.bull + ' ' + sig.bull + '</span><span>' + t.bear + ' ' + sig.bear + '</span></div>' : "")
              + '</button>';
          });
        }
      }
    } catch (e){}
    /* 2026-07-25 (june): 지금 쏠린곳도 테마논쟁·적중기록처럼 메뉴 항목으로. 목록은 서브뷰에서 */
    html += '<div class="v82-hub-sec">' + t.skewTitle + '</div>';
    html += '<button class="v82-hub-item" data-open="skew"><span class="em">📊</span>' + t.skewTitle + '<span class="ar">›</span></button>';
    html += '<div class="v82-hub-sec">' + t.themesSec + '</div>';
    html += '<button class="v82-hub-item" data-open="themes"><span class="em">◧</span>' + t.openThemes + '<span class="ar">›</span></button>';
    html += '<div class="v82-hub-sec">' + t.recordSec + '</div>';
    html += '<button class="v82-hub-item" data-open="record"><span class="em">⚖</span>' + t.openRecord + '<span class="ar">›</span></button>';
    html += '<div class="v82-hub-sec">' + t.communitySec + '<span class="v82-soon">' + t.communitySoon + '</span></div>';
    html += '<div class="v82-comm"><div class="v82-comm-h"><span class="em">👥</span>' + t.community + '</div>'
      + '<p class="v82-comm-d">' + esc(t.communityDesc) + '</p></div>';
    var head = hub.querySelector(".v82-inner");
    if (!head){ head = document.createElement("div"); head.className = "v82-inner"; hub.appendChild(head); }
    head.innerHTML = html;
    var brows = head.querySelectorAll("[data-brief]");
    for (var bi = 0; bi < brows.length; bi++){
      brows[bi].onclick = function(){
        var k = this.dataset.brief;
        hubOpenView(function(){ if (typeof entityFeedView === "function") entityFeedView(k); });
      };
    }
    var opens = head.querySelectorAll("[data-open]");
    for (var j = 0; j < opens.length; j++){
      opens[j].onclick = function(){
        var w = this.dataset.open;
        if (w === "skew") openSkewSub();
        else if (w === "themes") openThemesSub();
        else if (w === "record") openRecordSub();
      };
    }
  }

  /* ---------- 탐색 서브뷰 (지금쏠린곳 / 테마논쟁 / 적중기록) ---------- */
  /* 지금 쏠린곳: 허브 화면 안에서 콘텐츠만 스킴 목록으로 바꾼다(같은 화면, 한 스텝). */
  function skewSubHtml(){
    var t = T(), rows = skewData(), html = "";
    html += '<div class="v82-skew-sub" style="margin-top:2px">' + t.skewSub + '</div>';
    if (!rows.length){
      html += '<div class="v82-empty">아직 쏠림을 계산할 데이터가 부족합니다.</div>';
    } else {
      rows.forEach(function(o, idx){
        var dir = o.bull + o.bear, bp = dir ? Math.round(o.bull / dir * 100) : 0, rp = 100 - bp;
        var leanLb = (o.side === "bull" ? t.bull : t.bear) + " " + Math.round(o.pct * 100) + "%";
        html += '<button class="v82-skew-row" data-i="' + idx + '">'
          + '<div class="v82-skew-top"><span class="v82-skew-name">' + (o.icon ? o.icon + " " : "") + esc(o.label) + '</span>'
          + '<span class="v82-skew-lean ' + o.side + '">' + esc(leanLb) + '</span></div>'
          + '<div class="v82-skew-track"><i class="b" style="width:' + bp + '%"></i><i class="r" style="width:' + rp + '%"></i></div>'
          + '<div class="v82-skew-cts"><span>' + t.bull + ' ' + o.bull + '</span><span>' + t.bear + ' ' + o.bear + '</span></div></button>';
      });
    }
    return html;
  }
  function renderSkewSub(){
    var hub = $("v82hub"); if (!hub) return;
    var head = hub.querySelector(".v82-inner");
    if (!head){ head = document.createElement("div"); head.className = "v82-inner"; hub.appendChild(head); }
    var rows = skewData();
    head.innerHTML = skewSubHtml();
    var srows = head.querySelectorAll(".v82-skew-row");
    for (var i = 0; i < srows.length; i++){
      srows[i].onclick = function(){
        var o = rows[+this.dataset.i]; if (!o) return;
        HUB_SUB = null;                       /* 허브를 통째로 떠난다 */
        closeHub(true); silentBack();
        try { if (o.kind === "theme" && typeof openTheme === "function") openTheme(o.key);
              else if (typeof entityFeedView === "function") entityFeedView(o.key); } catch (e) {}
        setActive();
      };
    }
  }
  function openSkewSub(){
    HUB_SUB = "skew";
    renderSkewSub();
    setHeadTitle("v82hub", T().skewTitle);
    var hub = $("v82hub"); if (hub) hub.scrollTop = 0;
    if (typeof pushView === "function") pushView();
    setActive();
  }
  function closeHubSub(fromPop){
    HUB_SUB = null;
    renderHub();
    setHeadTitle("v82hub", T().explore);
    var hub = $("v82hub"); if (hub) hub.scrollTop = 0;
    if (!fromPop) silentBack();
    setActive();
  }

  /* 테마논쟁 / 적중기록: 피드에 렌더된다. 허브 화면을 숨기고 nav를 ←+제목으로 바꾼다. */
  function topNav(){ return document.querySelector("nav"); }
  function showSubbar(title){
    var n = topNav(); if (!n) return;
    var ti = document.querySelector("#v82subbar .ti"); if (ti) ti.textContent = title || "";
    n.classList.add("nav-sub");
  }
  function hideSubbar(){ var n = topNav(); if (n) n.classList.remove("nav-sub"); }
  function toTop(){
    try { window.scrollTo(0, 0); } catch (e) {}
    requestAnimationFrame(function(){ try { window.scrollTo(0, 0); } catch (e) {} });
  }
  function openThemesSub(){
    EXPLORE_SUB = "themes";
    closeHub(true);                           /* 허브 화면만 숨긴다(히스토리 유지) */
    try { if (typeof openThemes === "function") openThemes(); } catch (e) {}
    showSubbar(T().themesSec); toTop(); setActive();
  }
  function openRecordSub(){
    EXPLORE_SUB = "record";
    closeHub(true);
    try { if (typeof openScoreboard === "function") openScoreboard(); } catch (e) {}
    showSubbar(T().recordSec); toTop(); setActive();
  }
  function showHubSilent(){
    var hub = $("v82hub"), h = $("v82hub-h"); if (!hub) return;
    HUB_SUB = null; renderHub(); setHeadTitle("v82hub", T().explore);
    hub.classList.add("on"); if (h) h.classList.add("on");
    hub.scrollTop = 0; document.body.style.overflow = "hidden";
  }
  function closeExploreSub(fromPop){
    var was = EXPLORE_SUB; EXPLORE_SUB = null;
    try { if (was === "themes" && typeof closeThemes === "function") closeThemes();
          else if (was === "record" && typeof closeScoreboard === "function") closeScoreboard(); } catch (e) {}
    hideSubbar();
    showHubSilent();                          /* 피드 위에 허브를 다시 띄운다(pushView 없음) */
    if (!fromPop) silentBack();               /* 헤더 ←: 테마/기록 히스토리 엔트리를 걷어낸다 */
    setActive();
  }
  /* 홈/탐색/찾기 등으로 강제 이탈할 때 서브 상태만 정리(히스토리/허브 재오픈 없음) */
  function clearSubState(){
    if (EXPLORE_SUB){
      var was = EXPLORE_SUB; EXPLORE_SUB = null;
      try { if (was === "themes" && typeof closeThemes === "function") closeThemes();
            else if (was === "record" && typeof closeScoreboard === "function") closeScoreboard(); } catch (e) {}
    }
    hideSubbar();
    if (HUB_SUB){
      HUB_SUB = null; setHeadTitle("v82hub", T().explore);
      if ($("v82hub") && $("v82hub").classList.contains("on")){ renderHub(); $("v82hub").scrollTop = 0; }
    }
  }
  function hubOpenView(fn){ closeHub(true); silentBack(); try { fn(); } catch(e){} setActive(); }
  function openHub(){
    if (!mq.matches) return;
    var hub = $("v82hub"); if (!hub || hub.classList.contains("on")) return;
    HUB_SUB = null; setHeadTitle("v82hub", T().explore);   /* 항상 메뉴로 열린다 */
    renderHub();
    showScreen("v82hub");
    setActive();
  }
  function closeHub(fromPop){
    if (!hideScreen("v82hub")) return false;
    if (!fromPop) silentBack();
    setActive();
    return true;
  }

  /* ---------- ALERTS + notification settings ---------- */
  function notifPref(){
    var d = { newpost:true, debate:true, follow:true, eventsMaster:true, events:{} };
    try { var s = store.get("stk_notif", null); if (s && typeof s === "object"){ d.newpost=s.newpost!==false; d.debate=s.debate!==false; d.follow=s.follow!==false; d.eventsMaster=s.eventsMaster!==false; d.events=s.events||{}; } } catch(e){}
    return d;
  }
  function setNotifPref(key, on, evId){
    var p = notifPref();
    if (evId != null){ p.events = p.events || {}; p.events[evId] = on; }
    else { p[key] = on; }
    try { store.set("stk_notif", p); } catch(e){}
    try { if (typeof osTag === "function") osTag(evId != null ? ("evt_" + evId) : ("np_" + key), on); } catch(e){}
  }
  function upcomingEvents(){
    var out = [];
    try {
      if (typeof EVENTS === "undefined") return out;
      var today = new Date(); today.setHours(0,0,0,0);
      EVENTS.forEach(function(e){ var days = Math.round((new Date(e.date+"T00:00:00") - today)/86400000); if (days >= 0) out.push({ id:e.id, label:e.label, date:e.date, days:days }); });
      out.sort(function(a,b){ return a.days - b.days; });
    } catch(e){}
    return out;
  }
  function notifSettingsHtml(){
    var t = T(), np = notifPref();
    var sw = function(key, label, on){ return '<button class="v82-nset" data-np="'+key+'"><span class="v82-nset-l">'+esc(label)+'</span><span class="v82-sw'+(on?' on':'')+'"></span></button>'; };
    var h = '<div class="v82-nset-h">'+esc(t.nsTitle)+'</div>'
      + sw("newpost", t.nsNew, np.newpost)
      + sw("debate", t.nsDebate, np.debate)
      + sw("follow", t.nsFollow, np.follow);
    /* events: a master row you tap to expand your subscribed events (opt in via the bell on each event) */
    var subs = upcomingEvents().filter(function(ev){ return np.events && np.events[ev.id]; });
    h += '<div class="v82-evwrap">'
      + '<div class="v82-nset v82-evhead" data-evexpand><span class="v82-nset-l">'+esc(t.nsEvents)+' <i class="v82-evcaret">▾</i></span><span class="v82-sw'+(np.eventsMaster?' on':'')+'" data-npmaster="1"></span></div>'
      + '<div class="v82-evlist" id="v82evlist" style="display:none">';
    if (!subs.length){ h += '<div class="v82-nset-empty">'+esc(t.nsEvSubEmpty)+'</div>'; }
    else subs.forEach(function(ev){
      var d = ev.days === 0 ? "D-day" : "D-"+ev.days;
      h += '<button class="v82-nset v82-evrow" data-evt="'+esc(ev.id)+'"><span class="v82-nset-l">'+esc(ev.label[LANG])+' <i>'+d+'</i></span><span class="v82-sw on"></span></button>';
    });
    h += '</div></div>';
    return h + '<div class="v82-nset-div"></div>'
      + (window.stkNlHtml ? window.stkNlHtml() : "")
      + '<div class="v82-nset-div"></div><div class="v82-nset-h">'+esc(t.nsRecent)+'</div>';
  }
  function renderNotif(){
    var nt = $("v82notif"); if (!nt) return;
    var t = T(), S = (typeof STRINGS!=="undefined"&&STRINGS[LANG])?STRINGS[LANG]:{}, rows = [];
    try {
      /* new posts */
      if (typeof NEW_IDS !== "undefined"){
        ITEMS.filter(function(i){ return NEW_IDS.has(i.id); }).slice(0,6).forEach(function(i){
          rows.push({ em:"🆕", t1:t.ntNew, t2:i.title[LANG], id:i.id });
        });
      }
      /* graded / pending outcomes */
      ITEMS.filter(function(i){ return i.outcome && (i.outcome.status==="hit"||i.outcome.status==="miss"); }).slice(0,4).forEach(function(i){
        rows.push({ em: i.outcome.status==="hit"?"✅":"❌", t1:t.ntGrade, t2:i.title[LANG], id:i.id });
      });
      /* today's debate */
      if (typeof TODAY_ID !== "undefined" && TODAY_ID){
        var td = null; for (var k=0;k<ITEMS.length;k++) if (ITEMS[k].id===TODAY_ID){ td=ITEMS[k]; break; }
        if (td && td.ask) rows.push({ em:"💬", t1:t.ntDebate, t2:td.ask[LANG], id:td.id });
      }
      /* strong skews */
      skewData().filter(function(o){ return o.pct>=0.8 && (o.bull+o.bear)>=3; }).slice(0,4).forEach(function(o){
        rows.push({ em:"⚠️", t1:t.ntSkew, t2:(o.icon?o.icon+" ":"")+o.label+" · "+(o.side==="bull"?t.bull:t.bear)+" "+Math.round(o.pct*100)+"%",
          theme:o.kind==="theme"?o.key:null, ent:o.kind==="ent"?o.key:null });
      });
    } catch(e){}
    var html = notifSettingsHtml();
    if (!rows.length) html += '<div class="v82-empty">' + t.noAlerts + '</div>';
    else rows.forEach(function(r, i){
      html += '<button class="v82-nt" data-i="' + i + '"><span class="em">' + r.em + '</span>'
        + '<span class="bd"><span class="t1">' + esc(r.t1) + '</span>'
        + '<span class="t2">' + esc(r.t2||"") + '</span></span></button>';
    });
    var inner = nt.querySelector(".v82-inner");
    if (!inner){ inner = document.createElement("div"); inner.className = "v82-inner"; nt.appendChild(inner); }
    inner.innerHTML = html;
    /* wire the settings toggles */
    inner.querySelectorAll("[data-np]").forEach(function(b){
      b.onclick = function(){ var sw = b.querySelector(".v82-sw"); var on = !sw.classList.contains("on"); sw.classList.toggle("on", on); setNotifPref(b.getAttribute("data-np"), on); };
    });
    if (window.stkNlWire) window.stkNlWire(inner);
    /* events master toggle (does not expand) */
    var mrow = inner.querySelector("[data-evexpand]");
    if (mrow){
      var msw = mrow.querySelector("[data-npmaster]");
      if (msw) msw.onclick = function(ev){ ev.stopPropagation(); var on = !msw.classList.contains("on"); msw.classList.toggle("on", on); setNotifPref("eventsMaster", on); };
      mrow.onclick = function(){ var lst = $("v82evlist"); var car = mrow.querySelector(".v82-evcaret"); if (!lst) return; var open = lst.style.display !== "none"; lst.style.display = open ? "none" : "block"; if (car) car.style.transform = open ? "" : "rotate(180deg)"; };
    }
    /* tapping a subscribed event unsubscribes it and refreshes the list */
    inner.querySelectorAll(".v82-evrow[data-evt]").forEach(function(b){
      b.onclick = function(){ setNotifPref(null, false, b.getAttribute("data-evt")); var lst0 = $("v82evlist"); var wasOpen = lst0 && lst0.style.display !== "none"; renderNotif(); var lst = $("v82evlist"); if (lst && wasOpen){ lst.style.display = "block"; var car = inner.querySelector(".v82-evcaret"); if (car) car.style.transform = "rotate(180deg)"; } };
    });
    var btns = inner.querySelectorAll(".v82-nt");
    for (var i2 = 0; i2 < btns.length; i2++){
      (function(r){
        btns[i2].onclick = function(){
          if (r.id){ closeNotif(true); silentBack(); openCardById(r.id); }
          else if (r.theme){ closeNotif(true); silentBack(); if (typeof openTheme==="function") openTheme(r.theme); setActive(); }
          else if (r.ent){ closeNotif(true); silentBack(); if (typeof entityFeedView==="function") entityFeedView(r.ent); setActive(); }
        };
      })(rows[+btns[i2].dataset.i]);
    }
  }
  window.v82RefreshNotif = function(){ try { var nt = $("v82notif"); if (nt && nt.classList.contains("on")) renderNotif(); } catch(e){} };
  function openNotif(){
    if (!mq.matches) return;
    var nt = $("v82notif"); if (!nt || nt.classList.contains("on")) return;
    renderNotif();
    showScreen("v82notif");
    setActive();
  }
  function closeNotif(fromPop){
    if (!hideScreen("v82notif")) return false;
    if (!fromPop) silentBack();
    setActive();
    return true;
  }

  /* ---------- generic list (팔로우 내역 / 공유 내역) ---------- */
  function listRows(kind){
    var rows = [];
    try {
      if (kind === "follows"){
        var t = T();
        if (typeof WATCH !== "undefined" && WATCH.forEach){
          WATCH.forEach(function(k){
            if (typeof ENTITIES !== "undefined" && ENTITIES[k]){
              var e = ENTITIES[k], person = e.kind === "person";
              var nm = e.name || e.label || (e.aliases && e.aliases[0]) || k;
              rows.push({ em: person ? "👤" : "🏢", t1: nm, t2: person ? t.followsPeople : t.followsCompany, ent: k });
            }
          });
        }
        if (typeof FOLLOWED !== "undefined" && FOLLOWED.forEach && typeof SERIES !== "undefined"){
          FOLLOWED.forEach(function(sid){
            if (SERIES[sid]) rows.push({ em: "📚", t1: (SERIES[sid].name && SERIES[sid].name[LANG]) || sid, t2: t.followsSeries, series: sid });
          });
        }
      } else if (kind === "shares"){
        var ids = [];
        try { ids = store.get("stk_shares", []); } catch(e){ ids = []; }
        ids.forEach(function(id){
          for (var i = 0; i < ITEMS.length; i++){ if (ITEMS[i].id === id){ rows.push({ em:"↗️", t1: ITEMS[i].title[LANG], t2: dispName(ITEMS[i].source), id: id }); break; } }
        });
      }
    } catch(e){}
    return rows;
  }
  function renderList(kind){
    var ls = $("v82list"); if (!ls) return;
    var t = T();
    var rows = listRows(kind);
    var html = "";
    if (!rows.length){ html = '<div class="v82-empty">' + (kind === "shares" ? t.emptyShares : t.emptyFollows) + '</div>'; }
    else rows.forEach(function(r, i){
      html += '<button class="v82-nt" data-i="' + i + '"><span class="em">' + r.em + '</span>'
        + '<span class="bd"><span class="t1">' + esc(r.t1 || "") + '</span>'
        + '<span class="t2">' + esc(r.t2 || "") + '</span></span></button>';
    });
    var inner = ls.querySelector(".v82-inner");
    if (!inner){ inner = document.createElement("div"); inner.className = "v82-inner"; ls.appendChild(inner); }
    inner.innerHTML = html;
    var btns = inner.querySelectorAll(".v82-nt");
    for (var b = 0; b < btns.length; b++){
      (function(r){
        btns[b].onclick = function(){
          if (r.id){ closeList(true); silentBack(); openCardById(r.id); }
          else if (r.ent){ closeList(true); silentBack(); if (typeof entityFeedView === "function") entityFeedView(r.ent); setActive(); }
          else if (r.series){ closeList(true); silentBack(); if (typeof openSeries === "function") openSeries(r.series); setActive(); }
        };
      })(rows[+btns[b].dataset.i]);
    }
  }
  function openList(kind){
    if (!mq.matches) return;
    var ls = $("v82list"); if (!ls || ls.classList.contains("on")) return;
    setHeadTitle("v82list", kind === "shares" ? T().shares : T().follows);
    renderList(kind);
    showScreen("v82list");
    setActive();
  }
  function closeList(fromPop){
    if (!hideScreen("v82list")) return false;
    if (!fromPop) silentBack();
    setActive();
    return true;
  }

  /* ---------- entity picker (논객 / 회사) ---------- */
  function openPicker(kind){
    if (!mq.matches) return;
    var pk = $("v82picker"); if (!pk) return;
    var t = T();
    setHeadTitle("v82picker", kind==="person" ? t.people : t.company);
    var list;
    if (kind === "person"){
      var authors = new Set(ITEMS.map(function(i){ return i.source; }));
      list = Object.keys(ENTITIES).filter(function(k){ return ENTITIES[k].kind==="person" && authors.has(k); }).sort(function(a,b){ return entName(a).localeCompare(entName(b)); });
    } else {
      list = Object.keys(ENTITIES).filter(function(k){ return ENTITIES[k].kind==="company"; }).sort(function(a,b){ return a.localeCompare(b); });
    }
    var html = list.map(function(k, i){ return '<button class="pk-item" data-k="' + esc(k) + '">' + esc(entName(k)) + '</button>'; }).join("");
    var inner = pk.querySelector(".v82-inner");
    if (!inner){ inner = document.createElement("div"); inner.className = "v82-inner"; pk.appendChild(inner); }
    inner.innerHTML = html || ('<div class="v82-empty">—</div>');
    var items = inner.querySelectorAll(".pk-item");
    for (var i = 0; i < items.length; i++){
      items[i].onclick = function(){
        var k = this.dataset.k;
        closePicker(true); silentBack();
        if (typeof filterByEntity === "function") filterByEntity(k);
        setActive();
      };
    }
    showScreen("v82picker");
  }
  function closePicker(fromPop){
    if (!hideScreen("v82picker")) return false;
    if (!fromPop) silentBack();
    return true;
  }

  /* ---------- open a card in detail by id ---------- */
  /* index.html의 openFromCard(헤드라인 탭)가 모바일에서 쓸 유일한 통로 */
  window.v82OpenCard = function(id){ openCardById(id); };
  function openCardById(id){
    function tryOpen(n){
      var el = $("sig-" + id);
      if (el){ openDetail(el); return; }
      if (n < 12) setTimeout(function(){ tryOpen(n+1); }, 110);
    }
    if (!$("sig-" + id) && typeof goToItem === "function") goToItem(id);
    tryOpen(0);
  }

  /* ---------- card detail overlay ---------- */
  var DETAIL_PH = null;
  /* 2026-07-25 (june): "예측 추적중은 원문보기 오른쪽에 아이콘 형태로. 설명까지 다 보일
     필요는 없어." .oc는 card-body의 형제라 CSS만으로는 원문 보기 줄에 못 붙인다.
     상세를 열 때 .cta-row 안으로 옮기고, 아이콘만 남기는 건 CSS가 맡는다.
     이미 옮겨져 있으면 아무것도 안 한다(다시 열어도 안전). 피드에서는 .oc도 .cta-row도
     display:none이라 옮겨진 채로 돌아가도 보이는 변화가 없다. */
  function tuneDetail(card){
    try {
      var cta = card.querySelector(".cta-row"), oc = card.querySelector(".oc");
      if (cta && oc && oc.parentNode !== cta){
        if (!oc.getAttribute("title")) oc.setAttribute("title", oc.textContent.replace(/\s+/g, " ").trim());
        cta.appendChild(oc);
      }
    } catch (e) {}
  }
  function openDetail(card){
    if (!mq.matches || !card) return;
    var dt = $("v82detail"), body = $("v82dbody");
    if (dt.classList.contains("on")) return;
    tuneDetail(card);
    try { var _rid=(card.id||"").replace(/^sig-/,""); if(_rid && typeof setRead==="function") setRead(_rid); } catch(e){}
    try {
      DETAIL_PH = document.createComment("v82ph");
      card.parentNode.insertBefore(DETAIL_PH, card);
      card.classList.remove("v82c","v82cover","v82clip","collapsed");
      body.appendChild(card);
      dt.classList.add("on");
      body.scrollTop = 0;
      document.body.style.overflow = "hidden";
      refreshNav();
      if (typeof pushView === "function") pushView();
      try { v82MountComments(card); } catch (e) {}
    } catch(err){
      try { dt.classList.remove("on"); document.body.style.overflow = ""; refreshNav(); } catch(e2){}
    }
  }
  /* 2026-07-29 fix: on mobile, switching the feed to an entity view while the
     article detail overlay (#v82detail, z 13600) is open left the new entity
     page rendered underneath it, so the second tap on a glossary/entity sheet
     looked dead. Close the detail overlay first. Desktop is unaffected because
     it routes to showEntityRail instead. */
  (function(){
    function armEntityFeedViewGuard(){
      if (window.__v82EfvGuard) return true;
      var orig = window.entityFeedView;
      if (typeof orig !== "function") return false;
      window.__v82EfvGuard = true;
      window.entityFeedView = function(){
        try { closeDetail(false); } catch (e) {}
        return orig.apply(this, arguments);
      };
      return true;
    }
    if (!armEntityFeedViewGuard()){
      var tries = 0;
      var iv = setInterval(function(){
        if (armEntityFeedViewGuard() || ++tries > 40) clearInterval(iv);
      }, 150);
    }
  })();
  /* 2026-07-29 (2): the mobile article detail shows the comment thread inline at
     the bottom of the post, instead of only behind the comment icon. There is
     still exactly ONE comment implementation (assets/twc.js): we relocate its
     sheet node (#twcOv > .twc-sheet) into this card's .comment-box while the
     detail is open and put it back on close, so an inline copy can never drift
     out of sync with the sheet. Feed cards are unchanged (count badge only).
     Desktop never reaches this code — the v82 IIFE returns early there. */
  var V82_CB_HOST = null;
  var V82_CB_CHECK = null;
  var V82_CB_RO = null;
  var V82_CB_VV = false;
  function v82InlineSheet(){
    var host = $("v82dbody");
    return host ? host.querySelector(".twc-sheet.twc-inline") : null;
  }
  function v82MountComments(card, isRetry){
    if (!card || typeof toggleComments !== "function") return false;
    var host = card.querySelector(".comment-box");
    var id = (card.id || "").replace(/^sig-/, "");
    if (!host || !id) return false;
    v82UnmountComments();
    var ov = document.getElementById("twcOv");
    if (!ov) {
      /* twc builds #twcOv lazily on first use, so on the first article opened in
         a session it does not exist yet. Build it by opening the sheet once and
         closing it again — closeComments() silentBacks the entry that open just
         pushed, and __twcSilent keeps that popstate from closing the detail. */
      try { toggleComments(id); } catch (e) { return false; }
      try { if (typeof closeComments === "function") closeComments(); } catch (e) {}
      ov = document.getElementById("twcOv");
      if (!ov) return false;
    }
    /* toggleComments pushes a history entry so the back gesture can close the
       full-screen sheet. Inline there is nothing to close and that entry would
       eat one back tap, so we pre-open the overlay: toggleComments then sees
       wasOpen === true and skips the push entirely (TWC.hist stays false). */
    ov.hidden = false;
    try { toggleComments(id); } catch (e) { ov.hidden = true; return false; }
    ov.hidden = true;
    document.body.style.overflow = "hidden";   /* the detail overlay owns the lock */
    var sheet = ov.querySelector(".twc-sheet");
    if (!sheet) return false;
    sheet.classList.add("twc-inline");
    host.hidden = false;
    host.appendChild(sheet);
    V82_CB_HOST = host;
    v82PinCompBar(sheet);
    /* watchdog: if the section somehow lands empty, mount it once more rather
       than leaving the reader with no way to comment. */
    if (V82_CB_CHECK) { clearTimeout(V82_CB_CHECK); V82_CB_CHECK = null; }
    if (!isRetry) {
      V82_CB_CHECK = setTimeout(function(){
        V82_CB_CHECK = null;
        var dt = $("v82detail");
        var s = v82InlineSheet();
        if (dt && dt.classList.contains("on") && (!s || s.offsetHeight < 20)) v82MountComments(card, true);
      }, 600);
    }
    return true;
  }
  /* X-style: the composer stays pinned to the bottom of the detail while the
     article scrolls. Both .card and .twc-sheet carry a transform (entry
     animations), and a transformed ancestor becomes the containing block for
     position:fixed — so the bar is parked directly on #v82detail and positioned
     against that instead. */
  function v82PinnedBar(){
    var dt = $("v82detail");
    return dt ? dt.querySelector(".twc-comp.twc-pinned") : null;
  }
  function v82SyncCompBar(){
    var body = $("v82dbody");
    if (!body) return;
    var bar = v82PinnedBar();
    if (!bar) { body.style.paddingBottom = ""; return; }
    /* the bar is out of flow, so the article needs room to scroll clear of it */
    body.style.paddingBottom = ((bar.offsetHeight || 56) + 24) + "px";
    /* Pin the bar's bottom edge to the visible viewport bottom by MEASURING where
       the bar actually is, instead of assuming what iOS moved. Depending on the
       WebKit build the keyboard may shrink 100dvh, pan the layout viewport, both,
       or neither - assuming any one of them either double-corrects (2026-07-29:
       gap ABOVE the keyboard) or leaves the bar floating with the feed showing
       through BELOW it (2026-07-30 june screenshot). The measured delta is 0 when
       there is no keyboard, so desktop shells and tests are untouched. */
    var vv = window.visualViewport;
    if (vv) {
      bar.style.transform = "";
      var rb = bar.getBoundingClientRect();
      var delta = Math.round(rb.bottom - (vv.offsetTop + vv.height));
      if (delta > 1 || delta < -1) bar.style.transform = "translateY(" + (-delta) + "px)";
    }
  }
  function v82PinCompBar(sheet){
    var dt = $("v82detail");
    var bar = sheet && sheet.querySelector(".twc-comp");
    if (!dt || !bar) return;
    bar.classList.add("twc-pinned");
    dt.appendChild(bar);
    if (window.ResizeObserver) {
      try {
        if (!V82_CB_RO) V82_CB_RO = new ResizeObserver(v82SyncCompBar);
        V82_CB_RO.disconnect();
        V82_CB_RO.observe(bar);
      } catch (e) {}
    }
    if (window.visualViewport && !V82_CB_VV) {
      V82_CB_VV = true;
      window.visualViewport.addEventListener("resize", v82SyncCompBar);
      window.visualViewport.addEventListener("scroll", v82SyncCompBar);
    }
    v82CompWho();
    var ta = document.getElementById("twcText");
    if (ta && ta.getAttribute("data-v82focus") !== "1") {
      ta.setAttribute("data-v82focus", "1");
      ta.addEventListener("focus", function(){ v82OpenCompBar(true); });
      ta.addEventListener("blur", function(){ v82OpenCompBar(false); });
    }
    v82SyncCompBar();
  }
  /* X shows who you are posting as above the box. We have no mentions, so there is
     no "replying to @someone" line — just the nickname. */
  function v82CompWho(){
    var bar = v82PinnedBar();
    if (!bar) return;
    var row = bar.querySelector(".twc-who");
    var nick = "";
    try { nick = localStorage.getItem("stk_nick") || ""; } catch (e) {}
    if (!nick) { if (row && row.parentNode) row.parentNode.removeChild(row); return; }
    if (!row) {
      row = document.createElement("div");
      row.className = "twc-who";
      bar.insertBefore(row, bar.firstChild);
    }
    row.textContent = nick;
  }
  function v82OpenCompBar(on){
    var bar = v82PinnedBar();
    if (!bar) return;
    if (on) v82CompWho();
    if (on) bar.classList.add("twc-open"); else bar.classList.remove("twc-open");
    v82SyncCompBar();
    /* iOS reports the keyboard-shrunk visual viewport a beat late, so re-measure */
    setTimeout(v82SyncCompBar, 120);
    setTimeout(v82SyncCompBar, 380);
  }
  function v82UnpinCompBar(sheet){
    if (V82_CB_RO) { try { V82_CB_RO.disconnect(); } catch (e) {} }
    var bar = v82PinnedBar() || document.querySelector(".twc-comp.twc-pinned");
    var home = sheet || document.querySelector("#twcOv .twc-sheet");
    if (bar) {
      var who = bar.querySelector(".twc-who");
      if (who && who.parentNode) who.parentNode.removeChild(who);
      bar.classList.remove("twc-pinned");
      bar.classList.remove("twc-open");
      bar.style.transform = "";
      if (home) home.appendChild(bar);
    }
    var body = $("v82dbody");
    if (body) body.style.paddingBottom = "";
  }
  function v82UnmountComments(){
    if (V82_CB_CHECK) { clearTimeout(V82_CB_CHECK); V82_CB_CHECK = null; }
    var sheet = document.querySelector(".twc-sheet.twc-inline");
    if (!sheet) { V82_CB_HOST = null; return false; }
    v82UnpinCompBar(sheet);
    sheet.classList.remove("twc-inline");
    var ov = document.getElementById("twcOv");
    if (ov) ov.appendChild(sheet);
    if (V82_CB_HOST) V82_CB_HOST.hidden = true;
    V82_CB_HOST = null;
    /* fromPop = true: clear twc state without touching history */
    try { if (typeof closeComments === "function") closeComments(true); } catch (e) {}
    return true;
  }
  function v82ScrollToInlineComments(card){
    if (!card || !card.closest || !card.closest("#v82dbody")) return false;
    var sheet = v82InlineSheet();
    if (!sheet) return false;
    try { sheet.scrollIntoView({ behavior: "smooth", block: "center" }); }
    catch (e) { sheet.scrollIntoView(); }
    var box = document.getElementById("twcText");
    if (box) setTimeout(function(){ try { box.focus({ preventScroll: true }); } catch (e) {} }, 320);
    return true;
  }
  function closeDetail(fromPop){
    var dt = $("v82detail");
    if (!dt || !dt.classList.contains("on")) return false;
    try { v82UnmountComments(); } catch (e) {}
    dt.classList.remove("on");
    document.body.style.overflow = "";
    var body = $("v82dbody");
    var card = body.querySelector(".card");
    if (card){
      if (DETAIL_PH && DETAIL_PH.parentNode){
        DETAIL_PH.parentNode.insertBefore(card, DETAIL_PH);
        DETAIL_PH.remove();
        var id = (card.id || "").replace(/^sig-/, "");
        card.classList.add("v82c");
        try { if (typeof READ !== "undefined" && READ.has(id)) card.classList.add("collapsed"); } catch(e){}
        applyCompact();
      } else { card.remove(); }
    }
    DETAIL_PH = null;
    refreshNav();
    if (fromPop === false) silentBack();
    return true;
  }
  /* related-post ("함께 읽기") taps inside the detail overlay: the inline
     onclick=goToItem only scrolls the hidden feed underneath, so on mobile
     intercept and swap the open detail for the tapped item's detail. */
  document.addEventListener("click", function(e){
    if (!mq.matches) return;
    var rl = e.target.closest && e.target.closest(".related-link");
    if (!rl) return;
    var dt = document.getElementById("v82detail");
    if (!dt || !dt.classList.contains("on") || !dt.contains(rl)) return;
    var oc = rl.getAttribute("onclick") || "";
    var mm = oc.match(/goToItem\(['"]([^'"]+)['"]\)/);
    if (!mm) return;
    e.preventDefault(); e.stopPropagation();
    var tid = mm[1];
    closeDetail(false);
    setTimeout(function(){ try { openCardById(tid); } catch(err){} }, 90);
  }, true);
  function cardTap(e){
    var card = this;
    if (!mq.matches || !card.classList.contains("v82c")) return;
    if (e.target.closest(".eg-comment,.ask-comment")){
      var cid = (card.id || "").replace(/^sig-/, "");
      /* 라운드15: 댓글 아이콘은 상세를 열지 않고 댓글 시트(새창)만 연다 (트위터 모바일식) */
      if (v82ScrollToInlineComments(card)) return;
      e.preventDefault(); e.stopPropagation();
      if (typeof toggleComments === "function") toggleComments(cid);
      return;
    }
    if (e.target.closest("a,button,input,textarea,select,summary,.has-tip,.engage,.comment-box,.vote-row")) return;
    e.preventDefault();
    openDetail(card);
  }

  /* ---------- compact cards + cover budget + read-more ---------- */
  function itemOf(card){
    var id = (card.id || "").replace(/^sig-/, "");
    if (typeof ITEMS === "undefined") return null;
    for (var i = 0; i < ITEMS.length; i++) if (ITEMS[i].id === id) return ITEMS[i];
    return null;
  }
  function applyCompact(){
    if (!mq.matches) return;
    var list = $("feedList"); if (!list) return;
    var covers = 0;
    var cards = list.querySelectorAll(".card");
    for (var i = 0; i < cards.length; i++){
      var c = cards[i];
      c.classList.add("v82c");
      if (!c.__v82tap){ c.__v82tap = true; c.addEventListener("click", cardTap); }
      var it = itemOf(c);
      var allow = it && it.cover && (it.series || (it.hot && covers < 3));
      c.classList.toggle("v82cover", !!allow);
      if (allow) covers++;
      /* move the cover image to the bottom of the card (after the text,
         before the action bar) — Twitter-style media placement */
      if (!c.__v82cov){
        c.__v82cov = true;
        var cov = c.querySelector(".card-thumb-img");
        var eng = c.querySelector(".engage");
        if (cov && eng && eng.parentNode){ eng.parentNode.insertBefore(cov, eng); }
      }
      /* read-more affordance under the gist */
      if (!c.__v82more){
        c.__v82more = true;
        var g = c.querySelector(".gist-fold") || c.querySelector(".card-body");
        if (g){
          var mb = document.createElement("button");
          mb.className = "v82-more"; mb.type = "button";
          mb.textContent = T().more + " →";
          mb.addEventListener("click", function(e){ e.stopPropagation(); var cc=this.closest(".card"); if(cc){ cc.classList.add("v82expanded"); cc.classList.remove("v82clip"); } });
          g.appendChild(mb);
        }
      }
      /* mark clipped only when the gist actually overflows (an inline-expanded
         card stays open, Twitter-style, and is never re-clipped) */
      var gi = c.querySelector(".gist");
      if (gi && !c.classList.contains("v82expanded")) c.classList.toggle("v82clip", gi.scrollHeight - gi.clientHeight > 6);
    }
  }
  function plainFeed(){
    try {
      return !THEME_VIEW && !SB_VIEW && !SERIES_VIEW && !ENTITY_VIEW && !QUERY &&
             !BM_ONLY && !UNREAD_ONLY && !FREE_ONLY && TAB !== "mine";
    } catch(e){ return false; }
  }
  function insertModules(){
    if (!mq.matches) return;
    var list = $("feedList"); if (!list) return;
    var olds = list.querySelectorAll(".v82mod");
    for (var i = 0; i < olds.length; i++){ if (olds[i].__todayObs){ try { olds[i].__todayObs.disconnect(); } catch (_){} olds[i].__todayObs = null; } olds[i].remove(); }
    if (!plainFeed()) return;
    var cards = list.querySelectorAll(".card");
    if (cards.length < 3) return;
    var S = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG] : {};
    var mods = [];
    try {
      if (typeof TODAY_ID !== "undefined" && TODAY_ID){
        var titem = null;
        for (var j = 0; j < ITEMS.length; j++) if (ITEMS[j].id === TODAY_ID){ titem = ITEMS[j]; break; }
        if (titem && titem.ask && window.__v82todayHid !== TODAY_ID && !(typeof todayDismissed === "function" && todayDismissed())){
          /* bordered card + "왜 화두인가" context so readers know what's up for debate */
          var ctx = "";
          try {
            var raw = (titem.why && titem.why[LANG]) ? titem.why[LANG] : (titem.gist && titem.gist[LANG] ? v82Plain(titem.gist[LANG]) : "");
            ctx = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
            if (ctx.length > 180) ctx = ctx.slice(0, 176).replace(/\s+\S*$/, "") + "…";
          } catch(e){ ctx = ""; }
          var tc = document.createElement("div"); tc.className = "v82mod v82today";
          tc.innerHTML =
            '<button class="v82today-x" aria-label="close">×</button>' +
            '<div class="v82today-tag">💬 ' + (S.todayLabel || T().ntDebate) + '</div>' +
            '<div class="v82today-q">' + esc(titem.ask[LANG] || titem.title[LANG] || "") + '</div>' +
            (ctx ? '<div class="v82today-ctx">' + esc(ctx) + '</div>' : "") +
            '<div class="v82today-src">' + esc(dispName(titem.source)) + ' · ' + esc(titem.title[LANG] || "") + '</div>' +
            '<div class="v82today-cta">' + (S.todayJoin || T().ntDebate) + ' →</div>';
          tc.querySelector(".v82today-x").addEventListener("click", function(ev){ ev.stopPropagation(); window.__v82todayHid = TODAY_ID; if (typeof markTodayDismissed === "function") markTodayDismissed(); if (typeof collapseHide === "function") collapseHide(tc, function(){ tc.remove(); }); else tc.remove(); });
          tc.addEventListener("click", function(){ if (typeof markTodayDismissed === "function") markTodayDismissed(); openCardById(TODAY_ID); setTimeout(function(){ if (typeof toggleComments === "function") toggleComments(TODAY_ID); }, 320); });
          if (typeof watchTodayPast === "function") watchTodayPast(tc); /* 스크롤로 지나치면 그날 하루 숨김 */
          mods.push({ top: true, node: tc });
        }
      }
    } catch(e){}
    mods.forEach(function(mm){
      if (mm.top){ var first = list.querySelector(".card"); if (first) first.before(mm.node); else list.appendChild(mm.node); }
      else { var c = list.querySelectorAll(".card")[mm.after]; if (c) c.after(mm.node); }
    });
  }
  function mod(title, inner, onMore){
    var d = document.createElement("div"); d.className = "v82mod";
    var h = document.createElement("div"); h.className = "v82mod-h";
    var b = document.createElement("b"); b.textContent = title; h.appendChild(b);
    if (onMore){ var m = document.createElement("button"); m.textContent = T().more + " →"; m.addEventListener("click", onMore); h.appendChild(m); }
    d.appendChild(h); d.appendChild(inner); return d;
  }

  /* ---------- community-slide top tabs ---------- */
  function buildTopTabs(){
    if (!mq.matches) return;
    var strip = $("v82tabs"); if (!strip) return;
    /* rbeta: Twitter-style 최신 / 팔로잉 switcher instead of category pills */
    if (typeof RBETA !== "undefined" && RBETA){
      var _cur = (typeof TAB !== "undefined") ? TAB : "all";
      var _L = ({ ko:["최신","팔로잉"], en:["Latest","Following"], ja:["最新","フォロー中"] })[typeof LANG!=="undefined"?LANG:"ko"] || ["최신","팔로잉"];
      strip.innerHTML =
        '<button class="v82fsw-t' + (_cur!=="mine"?" on":"") + '" data-t="all">' + _L[0] + '</button>' +
        '<button class="v82fsw-t' + (_cur==="mine"?" on":"") + '" data-t="mine">' + _L[1] + '</button>';
      var _bs = strip.querySelectorAll("[data-t]");
      for (var _i=0;_i<_bs.length;_i++){ _bs[_i].onclick = function(){ var id=this.dataset.t; goHomeThen(function(){ if (typeof setTab==="function") setTab(id); }); }; }
      return;
    }
    if (typeof CATEGORIES === "undefined") return;
    var t = T(), cur = (typeof TAB !== "undefined") ? TAB : "all";
    var html = "";
    var showMine = false;
    try { showMine = (typeof mineCount==="function" && mineCount()>0) || cur==="mine"; } catch(e){}
    if (showMine) html += '<button class="v82-tp mine' + (cur==="mine"?" on":"") + '" data-t="mine">★ ' + ((STRINGS[LANG]&&STRINGS[LANG].myFeed)||"For you") + '</button>';
    CATEGORIES.forEach(function(c){ html += '<button class="v82-tp' + (cur===c.id?" on":"") + '" data-t="' + c.id + '">' + esc(c[LANG]) + '</button>'; });
    var entActive = false; try { entActive = !!ENTITY_VIEW; } catch(e){}
    html += '<button class="v82-tp pick' + (entActive?" act":"") + '" data-pick="person">👤 ' + t.people + ' ▾</button>';
    html += '<button class="v82-tp pick' + (entActive?" act":"") + '" data-pick="company">🏢 ' + t.company + ' ▾</button>';
    strip.innerHTML = html;
    var tps = strip.querySelectorAll("[data-t]");
    for (var i = 0; i < tps.length; i++){ tps[i].onclick = function(){ var id=this.dataset.t; goHomeThen(function(){ if (typeof setTab==="function") setTab(id); }); }; }
    var pks = strip.querySelectorAll("[data-pick]");
    for (var p = 0; p < pks.length; p++){ pks[p].onclick = function(){ openPicker(this.dataset.pick); }; }
  }
  function goHomeThen(fn){
    /* leave any shell screen / app view, then run */
    clearSubState();
    if (anyScreenOpen()){ closeFind(true); closeHub(true); closeNotif(true); closePicker(true); closeList(true); silentBack(); }
    try { if (typeof THEME_VIEW!=="undefined" && THEME_VIEW && typeof closeThemes==="function") closeThemes(); } catch(e){}
    fn(); setActive();
  }

  /* ---------- bottom nav ---------- */
  function closeAppSheets(){
    try { var cal=$("calSheet"); if(cal && !cal.hidden && typeof closeCal==="function"){ closeCal(); silentBack(); } } catch(e){}
    try { var me=$("meSheet"); if(me && !me.hidden && typeof closeMe==="function"){ closeMe(); silentBack(); } } catch(e){}
  }
  function navGo(v){
    clearSubState();          /* 어느 탭을 누르든 탐색 서브뷰 잔재부터 정리 */
    if (v === "home"){
      if (closeDetail(true)) silentBack();
      closeFind(false); closeHub(false); closeNotif(false); closePicker(false); closeList(true);
      closeAppSheets();
      try { if (typeof THEME_VIEW!=="undefined" && THEME_VIEW && typeof closeThemes==="function") closeThemes(); } catch(e){}
      if (typeof goHome === "function") goHome();
      setActive();
    } else if (v === "find"){
      closeHub(true); closeNotif(true); closePicker(true); closeList(true); closeDetail(true); closeAppSheets();
      openFind();
    } else if (v === "explore"){
      closeFind(true); closeNotif(true); closePicker(true); closeList(true); closeDetail(true); closeAppSheets();
      openHub();
    } else if (v === "cal"){
      closeFind(true); closeHub(true); closeNotif(true); closePicker(true); closeList(true); closeDetail(true);
      if (typeof openCal === "function") openCal();
      setActive();
    } else if (v === "notif"){
      closeFind(true); closeHub(true); closePicker(true); closeList(true); closeDetail(true); closeAppSheets();
      openNotif();
    }
  }
  function setActive(){
    var nav = $("v82nav"); if (!nav) return;
    var cur = "home";
    if ($("v82explore") && $("v82explore").classList.contains("on")) cur = "find";
    else if ($("v82hub") && $("v82hub").classList.contains("on")) cur = "explore";
    else if ($("v82notif") && $("v82notif").classList.contains("on")) cur = "notif";
    else { try { if (THEME_VIEW || SB_VIEW) cur = "explore"; } catch(e){} }
    try { var cal=$("calSheet"); if (cal && !cal.hidden) cur = "cal"; } catch(e){}
    var bs = nav.querySelectorAll("button");
    for (var i = 0; i < bs.length; i++) bs[i].classList.toggle("on", bs[i].dataset.v === cur);
    refreshNav();
  }

  /* ---------- back handling ---------- */
  window.v82Pop = function(){
    if (SILENT){ SILENT = false; return true; }
    if (!mq.matches) return false;
    var cfs = $("chartFS"); if (cfs && !cfs.hidden) return false;
    var cal = $("calSheet"); if (cal && !cal.hidden) return false;
    var me = $("meSheet"); if (me && !me.hidden) return false;
    /* 탐색 서브뷰가 최우선: 지금쏠린곳(허브 내부) / 테마논쟁·적중기록(피드) → 뒤로가기는 허브로 */
    if (HUB_SUB && $("v82hub") && $("v82hub").classList.contains("on")){ closeHubSub(true); return true; }
    if (EXPLORE_SUB){ closeExploreSub(true); return true; }
    if (closeDrawer(true)) return true;
    if (closeList(true)) return true;
    if (closePicker(true)) { setActive(); return true; }
    if (closeDetail(true)) return true;
    if (closeNotif(true)) return true;
    if (closeHub(true)) return true;
    if (closeFind(true)) return true;
    return false;
  };

  /* ---------- 손가락 추적 좌우 스와이프: 최신 ↔ 팔로잉 (2026-07-28, june) ----------
     이전엔 스와이프를 감지만 하고 탭을 click()해서 툭 넘어갔다. 이제 X처럼
     #feed을 손가락 따라 밀고(가로 확정 시), 임계(폭 30%)를 넘기면 나가는 방향으로
     마저 밀어낸 뒤 setTab으로 전환 → 반대편에서 새 피드가 들어온다. 못 넘기면
     제자리로 스냅백. 세로 스크롤은 방해하지 않고(가로로 확정된 뒤에만 preventDefault),
     가로 스크롤 영역(핫레일·탭바·차트·표)·오버레이·좌우 가장자리는 건드리지 않는다. */
  (function swipeTabs(){
    var x0=0,y0=0,tracking=false,axis=null,moved=false,W=360,startTab=0,targetT=null,goNext=false,edge=false,animating=false;
    var NOSWIPE=".v82-tabs,#v82tabs,#hotRail,[data-v82hot],.scrollx,.chart,svg,table,input,textarea,select,.twc-ov,.img-fs";
    function blocked(){
      if (anyScreenOpen()) return true;
      var d=$("v82detail"); if (d&&d.classList.contains("on")) return true;
      var ov=document.getElementById("twcOv"); if (ov&&!ov.hidden) return true;
      var fs=document.getElementById("imgFS"); if (fs&&!fs.hidden) return true;
      var cf=$("chartFS"); if (cf&&!cf.hidden) return true;
      var cal=$("calSheet"); if (cal&&!cal.hidden) return true;
      var me=$("meSheet"); if (me&&!me.hidden) return true;
      var dw=$("v82drawer"); if (dw&&dw.classList.contains("on")) return true;
      return false;
    }
    function feedEl(){ return $("feed"); }
    function wrapEl(){ return document.querySelector(".wrap"); }
    function tabBtns(){ var s=$("v82tabs"); return s ? s.querySelectorAll(".v82fsw-t") : []; }
    function cleanup(f){ if(!f) return; f.style.transition=""; f.style.transform=""; f.style.opacity=""; var w=wrapEl(); if(w) w.style.overflowX=""; }

    document.addEventListener("touchstart", function(e){
      tracking=false; axis=null; moved=false;
      if (animating) return;
      if (!mq.matches || e.touches.length!==1) return;
      if (typeof RBETA==="undefined" || !RBETA) return;
      if (blocked()) return;
      var bs=tabBtns(); if (bs.length<2) return;                 /* 최신/팔로잉 스위처가 있을 때만(홈) */
      var t=e.touches[0];
      if (t.clientX<26 || t.clientX>innerWidth-26) return;       /* 가장자리는 브라우저 몫 */
      if (e.target.closest && e.target.closest(NOSWIPE)) return;
      x0=t.clientX; y0=t.clientY; tracking=true; W=innerWidth||360;
      startTab=0; for (var i=0;i<bs.length;i++) if (bs[i].classList.contains("on")) startTab=i;
    }, { passive:true });

    document.addEventListener("touchmove", function(e){
      if (!tracking || animating || e.touches.length!==1) return;
      var t=e.touches[0], dx=t.clientX-x0, dy=t.clientY-y0;
      if (axis===null){
        if (Math.abs(dx)>10 || Math.abs(dy)>10) axis = Math.abs(dx)>Math.abs(dy)*1.4 ? "x" : "y";
        else return;
      }
      if (axis!=="x") return;                                    /* 세로로 확정되면 스크롤에 맡긴다 */
      if (e.cancelable) e.preventDefault();                      /* 가로 확정 후에만 스크롤/제스처 억제 */
      moved=true;
      var bs=tabBtns();
      goNext = dx<0;
      var target = goNext ? startTab+1 : startTab-1;
      edge = (target<0 || target>=bs.length);
      targetT = (!edge && bs[target]) ? bs[target].dataset.t : null;
      var f=feedEl(); if(!f) return;
      var w=wrapEl(); if (w) w.style.overflowX="clip";           /* 미끄러지는 피드를 뷰포트에서 자름 */
      var mv = edge ? dx*0.28 : dx;                              /* 가장자리 고무줄 */
      f.style.transition="none";
      f.style.transform="translateX("+mv+"px)";
      f.style.opacity = edge ? "1" : String(1 - Math.min(Math.abs(dx)/W,1)*0.22);
    }, { passive:false });

    document.addEventListener("touchend", function(e){
      if (!tracking || animating){ tracking=false; return; }
      tracking=false;
      var f=feedEl();
      if (axis!=="x" || !moved){ if(f) cleanup(f); return; }
      var dx = (e.changedTouches&&e.changedTouches.length) ? e.changedTouches[0].clientX-x0 : 0;
      var pass = Math.abs(dx) > W*0.30;
      if (edge || !pass || !targetT){                            /* 스냅백 */
        if (f){ f.style.transition="transform .22s cubic-bezier(.22,.61,.36,1), opacity .22s ease"; f.style.transform=""; f.style.opacity=""; }
        setTimeout(function(){ cleanup(f); }, 250);
        return;
      }
      /* 커밋: 나가는 방향으로 마저 밀어내고 → 전환 → 반대편에서 들어오게 */
      animating=true;
      var out = goNext ? -W : W, inFrom = goNext ? W : -W, tt=targetT;
      f.style.transition="transform .2s cubic-bezier(.4,0,.2,1), opacity .2s ease";
      f.style.transform="translateX("+out+"px)";
      f.style.opacity="0";
      var done=false;
      var finish=function(){
        if (done) return; done=true;
        try { f.removeEventListener("transitionend", finish); } catch(_){}
        try { goHomeThen(function(){ if (typeof setTab==="function") setTab(tt); }); } catch(err){}
        var f2=feedEl() || f;
        f2.style.transition="none";
        f2.style.transform="translateX("+inFrom+"px)";
        f2.style.opacity="0";
        void f2.offsetWidth;                                     /* 리플로우 */
        requestAnimationFrame(function(){
          f2.style.transition="transform .24s cubic-bezier(.22,.61,.36,1), opacity .24s ease";
          f2.style.transform=""; f2.style.opacity="1";
          setTimeout(function(){ cleanup(f2); animating=false; }, 300);
        });
      };
      f.addEventListener("transitionend", finish);
      setTimeout(finish, 260);                                   /* transitionend 폴백 */
    }, { passive:true });

    document.addEventListener("touchcancel", function(){
      if (!tracking) return; tracking=false;
      if (!animating){ var f=feedEl(); if (f){ f.style.transition="transform .22s ease"; f.style.transform=""; f.style.opacity=""; setTimeout(function(){cleanup(f);},250); } }
    }, { passive:true });
  })();

  /* ---------- auto-hide header ---------- */
  var lastY = 0;
  window.addEventListener("scroll", function(){
    if (!mq.matches) return;
    var nav = document.querySelector("nav"); if (!nav) return;
    var y = window.scrollY || 0;
    if (y > lastY && y > 90) nav.classList.add("v82hide");
    else nav.classList.remove("v82hide");
    lastY = y;
  }, { passive: true });

  /* ---------- feed render hook (observer disconnected while writing) ---------- */
  var pending = false, OBS = null;
  function onFeedMutate(){
    if (pending) return;
    pending = true;
    requestAnimationFrame(function(){
      pending = false;
      if (OBS) OBS.disconnect();
      try { applyCompact(); insertModules(); buildTopTabs(); relabel(); setActive(); }
      finally { var list = $("feedList"); if (OBS && list) OBS.observe(list, { childList: true }); }
    });
  }
  function watchFeed(){
    var list = $("feedList"); if (!list) return;
    OBS = new MutationObserver(onFeedMutate);
    OBS.observe(list, { childList: true });
    onFeedMutate();
  }
  /* 요약 전문 청크는 카드가 그려진 뒤에 도착한다. innerHTML 교체는 feedList의
     childList 감시에 안 걸려서, 짧은 미리보기 기준으로 내려진 클립 판정이
     영영 안 뒤집혔다(→ 더 보기 실종). 데스크톱 v83ClipScan처럼 1초마다 다시 잰다. */
  setInterval(function(){
    if (!mq.matches) return;
    var cards = document.querySelectorAll("#feedList .card.v82c");
    for (var i = 0; i < cards.length; i++){
      var c = cards[i], g = c.querySelector(".gist");
      if (g && !c.classList.contains("v82expanded"))
        c.classList.toggle("v82clip", g.scrollHeight - g.clientHeight > 6);
    }
  }, 1000);
  /* watch intro/onboard so the nav hides during the splash */
  function watchSplash(){
    var io = $("intro"), ob = $("onboard");
    var mo = new MutationObserver(refreshNav);
    if (io) mo.observe(io, { attributes:true, attributeFilter:["hidden","class"] });
    if (ob) mo.observe(ob, { attributes:true, attributeFilter:["hidden","class"] });
    refreshNav();
  }

  /* ---------- debug badge (?v82debug) ---------- */
  if (location.search.indexOf("v82debug") >= 0){
    var dbg = document.createElement("div");
    dbg.style.cssText = "position:fixed;top:70px;left:8px;right:8px;z-index:99999;background:rgba(0,0,0,.82);color:#0f0;font:10px/1.5 monospace;padding:6px 8px;border-radius:8px;pointer-events:none;white-space:pre-wrap;";
    dbg.textContent = "v82debug ready";
    document.body.appendChild(dbg);
    var dn = 0;
    var dsc = function(el){ if(!el||!el.tagName) return "?"; return el.tagName + (el.id?"#"+el.id:"") + (el.className&&el.className.baseVal===undefined?"."+String(el.className).split(" ").slice(0,2).join("."):""); };
    document.addEventListener("touchstart", function(e){ dn++; dbg.textContent = "[" + dn + "] touch: " + dsc(e.target); }, { passive: true, capture: true });
    document.addEventListener("click", function(e){ dbg.textContent += "\nclick: " + dsc(e.target); }, true);
    window.addEventListener("error", function(e){ dbg.textContent += "\nERR: " + e.message; });
  }

  /* ---------- viewport switches ---------- */
  var mqChange = function(fn){ if (mq.addEventListener) mq.addEventListener("change", fn); else if (mq.addListener) mq.addListener(fn); };
  mqChange(function(){
    if (!mq.matches){
      closeDrawer(true); closeDetail(true);
      closeFind(true); closeHub(true); closeNotif(true); closePicker(true); closeList(true);
      var nav = document.querySelector("nav"); if (nav) nav.classList.remove("v82hide");
      document.body.style.overflow = "";
      var list = $("feedList");
      if (list) list.querySelectorAll(".v82mod").forEach(function(m){ m.remove(); });
    } else { onFeedMutate(); }
  });

  buildShell();
  /* 허브 헤더 ←: 지금쏠린곳 서브면 메뉴로, 아니면 홈으로 */
  var _hubBk = document.querySelector("#v82hub-h .bk");
  if (_hubBk) _hubBk.onclick = function(){ if (HUB_SUB) closeHubSub(false); else navGo("home"); };
  watchFeed();
  watchSplash();
})();
