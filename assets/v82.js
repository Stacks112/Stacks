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
        me:"내 정보",record:"판정 기록",alerts:"알림 설정",appearance:"화면 테마",events:"다가오는 이벤트",
        dwProfile:"프로필",dwFollowing:"팔로잉",dwShared:"공유한 글",
        skewTitle:"지금 쏠린 곳",skewSub:"테마·종목별로 강세/약세 의견이 어디로 쏠려 있는지 한눈에 봅니다.",
        skewMethod:"계산 기준: 최근 7일 방향성 글 · 출처별 1표 · 글 5개 또는 출처 3곳 미만은 표본 적음 · 50:50은 엇갈림",
        trWk:"지난주 → 이번 주",trLast:"지난주",trNow:"이번 주",
        trMove:"지난주와 이번 주, 쏠림이 이렇게 옮겨갔습니다.",
        trSame:"지난주에 이어 이번 주도 같은 곳에 쏠려 있습니다.",
        trOnly:"이번 주 논의가 가장 뜨거운 곳입니다.",
        trRank:"쏠림 순위 · 최근 7일",trAll:"최근 7일 · 테마와 종목",trN:"{n}건",trNew:"NEW",trKeep:"=",
        themesSec:"테마 논쟁",recordSec:"판정 기록",people:"논객",company:"회사",
        ntNew:"새 글",ntGrade:"채점",ntSkew:"쏠림 알림",noAlerts:"새로운 알림이 없습니다.",
        bull:"강세",bear:"약세",mix:"엇갈림",sourceUnit:"출처",postUnit:"글",smallSample:"표본 적음",sampleDetail:"글 {posts}개 · 출처 {sources}곳",sourceTitle:"출처별 의견",sourceEmpty:"출처 정보가 없어요.",sourceOriginal:"최근 원문 ↗",openThemes:"테마 논쟁 보기",openRecord:"저자 판정 기록 보기",
        bm:"북마크",follows:"팔로우 내역",shares:"공유 내역",nlLabel:"이번 주 베스트 메일",
        community:"커뮤니티",communitySec:"커뮤니티",communitySoon:"준비 중",
        communityDesc:"특정 논객이나 회사를 함께 쫓는 커뮤니티를 만들거나 팔로우하고, 인용해서 덧글을 남기고, 직접 글도 쓰며 서로 소통하는 공간이에요. 곧 찾아옵니다.",
        emptyFollows:"아직 팔로우한 논객·회사·시리즈가 없어요.",emptyShares:"아직 공유한 글이 없어요.",
        followsPeople:"논객",followsCompany:"회사",followsSeries:"시리즈",
        nsTitle:"알림 설정",nsNew:"새 글 알림",nsFollow:"팔로우 새 글 알림",
        nsEvents:"다가오는 이벤트 알림",nsNoEvents:"예정된 이벤트가 없어요.",nsRecent:"최근 알림",nsEvSubEmpty:"알림 신청한 이벤트가 없어요. 이벤트의 종 버튼을 눌러 신청하세요.",
        recentQ:"최근 검색",recentClear:"전체 지우기",recentDel:"지우기",
        calToday:"오늘",calMonthView:"월별보기",calWeekView:"주별보기",calMonthSoon:"월별 보기는 곧 추가됩니다",calEarnings:"실적",calActual:"실제",calAiSummary:"이번주 AI 요약"},
    en:{home:"Home",find:"Find",explore:"Explore",cal:"Calendar",notif:"Alerts",post:"Post",more:"More",
        me:"My page",record:"Track record",alerts:"Notifications",appearance:"Appearance",events:"Upcoming events",
        dwProfile:"Profile",dwFollowing:"Following",dwShared:"Shared posts",
        skewTitle:"Where the crowd is leaning",skewSub:"See at a glance which way bull/bear opinion tilts, by theme and ticker.",
        skewMethod:"Method: directional calls from the last 7 days · one vote per source · fewer than 5 calls or 3 sources is a small sample · 50:50 stays split",
        trWk:"Last week → this week",trLast:"Last week",trNow:"This week",
        trMove:"Here is how the lean moved between last week and this week.",
        trSame:"Same place as last week — the lean has not moved.",
        trOnly:"Where the argument is hottest this week.",
        trRank:"Skew ranking · last 7 days",trAll:"Last 7 days · themes and tickers",trN:"{n} posts",trN1:"1 post",trNew:"NEW",trKeep:"=",
        themesSec:"Theme debates",recordSec:"Track record",people:"Authors",company:"Companies",
        ntNew:"New",ntGrade:"Graded",ntSkew:"Skew alert",noAlerts:"No new alerts.",
        bull:"Bull",bear:"Bear",mix:"Split",sourceUnit:"sources",postUnit:"posts",smallSample:"small sample",sampleDetail:"{posts} posts · {sources} sources",sourceTitle:"By source",sourceEmpty:"No source detail is available.",sourceOriginal:"Latest original ↗",openThemes:"Open theme debates",openRecord:"Open author track record",
        bm:"Bookmarks",follows:"Following",shares:"Share history",nlLabel:"Weekly best by email",
        community:"Community",communitySec:"Community",communitySoon:"Coming soon",
        communityDesc:"A space to create or follow communities around a given author or company, quote-and-comment, post your own takes, and talk with others. Coming soon.",
        emptyFollows:"You aren't following any authors, companies, or series yet.",emptyShares:"You haven't shared anything yet.",
        followsPeople:"Author",followsCompany:"Company",followsSeries:"Series",
        nsTitle:"Notification settings",nsNew:"New posts",nsFollow:"New posts from who you follow",
        nsEvents:"Upcoming events",nsNoEvents:"No upcoming events.",nsRecent:"Recent alerts",nsEvSubEmpty:"No events subscribed yet. Tap the bell on an event to get alerts.",
        recentQ:"Recent searches",recentClear:"Clear all",recentDel:"Remove",
        calToday:"Today",calMonthView:"Monthly",calWeekView:"Weekly",calMonthSoon:"Monthly view is coming soon.",calEarnings:"Earnings",calActual:"Actual",calAiSummary:"This week's AI summary"},
    ja:{home:"ホーム",find:"探す",explore:"発見",cal:"カレンダー",notif:"通知",post:"投稿",more:"もっと見る",
        me:"マイページ",record:"的中記録",alerts:"通知設定",appearance:"テーマ",events:"今後のイベント",
        dwProfile:"プロフィール",dwFollowing:"フォロー中",dwShared:"共有した記事",
        skewTitle:"今の傾き",skewSub:"テーマ・銘柄ごとに強気/弱気の意見がどちらに傾いているか一目で。",
        skewMethod:"集計基準: 直近7日の方向性記事 · 出典ごとに1票 · 記事5件または出典3件未満は少数サンプル · 50:50は交錯",
        trWk:"先週 → 今週",trLast:"先週",trNow:"今週",
        trMove:"先週と今週で、傾きはこう動きました。",
        trSame:"先週に続き今週も同じところに傾いています。",
        trOnly:"今週、議論が最も熱い場所。",
        trRank:"傾きランキング · 直近7日",trAll:"直近7日 · テーマと銘柄",trN:"{n}件",trNew:"NEW",trKeep:"=",
        themesSec:"テーマ論争",recordSec:"的中記録",people:"論客",company:"企業",
        ntNew:"新着",ntGrade:"採点",ntSkew:"傾きアラート",noAlerts:"新しい通知はありません。",
        bull:"強気",bear:"弱気",mix:"交錯",sourceUnit:"著者",postUnit:"記事",smallSample:"少数サンプル",sampleDetail:"記事{posts}件 · 出典{sources}",sourceTitle:"出典別の意見",sourceEmpty:"出典情報はありません。",sourceOriginal:"最新原文 ↗",openThemes:"テーマ論争を見る",openRecord:"著者の的中記録を見る",
        bm:"ブックマーク",follows:"フォロー履歴",shares:"共有履歴",nlLabel:"今週のベストをメール",
        community:"コミュニティ",communitySec:"コミュニティ",communitySoon:"準備中",
        communityDesc:"特定の論客や企業を一緒に追うコミュニティを作ったりフォローし、引用してコメントを残し、自分でも投稿して交流できる場です。近日公開。",
        emptyFollows:"まだフォローした論客・企業・シリーズがありません。",emptyShares:"まだ共有した記事がありません。",
        followsPeople:"論客",followsCompany:"企業",followsSeries:"シリーズ",
        nsTitle:"通知設定",nsNew:"新着記事",nsFollow:"フォロー中の新着",
        nsEvents:"今後のイベント",nsNoEvents:"予定されたイベントはありません。",nsRecent:"最近の通知",nsEvSubEmpty:"通知を登録したイベントはありません。イベントのベルを押して登録してください。",
        recentQ:"最近の検索",recentClear:"すべて消去",recentDel:"削除",
        calToday:"今日",calMonthView:"月別",calWeekView:"週別",calMonthSoon:"月別表示は近日公開予定です。",calEarnings:"決算",calActual:"実績",calAiSummary:"今週のAI要約"}
  };
  V82S.ko.skewAsOf = "기준일 {date}"; V82S.en.skewAsOf = "As of {date}"; V82S.ja.skewAsOf = "基準日 {date}";
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
  var STACKS_MARK = '<svg class="v82-stack-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 21 8l-9 4.5L3 8l9-4.5Z" fill="currentColor"/><path d="M4.6 11.6 3 12.4 12 17l9-4.6-1.6-.8L12 15.3l-7.4-3.7Z" fill="currentColor" opacity=".72"/><path d="M4.6 15.6 3 16.4 12 21l9-4.6-1.6-.8L12 19.3l-7.4-3.7Z" fill="currentColor" opacity=".45"/></svg>';
  var DRAWER_ICONS = {
    me:'<svg viewBox="0 0 24 24"><circle cx="12" cy="7.5" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/></svg>',
    bm:'<svg viewBox="0 0 24 24"><path d="M6 4.5h12v16l-6-4-6 4z"/></svg>',
    readlist:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.2l2.4 2.4 4.6-5"/></svg>',
    follows:'<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><circle cx="17" cy="9.5" r="2.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M14 15a5 5 0 0 1 7.5 4.3"/></svg>',
    shares:'<svg viewBox="0 0 24 24"><path d="M12 16V3m0 0L7.5 7.5M12 3l4.5 4.5"/><path d="M5 12v7h14v-7"/></svg>',
    skew:'<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8M15 7h6v6"/></svg>',
    themes:'<svg viewBox="0 0 24 24"><path d="M4 5.5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5"/></svg>',
    record:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 8V3m4 5 3.5-3.5"/></svg>',
    cal:ICONS.cal,
    home:ICONS.home,
    alerts:ICONS.notif,
    moon:'<svg class="v82-theme-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21.752 15.002A9.718 9.718 0 0 1 18 15.75C12.615 15.75 8.25 11.385 8.25 6c0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"/></svg>',
    sun:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    close:'<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>'
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
    var dr = document.createElement("div"); dr.id = "v82drawer";
    dr.setAttribute("role", "dialog"); dr.setAttribute("aria-modal", "true"); dr.setAttribute("aria-hidden", "true");
    document.body.appendChild(dr);

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
      var av = document.createElement("button"); av.id = "v82av"; av.innerHTML = STACKS_MARK;
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
      /* 2026-08-03: 서랍에서 바로 들어온 판정 기록·최근 읽은 글·북마크에도 이 바가 뜬다.
         그때는 EXPLORE_SUB가 없으므로(허브 경유가 아님) 일반 뒤로가기로 되돌린다. */
      sb.querySelector(".bk").onclick = function(){
        if (EXPLORE_SUB){ closeExploreSub(false); return; }
        try { history.back(); } catch (e) {}
      };
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
    /* 2026-08-05: 지표 상세(#v82ind)도 v82detail(기사 상세)과 같은 "드릴다운" 화면이라
       (v82cal처럼 하단 nav를 유지하는 최상위 탭이 아님) 열려 있는 동안 nav를 숨긴다. */
    var vind = $("v82ind"); if (vind && vind.classList.contains("on")) hide = true;
    nav.classList.toggle("v82-off", hide);
  }

  /* ---------- drawer ---------- */
  function renderDrawer(){
    var t = T(); var dr = $("v82drawer"); if (!dr) return;
    var curLang = (typeof LANG !== "undefined") ? LANG : "ko";
    var _dwT = function(k){ var s = (typeof v83T === "function") ? v83T(k) : null; return s || t[k] || k; };
    var recentReadLabel = curLang === "en" ? "Recently read" : (curLang === "ja" ? "最近読んだ記事" : "최근 읽은 글");
    function _dwItem(k, icon, label){ return '<button class="v82dw-item" data-act="' + k + '"><span class="ic">' + icon + '</span><span>' + (label || _dwT(k)) + '</span></button>'; }
    dr.innerHTML =
      '<div class="v82dw-top"><div class="v82dw-brand"><span class="v82dw-logo">' + STACKS_MARK + '</span><span class="v82dw-name">Stacks</span></div><div class="v82dw-actions">' +
        '<button class="v82dw-top-action" data-dw-theme aria-label="' + _dwT("appearance") + '">' + ((typeof THEME !== "undefined" && THEME === "dark") ? DRAWER_ICONS.moon : DRAWER_ICONS.sun) + '</button>' +
        '<button class="v82dw-x" aria-label="close">' + DRAWER_ICONS.close + '</button>' +
      '</div></div>' +
      '<div class="v82dw-menu v82dw-primary">' +
        _dwItem("me", DRAWER_ICONS.me, t.dwProfile) + _dwItem("bm", DRAWER_ICONS.bm) + _dwItem("readlist", DRAWER_ICONS.readlist, recentReadLabel) + _dwItem("follows", DRAWER_ICONS.follows, t.dwFollowing) +
        _dwItem("shares", DRAWER_ICONS.shares, t.dwShared) + _dwItem("skewnow", DRAWER_ICONS.skew, t.skewTitle) + _dwItem("themes", DRAWER_ICONS.themes) +
        _dwItem("record", DRAWER_ICONS.record) + _dwItem("cal", DRAWER_ICONS.cal) +
      '</div><div class="v82dw-divider"></div><div class="v82dw-menu v82dw-secondary">' +
        _dwItem("home", DRAWER_ICONS.home) + _dwItem("alerts", DRAWER_ICONS.alerts) +
      '</div>' +
      '<div class="v82dw-langs">' +
        '<button data-lang="ko" class="v82dw-lb ' + (curLang === "ko" ? "on" : "") + '">한국어</button>' +
        '<button data-lang="en" class="v82dw-lb ' + (curLang === "en" ? "on" : "") + '">English</button>' +
        '<button data-lang="ja" class="v82dw-lb ' + (curLang === "ja" ? "on" : "") + '">日本語</button>' +
      '</div>';
    dr.querySelector(".v82dw-x").onclick = function(){ closeDrawer(); };
    var themeButton = dr.querySelector("[data-dw-theme]");
    if (themeButton) themeButton.onclick = function(){
      if (typeof toggleTheme === "function") toggleTheme();
      themeButton.innerHTML = (typeof THEME !== "undefined" && THEME === "dark") ? DRAWER_ICONS.moon : DRAWER_ICONS.sun;
    };
    var acts = dr.querySelectorAll("[data-act]");
    for (var ai = 0; ai < acts.length; ai++){ acts[ai].onclick = function(){ drawerAct(this.dataset.act); }; }
    var lbs = dr.querySelectorAll(".v82dw-lb");
    for (var li = 0; li < lbs.length; li++){ lbs[li].onclick = function(){ closeDrawer(true); if (typeof setLang === "function") setLang(this.dataset.lang); }; }
  }
  function drawerAct(act){
    if (act === "me"){ closeDrawer(true); if (typeof openMe === "function") openMe(); }
    else if (act === "home"){ closeDrawer(true); navGo("home"); }
    else if (act === "browse"){ closeDrawer(true); navGo("find"); }
    else if (act === "skew"){ closeDrawer(true); navGo("explore"); }
    else if (act === "skewnow"){ closeDrawer(true); try { if (typeof window.v82OpenSkew === "function") window.v82OpenSkew(); } catch (e) {} }
    /* openThemes/openScoreboard는 #feed로 smooth scroll을 걸어서, 서랍으로 들어오면
       상단 ←+제목 바를 지나쳐 내려간 채로 착지한다(nav가 v82hide로 접힘). 맨 위로 되돌린다. */
    else if (act === "themes"){ closeDrawer(true); if (typeof openThemes === "function") openThemes(); toTop(); try { setActive(); } catch(e){} }
    else if (act === "record"){ closeDrawer(true); if (typeof openScoreboard === "function") openScoreboard(); toTop(); try { setActive(); } catch(e){} }
    else if (act === "cal"){ closeDrawer(true); navGo("cal"); }
    else if (act === "alerts"){ closeDrawer(true); navGo("notif"); }
    else if (act === "bm"){ closeDrawer(true); goHomeThen(function(){ if (typeof v83Bookmarks === "function") v83Bookmarks(); }); }
    else if (act === "readlist"){ closeDrawer(true); goHomeThen(function(){ if (typeof v83ReadList === "function") v83ReadList(); }); }
    else if (act === "follows"){ closeDrawer(true); openList("follows"); }
    else if (act === "shares"){ closeDrawer(true); openList("shares"); }
    else closeDrawer();
  }
  function openDrawer(){
    if (!mq.matches) return;
    renderDrawer();
    $("v82drawer").classList.add("on"); $("v82scrim").classList.add("on");
    $("v82drawer").setAttribute("aria-hidden", "false");
    document.body.classList.add("v82-drawer-open");
    refreshNav();
    if (typeof pushView === "function") pushView();
  }
  function closeDrawer(fromPop){
    var dr = $("v82drawer");
    if (!dr || !dr.classList.contains("on")) return false;
    dr.classList.remove("on"); $("v82scrim").classList.remove("on");
    dr.setAttribute("aria-hidden", "true");
    document.body.classList.remove("v82-drawer-open");
    refreshNav();
    if (!fromPop) silentBack();
    return true;
  }
  document.addEventListener("keydown", function(e){
    if (e.key === "Escape") closeDrawer();
  });

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
    return ["v82explore","v82hub","v82notif","v82picker","v82list","v82cal","v82ind"].some(function(id){ var s=$(id); return s && s.classList.contains("on"); });
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
  function skewData(lo, hi){
    var out = [];
    var inWindow = function(it){ return (!lo || it.date >= lo) && (!hi || it.date <= hi); };
    var summarize = function(items){
      if (typeof skewConsensus === "function") return skewConsensus(items);
      var t = stanceTally(items), d = t.bull + t.bear;
      return { side:t.bull > t.bear ? "bull" : t.bear > t.bull ? "bear" : "mix", pct:d ? Math.max(t.bull,t.bear)/d : 0,
        sourceBull:t.bull, sourceBear:t.bear, sourceDir:d, sourceCount:d, sourceSplit:0,
        articleBull:t.bull, articleBear:t.bear, articleDir:d, lowSample:d < 5 };
    };
    var add = function(kind, key, label, icon, items, min){
      var c = summarize(items); if (c.articleDir < min) return;
      out.push({ kind:kind, key:key, label:label, icon:icon || "", bull:c.articleBull, bear:c.articleBear,
        sourceBull:c.sourceBull, sourceBear:c.sourceBear, sourceDir:c.sourceDir, sourceCount:c.sourceCount,
        articleDir:c.articleDir, pct:c.pct, side:c.side, lowSample:c.lowSample, items:items.slice() });
    };
    try {
      Object.keys(THEMES).forEach(function(k){ add("theme", k, THEMES[k].label[LANG], THEMES[k].icon, themeItems(k).filter(inWindow), 1); });
      var byEnt = {};
      ITEMS.forEach(function(it){ if(!itemStance(it) || !inWindow(it)) return; itemEntities(it).forEach(function(e){ if(ENTITIES[e]&&ENTITIES[e].kind==="company"){ (byEnt[e]=byEnt[e]||[]).push(it); } }); });
      Object.keys(byEnt).forEach(function(e){ add("ent", e, entName(e), "", byEnt[e], 3); });
    } catch(e){}
    var rankBucket = function(o){ return o.side === "mix" ? 2 : o.lowSample ? 1 : 0; };
    out.sort(function(a,b){ return (rankBucket(a)-rankBucket(b)) || (b.pct-a.pct) || (b.articleDir-a.articleDir); });
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
  /* 2026-08-04 (june): "섹터 쏠림이 지난주보다 얼마나 더 쏠렸는지"가 차별점이다.
     데스크톱(v83)에는 이미 있지만 모바일에는 현재 상태 막대뿐이었다 — 대부분의 독자가
     못 보는 자리에 있던 셈. 계산은 index.html의 v83ThemeAttention을 그대로 재사용한다.
     로직을 여기서 다시 구현하면 두 셸의 숫자가 갈라진다. 그 함수가 없으면(로드 순서·구버전)
     조용히 통째로 생략하고 기존 목록만 보여준다. */
  function skewTrendHtml(){
    if (typeof v83ThemeAttention !== "function") return "";
    var t = T(), h = "";
    try {
      var iso = function(off){
        if (typeof skewLocalIsoDate === "function") return skewLocalIsoDate(off);
        var d = new Date(); d.setHours(12, 0, 0, 0); d.setDate(d.getDate() - off);
        return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
      };
      var nowA = v83ThemeAttention(iso(6), iso(0));      /* 최근 7일 */
      var prevA = v83ThemeAttention(iso(13), iso(7));    /* 그 전 7일 */
      if (!nowA.length) return "";
      var sideLb = function(c){ return c.side === "bull" ? t.bull : c.side === "bear" ? t.bear : t.mix; };
      var statLb = function(c){
        var sources = c.sourceDir || c.sourceCount || 0, posts = c.dir || c.articleDir || 0;
        return sources + " " + t.sourceUnit + " · " + posts + " " + t.postUnit
          + (c.lowSample ? " · " + t.smallSample : "");
      };
      /* 2026-08-11: 순위 목록(.v82-tr-row)은 .v82-tr-chip(세로 배치, 폭 여유 있음)과 달리
         한 줄에 순위·이름·강세율·통계·변동배지를 다 넣어야 해서 statLb 전체(출처+글)를 쓰면
         테마 이름(.nm)이 밀려 잘렸다. 행 요약은 글 수 + 표본 적음만 남기고, 출처 구성은
         행을 탭해 들어가는 테마 상세에서 보게 한다(다른 값을 없앤 게 아니라 자리만 옮김). */
      var rowStatLb = function(c){
        var posts = c.dir || c.articleDir || 0;
        return posts + " " + t.postUnit + (c.lowSample ? " · " + t.smallSample : "");
      };
      /* 2026-08-11 (june 승인): 출처 1곳이면 %를 안 쓰고, 2곳 이상이면 분수(강세 2/3)로 —
         v83SkewShare()가 index.html에 있고 데스크톱과 완전히 같은 계산(분자=max(sourceBull,
         sourceBear), 분모=sourceDir)을 쓴다. 없으면(로드 순서·구버전) 조용히 숫자를 뺀다 —
         거짓 %를 보여주는 것보다 낫다. */
      var share = function(c){ return typeof v83SkewShare === "function" ? v83SkewShare(c) : ""; };
      var chip = function(lb, c, now){
        return '<span class="v82-tr-chip' + (now ? " now" : "") + '"><small>' + esc(lb) + '</small>'
          + '<b>' + (c.icon ? c.icon + " " : "") + esc(c.label) + '</b>'
          + '<span class="sd ' + c.side + '">' + esc(sideLb(c)) + share(c) + ' · ' + esc(statLb(c)) + '</span></span>';
      };
      var topNow = nowA[0], topPrev = prevA.length ? prevA[0] : null;
      h += '<div class="v82-tr">';
      h += '<div class="v82-tr-h">' + esc(t.trWk) + '</div>';
      h += '<div class="v82-tr-hero">'
         + (topPrev && topPrev.key !== topNow.key
              ? chip(t.trLast, topPrev, false) + '<span class="v82-tr-arr">→</span>' + chip(t.trNow, topNow, true)
              : chip(t.trNow, topNow, true))
         + '</div>';
      h += '<p class="v82-tr-cap">' + esc(topPrev ? (topPrev.key !== topNow.key ? t.trMove : t.trSame) : t.trOnly) + '</p>';
      var prevIdx = {}; prevA.forEach(function(c, i){ prevIdx[c.key] = i; });
      h += '<div class="v82-tr-rk">' + nowA.slice(0, 6).map(function(c, i){
        var pi = prevIdx[c.key], mv;
        if (pi === undefined) mv = '<span class="mv new">' + esc(t.trNew) + '</span>';
        else if (pi > i) mv = '<span class="mv up">▲' + (pi - i) + '</span>';
        else if (pi < i) mv = '<span class="mv dn">▼' + (i - pi) + '</span>';
        else mv = '<span class="mv">' + esc(t.trKeep) + '</span>';
        return '<button class="v82-tr-row" data-th="' + esc(c.key) + '">'
          + '<span class="rk">' + (i + 1) + '</span>'
          + '<span class="nm">' + (c.icon ? c.icon + " " : "") + esc(c.label) + '</span>'
          + '<span class="sd ' + c.side + '">' + esc(sideLb(c)) + share(c) + '</span>'
          + '<span class="n">' + esc(rowStatLb(c)) + '</span>'
          + mv + '</button>';
      }).join("") + '</div>';
      h += '</div>';
    } catch (e){ return ""; }
    return h;
  }
  function skewSubHtml(){
    var t = T(), rows = skewData(skewLocalIsoDate(6), skewLocalIsoDate(0)), html = "";
    var sourceLatest = t.sourceLatest || (LANG === "en" ? "latest" : LANG === "ja" ? "最新" : "최신");
    var sourceMissing = t.sourceMissing || (LANG === "en" ? "No original link" : LANG === "ja" ? "原文リンクなし" : "원문 연결 없음");
    html += '<div class="v82-skew-sub" style="margin-top:2px">' + t.skewSub + '</div>';
    html += '<div class="v82-skew-method">' + esc(t.skewMethod + " · " + t.skewAsOf.replace("{date}", skewLocalIsoDate(0))) + '</div>';
    html += skewTrendHtml();
    if (!rows.length){
      html += '<div class="v82-empty">아직 쏠림을 계산할 데이터가 부족합니다.</div>';
    } else {
      /* 데스크톱과 모바일 모두 최근 7일 창을 사용한다. */
      html += '<div class="v82-hub-sec">' + esc(t.trAll) + '</div>';
      rows.forEach(function(o, idx){
        var dir = o.sourceDir || 0, bp = dir ? Math.round((o.sourceBull || 0) / dir * 100) : 0, rp = 100 - bp;
        /* 2026-08-11: leanLb에 sampleDetail("글 N개 · 출처 N곳")까지 붙이면 같은 줄에서
           출처/글 수가 아래 .v82-skew-cts, 오른쪽 소스 토글과 3중으로 겹쳐 .v82-skew-name이
           30px까지 밀려 테마 이름이 안 보였다. "표본 적음" 표시는 유지하고 수치 중복만 뺀다. */
        var leanLb = (o.side === "bull" ? t.bull : o.side === "bear" ? t.bear : t.mix) + " " + Math.round(o.pct * 100) + "%"
          + (o.lowSample ? " · " + t.smallSample : "");
        /* 출처 수는 오른쪽 .v82-skew-source-toggle 버튼이 이미 보여준다 — 여기서는 글 수만. */
        var stat = (o.articleDir || 0) + " " + t.postUnit;
        var sourceCount = skewSourceBreakdown(o.items).length;
        var sourceToggle = '<button type="button" class="v82-skew-source-toggle" aria-expanded="false"'
          + ' onclick="toggleSkewSources(this,event)">' + esc(sourceCount + " " + t.sourceUnit) + '</button>';
        var sourceCfg = { cls:"skew-source-detail v82-skew-source-detail", title:t.sourceTitle || t.sourceUnit,
          empty:t.sourceEmpty || "", original:t.sourceOriginal || "", originalMissing:sourceMissing, latest:sourceLatest, bull:t.bull, bear:t.bear, mix:t.mix, postUnit:t.postUnit };
        html += '<div class="v82-skew-row-wrap"><div class="v82-skew-row-line"><button class="v82-skew-row" data-i="' + idx + '">'
          + '<div class="v82-skew-top"><span class="v82-skew-name">' + (o.icon ? o.icon + " " : "") + esc(o.label) + '</span>'
          + '<span class="v82-skew-lean ' + o.side + '">' + esc(leanLb) + '</span></div>'
          + '<div class="v82-skew-track"><i class="b" style="width:' + bp + '%"></i><i class="r" style="width:' + rp + '%"></i></div>'
          + '<div class="v82-skew-cts"><span>' + esc(stat) + '</span><span>' + t.bull + ' ' + o.sourceBull + ' · ' + t.bear + ' ' + o.sourceBear + '</span></div></button>'
          + sourceToggle + '</div>' + skewSourceDetailHtml(o.items, sourceCfg) + '</div>';
      });
    }
    return html;
  }
  /* 2026-08-14 (모바일 쏠림 바): index.html 인라인 스크립트의 MKT_BAR_EL(#mktBar
     정적 노드)/mktPaint()를 재사용한다 - v82.js는 그 뒤에 로드되므로 접근 가능하다.
     데스크톱 v83과 같은 클래스(.mkt-bar-skew)를 붙여 카드형 CSS(스코프는 index.html
     쪽에서 html.v83 접두사를 뗀 채 공유)를 그대로 타되, mq.matches로 데스크톱에서는
     절대 실행되지 않게 막는다 - openSkewSub()는 window.v82OpenSkew(mq.matches 가드)나
     renderHub()의 메뉴 버튼(그 자체가 openHub() 뒤에서만 노출 - openHub()도 mq.matches
     가드)을 거쳐야만 불리므로 이중으로 막혀 있지만, 여기서도 한 번 더 확인한다(방어적,
     비용 없음). 서브뷰를 벗어나는 모든 지점(허브로 뒤로가기 closeHubSub, 홈/찾기/탐색
     강제 이탈 clearSubState, 여기 목록 항목 클릭으로 허브를 통째로 떠나는 두 핸들러)에서
     mktMobileSkewExit()를 불러 window.MKT_M_SKEW를 내린다 - #v82hub는 .v82-screen이라
     닫히면 display:none이라(assets/v82.css) 바를 안 내려도 시각적으로는 이미 안 보이지만,
     플래그를 정확히 유지해야 다음 mktPaint() 호출(언어 전환 등)이 헷갈리지 않는다. */
  function mktMobileSkewEnter(container){
    try {
      if (!mq.matches) return;
      var bar = window.MKT_BAR_EL;
      if (!bar || !container) return;
      bar.classList.add("mkt-bar-skew");
      container.insertBefore(bar, container.firstChild);
      window.MKT_M_SKEW = true;
      if (typeof window.mktPaint === "function") window.mktPaint();
    } catch (e) {}
  }
  function mktMobileSkewExit(){
    try {
      window.MKT_M_SKEW = false;
      if (typeof window.mktPaint === "function") window.mktPaint();
    } catch (e) {}
  }
  function renderSkewSub(){
    var hub = $("v82hub"); if (!hub) return;
    var head = hub.querySelector(".v82-inner");
    if (!head){ head = document.createElement("div"); head.className = "v82-inner"; hub.appendChild(head); }
    var rows = skewData(skewLocalIsoDate(6), skewLocalIsoDate(0));
    head.innerHTML = skewSubHtml();
    mktMobileSkewEnter(head);                 /* 목록 맨 위에 시장 바를 꽂는다(innerHTML로 갈아끼운 뒤) */
    var srows = head.querySelectorAll(".v82-skew-row");
    for (var i = 0; i < srows.length; i++){
      srows[i].onclick = function(){
        var o = rows[+this.dataset.i]; if (!o) return;
        HUB_SUB = null;                       /* 허브를 통째로 떠난다 */
        mktMobileSkewExit();
        closeHub(true); silentBack();
        try { if (o.kind === "theme" && typeof openTheme === "function") openTheme(o.key);
              else if (typeof entityFeedView === "function") entityFeedView(o.key); } catch (e) {}
        setActive();
      };
    }
    var trows = head.querySelectorAll(".v82-tr-row");
    for (var ti = 0; ti < trows.length; ti++){
      trows[ti].onclick = function(){
        var k = this.dataset.th; if (!k) return;
        HUB_SUB = null;
        mktMobileSkewExit();
        closeHub(true); silentBack();
        try { if (typeof openTheme === "function") openTheme(k); } catch (e) {}
        setActive();
      };
    }
  }
  function openSkewSub(fromHistory){
    HUB_SUB = "skew";
    renderSkewSub();
    setHeadTitle("v82hub", T().skewTitle);
    var hub = $("v82hub"); if (hub) hub.scrollTop = 0;
    if (!fromHistory && typeof pushView === "function") pushView();
    setActive();
    if (typeof stkSyncUrlSoon === "function") stkSyncUrlSoon();
  }
  function closeHubSub(fromPop){
    HUB_SUB = null;
    mktMobileSkewExit();
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
    var go = function(){ try { window.scrollTo(0, 0); } catch (e) {} };
    go();
    requestAnimationFrame(go);
    setTimeout(go, 60); setTimeout(go, 220);   /* 진행 중인 smooth scroll을 이긴다 */
    var nav = document.querySelector("nav"); if (nav) nav.classList.remove("v82hide");
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
      mktMobileSkewExit();
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
  window.v82OpenSkew = function(fromHistory){
    if (!mq.matches) return false;
    openHub();
    openSkewSub(!!fromHistory);
    return true;
  };
  window.v82HubSub = function(){ return HUB_SUB; };
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
    /* 2026-08-03: 헤더 제목은 서랍의 메뉴 이름과 같아야 한다(테마 논쟁·판정 기록과 동일
       규칙). 기존 T().follows/shares는 "팔로우 내역"·"공유 내역"이라 메뉴명과 달랐다. */
    setHeadTitle("v82list", kind === "shares" ? T().dwShared : T().dwFollowing);
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

  /* ---------- MOBILE CALENDAR (v82.15, 2026-08-05): Toss-style week view ----------
     데스크톱 v83 캘린더(index.html의 renderV83CalPage/tcalRowHtml/V83CAL 등)는 건드리지
     않는다 — 여기서는 순수 데이터 함수(v83CalAllRows/tcalWeekGroups/tcalWeekLabel/
     tcalSunday/tcalYmd/TCAL_FLAG/logoUrl 등, 전부 index.html 전역)만 재사용하고
     필터 상태(V82CAL_FILTER)와 렌더링은 모바일 전용으로 완전히 분리했다.
     주의: V83CAL.filter/country는 데스크톱과 공유되는 전역이라 여기서는 안 쓴다 —
     "실적" 필터는 데스크톱의 "이벤트"(전체 뉴스 이벤트) 필터와 의미가 다르다(실데이터
     확인 결과 이벤트 kind는 earnings/macro 두 종류가 섞여 있고, "실적"은 kind==="earnings"
     만을 뜻해야 맞다 — 그대로 v83CalFilter('event')를 재사용하면 macro 뉴스까지
     "실적" 탭에 섞여 나온다). V83CAL.anchor만 렌더 시점마다 "오늘"로 맞춘다. */
  var V82CAL_FILTER = { filter: "all" };
  /* 2026-08-05(월간뷰): 주간뷰와 토글되는 두 번째 모드. 데스크톱 V83CAL.y/.m는
     화살표로 월을 넘기는 상태라 여기서 같이 쓰면 두 화면이 서로 간섭한다 —
     그래서 공유하지 않고 모바일 전용 변수 하나만 둔다. 월 이동 UI는 없다(참고
     이미지에도 화살표가 없다) — 항상 "이번 달"만 고정으로 보여준다. openCalScreen()이
     열 때마다 "week"로 리셋해 재진입 시 항상 주간뷰부터 시작하게 한다. */
  var V82CAL_MODE = "week";

  /* "21:30" → "오후 9시 30분" 같은 표기. indicator.nextTime은 이미 KST 문자열이라
     (지표 상세 페이지도 변환 없이 그대로 표시) 타임존 계산 없이 파싱만 한다.
     기존 코드에 재사용 가능한 시간 포맷 헬퍼가 없어 새로 작성했다. */
  function v82CalTimeLabel(hhmm){
    if (!hhmm || hhmm.indexOf(":") < 0) return "";
    var bits = hhmm.split(":"); var h = parseInt(bits[0], 10), m = parseInt(bits[1], 10) || 0;
    if (isNaN(h)) return "";
    var pm = h >= 12; var h12 = h % 12; if (h12 === 0) h12 = 12;
    if (LANG === "ja"){
      var pj = pm ? "午後" : "午前";
      return m === 0 ? (pj + h12 + "時") : (pj + h12 + "時" + m + "分");
    }
    if (LANG === "en"){
      var pe = pm ? "PM" : "AM";
      return m === 0 ? (h12 + pe) : (h12 + ":" + (m < 10 ? "0" + m : m) + pe);
    }
    var pk = pm ? "오후" : "오전";
    return m === 0 ? (pk + " " + h12 + "시") : (pk + " " + h12 + "시 " + m + "분");
  }

  /* v83CalAllRows()(index.html 전역, 순수 함수)를 그대로 불러온 뒤 모바일 전용
     필터만 로컬로 적용한다 — v83CalFiltered()는 공유 V83CAL.filter/country를
     건드리므로 쓰지 않는다(위 섹션 코멘트 참고). */
  function v82CalRows(){
    var rows = (typeof v83CalAllRows === "function") ? v83CalAllRows() : [];
    if (V82CAL_FILTER.filter === "indicator") rows = rows.filter(function(r){ return r.isIndicator; });
    else if (V82CAL_FILTER.filter === "earnings") rows = rows.filter(function(r){ return !r.isIndicator && r.kind === "earnings"; });
    return rows;
  }

  /* 이번 주(일~토) 지표 회차 수 + 실적 발표 수를 세어 "AI가 요약한 것처럼" 보이는
     문장을 만든다 — 실제 LLM 호출은 없다(예산/연동 없음, 이번 작업 범위 밖). */
  function v82CalWeekSummaryText(){
    var TS = (typeof TCAL_STR !== "undefined" && (TCAL_STR[LANG] || TCAL_STR.ko)) || {};
    var todayD = new Date(); todayD.setHours(0, 0, 0, 0);
    var sun = tcalSunday(todayD), sat = new Date(sun.getTime() + 6 * 86400000);
    var sunStr = tcalYmd(sun), satStr = tcalYmd(sat);
    var rows = (typeof v83CalAllRows === "function" ? v83CalAllRows() : [])
      .filter(function(r){ return r.date >= sunStr && r.date <= satStr; });
    var indN = rows.filter(function(r){ return r.isIndicator; }).length;
    var earnN = rows.filter(function(r){ return !r.isIndicator && r.kind === "earnings"; }).length;
    if (!indN && !earnN) return TS.weekSummaryEmpty || "";
    if (LANG === "ja"){
      if (indN && earnN) return "今週、経済指標" + indN + "件・決算" + earnN + "件が予定されています";
      if (indN) return "今週、経済指標" + indN + "件が予定されています";
      return "今週、決算発表" + earnN + "件が予定されています";
    }
    if (LANG === "en"){
      if (indN && earnN) return "This week: " + indN + " indicator release" + (indN > 1 ? "s" : "") + " and " + earnN + " earnings report" + (earnN > 1 ? "s" : "") + " ahead.";
      if (indN) return "This week: " + indN + " indicator release" + (indN > 1 ? "s" : "") + " ahead.";
      return "This week: " + earnN + " earnings report" + (earnN > 1 ? "s" : "") + " ahead.";
    }
    if (indN && earnN) return "이번주 지표 " + indN + "건, 실적 " + earnN + "건이 예정되어 있어요";
    if (indN) return "이번주 지표 " + indN + "건이 예정되어 있어요";
    return "이번주 실적 " + earnN + "건이 예정되어 있어요";
  }

  /* 원형 아이콘(44px). 지표=국기(연회색 원 안에 작게 인셋), 실적/뉴스=회사 로고
     (원 전체를 채움). 실패 시 kind별 색(.ck-earnings/.ck-macro/.ck-x, 데스크톱
     캘린더 도트에서 쓰는 기존 색 범례 재사용)만 남는 원으로 폴백한다 — 데스크톱
     tcalRowHtml()의 onerror 전략(이미지만 숨기고 슬롯 크기는 고정이라 레이아웃이
     안 밀림)과 동일한 원리다. */
  function v82CalIconHtml(r){
    if (r.isIndicator){
      var flagCode = (typeof TCAL_FLAG !== "undefined" && TCAL_FLAG[r.ind.country]) || "";
      var flagImg = flagCode
        ? '<img src="https://flagcdn.com/48x36/' + flagCode + '.png" alt="" onerror="this.style.display=\'none\'">'
        : "";
      return '<span class="v82cal-icon v82cal-icon-flag">' + flagImg + '</span>';
    }
    var domain = (r.entity && typeof ENTITIES !== "undefined" && ENTITIES[r.entity] && ENTITIES[r.entity].logo) || null;
    var ck = "ck-" + (r.kind || "x");
    var img = (domain && typeof logoUrl === "function")
      ? '<img src="' + logoUrl(domain) + '" alt="" onerror="this.style.display=\'none\'">'
      : "";
    return '<span class="v82cal-icon ' + ck + '">' + img + '</span>';
  }

  /* 한 행. 지표는 발표 회차가 있으면(actual 존재) 실제/예측 비교색(.tcal-hi/.tcal-lo,
     데스크톱과 같은 규칙 재사용), 없으면(다음 예정) 발표 시각을 보여준다. 실적/뉴스
     이벤트는 "주요/관심" 같은 중요도 태그를 넣지 않는다(items.json의 events엔 그런
     필드가 없다 — date/entity/id/itemId/kind/label/title뿐이라 지어내지 않았다).
     실적 행 2번째 줄도 EPS 실제/예측이 아니라 티커다 — 같은 이유로 EPS 데이터가
     없어서, 있는 정보(티커)만 보여준다. */
  function v82CalRowHtml(r){
    var iconHtml = v82CalIconHtml(r);
    var title, subHtml = "", onclick;
    if (r.isIndicator){
      var ind = r.ind, unit = ind.unit || "";
      title = esc(ind.name[LANG] || ind.name.en);
      var hasActual = r.actual !== null && r.actual !== undefined;
      if (hasActual){
        var colorCls = "";
        if (r.forecast !== null && r.forecast !== undefined){
          if (r.actual > r.forecast + 1e-9) colorCls = "tcal-hi"; else if (r.actual < r.forecast - 1e-9) colorCls = "tcal-lo";
        }
        var TSf = (typeof TCAL_STR !== "undefined" && (TCAL_STR[LANG] || TCAL_STR.ko)) || {};
        var fTxt = (r.forecast === null || r.forecast === undefined) ? "" : (' · ' + esc(TSf.colForecast || "") + ' ' + esc(r.forecast + unit));
        subHtml = '<span class="v82cal-sub"><span class="' + colorCls + '">' + esc(T().calActual) + ' ' + esc(r.actual + unit) + '</span>' + fTxt + '</span>';
      } else {
        var tLbl = v82CalTimeLabel(ind.nextTime);
        if (tLbl) subHtml = '<span class="v82cal-sub v82cal-sub-muted">' + esc(tLbl) + '</span>';
      }
      /* 2026-08-05: 지표 행 탭 → 새 모바일 지표 상세(v82ind, 아래 섹션). 데스크톱
         전용 goIndicator()(index.html, INDICATOR_VIEW/render() 기반)는 그대로 두고
         건드리지 않는다 — 모바일은 별도 함수로 분기한다. 실적/뉴스 행(else 분기)의
         evGo() 폴백은 무수정. */
      onclick = "v82GoIndicator('" + ind.id + "')";
    } else {
      title = esc((r.label && (r.label[LANG] || r.label.en)) || (r.title && (r.title[LANG] || r.title.en)) || "");
      var ticker = (r.entity && typeof ENTITIES !== "undefined" && ENTITIES[r.entity] && ENTITIES[r.entity].ticker) || "";
      if (ticker) subHtml = '<span class="v82cal-sub v82cal-sub-muted">' + esc(ticker) + '</span>';
      onclick = "evGo('" + r.id + "')";
    }
    return '<button type="button" class="v82cal-row" onclick="' + onclick + '">' + iconHtml
      + '<span class="v82cal-row-txt"><span class="v82cal-row-title">' + title + '</span>' + subHtml + '</span></button>';
  }

  /* 월간뷰 칩 전용 제목 헬퍼 — v82CalRowHtml()과 같은 우선순위(ind.name → label →
     title)로 표시용 문자열만 뽑는다. v82CalRowHtml() 자체는 건드리지 않는다(주간뷰
     회귀 위험 최소화). */
  function v82CalRowTitle(r){
    if (r.isIndicator){
      var ind = r.ind;
      return (ind && ind.name && (ind.name[LANG] || ind.name.en)) || "";
    }
    return (r.label && (r.label[LANG] || r.label.en)) || (r.title && (r.title[LANG] || r.title.en)) || "";
  }

  function v82CalDayHeadHtml(dateStr, todayStr){
    var d = new Date(dateStr + "T00:00:00");
    var wd = (typeof TCAL_WD1 !== "undefined" && TCAL_WD1[LANG]) || TCAL_WD1.ko;
    var chip = dateStr === todayStr ? ('<span class="v82cal-today-chip">' + esc(T().calToday) + '</span>') : "";
    return '<div class="v82cal-day-h" data-date="' + dateStr + '"><span class="v82cal-day-num">' + d.getDate()
      + '</span><span class="v82cal-day-wd">' + esc(wd[d.getDay()]) + '</span>' + chip + '</div>';
  }

  /* group.rows는 tcalWeekGroups()가 이미 날짜 오름차순으로 정렬해서 준다 — 날짜가
     바뀔 때마다 새 day-group 컨테이너를 연다(데스크톱은 showDate로 한 줄에 압축해
     보여주지만, 모바일은 참고 이미지 구조상 날짜별 소제목 블록이 필요하다). */
  function v82CalWeekRowsHtml(group, todayStr){
    var html = "", lastDate = null, open = false;
    group.rows.forEach(function(r){
      if (r.date !== lastDate){
        if (open) html += "</div>";
        lastDate = r.date; open = true;
        html += v82CalDayHeadHtml(r.date, todayStr) + '<div class="v82cal-day-rows">';
      }
      html += v82CalRowHtml(r);
    });
    if (open) html += "</div>";
    return html;
  }

  /* 월~토 6열, 오늘 강조, 토요일 흐리게. 탭 → 스크롤 + 선택 표시. 이 파일의 기존
     방식대로 인라인 onclick 문자열 대신 querySelector 후 바인딩한다. */
  function v82CalRenderStrip(){
    var wrap = $("v82calStrip"); if (!wrap) return;
    var todayD = new Date(); todayD.setHours(0, 0, 0, 0);
    var todayStr = tcalYmd(todayD);
    var sun = tcalSunday(todayD);
    var wd = (typeof TCAL_WD1_MINI !== "undefined" && TCAL_WD1_MINI[LANG]) || TCAL_WD1_MINI.ko;
    var t = T();
    var html = "";
    for (var i = 1; i <= 6; i++){
      var d = new Date(sun.getTime() + i * 86400000);
      var dStr = tcalYmd(d);
      var isToday = dStr === todayStr;
      var cls = "v82cal-strip-btn" + (isToday ? " today" : "") + (i === 6 ? " sat" : "");
      var label = isToday ? t.calToday : wd[i - 1];
      html += '<button type="button" class="' + cls + '" data-date="' + dStr + '">'
        + '<span class="v82cal-strip-wd">' + esc(label) + '</span>'
        + '<span class="v82cal-strip-num' + (isToday ? " badge" : "") + '">' + d.getDate() + '</span></button>';
    }
    wrap.innerHTML = html;
    var btns = wrap.querySelectorAll(".v82cal-strip-btn");
    for (var b = 0; b < btns.length; b++){ btns[b].onclick = function(){ v82CalPickDay(this.dataset.date); }; }
  }
  function v82CalPickDay(dateStr, behavior){
    try {
      var strip = $("v82calStrip");
      if (strip){
        var btns = strip.querySelectorAll(".v82cal-strip-btn");
        for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("sel", btns[i].dataset.date === dateStr);
      }
      var body = $("v82calGroups");
      var target = body && body.querySelector('[data-date="' + dateStr + '"]');
      /* 이벤트 없는 날짜에는 day-head가 없을 수 있다. 그 날짜가 속한 주의
         divider를 대신 잡아 월간 셀 탭도 항상 해당 주로 이동하게 한다. */
      if (!target && body && typeof tcalSunday === "function"){
        var d = new Date(dateStr + "T00:00:00");
        target = body.querySelector('[data-week-start="' + tcalYmd(tcalSunday(d)) + '"]');
      }
      if (target && target.scrollIntoView) target.scrollIntoView({ behavior: behavior || "smooth", block: "start" });
    } catch (e) {}
  }
  function v82CalGoToday(){
    var d = new Date(); d.setHours(0, 0, 0, 0);
    v82CalPickDay(tcalYmd(d));
  }
  /* ---------- 2026-08-05: 월간뷰 (주간뷰와 헤더 토글로 전환되는 두 번째 모드) ----------
     "+N개" 오버플로 라벨. 템플릿 치환 헬퍼가 이 파일에 따로 없어(v82CalWeekSummaryText도
     LANG별로 직접 문자열을 짠다) 같은 스타일로 맞춘다. */
  function v82CalMoreLabel(n){
    if (LANG === "ja") return "+" + n + "件";
    if (LANG === "en") return "+" + n + " more";
    return "+" + n + "개";
  }
  /* v82CalWeekSummaryText()와 정확히 같은 패턴(카운트 기반, 실제 LLM 호출 없음)을
     주 단위 대신 달 단위로 확장한 것. 필터(V82CAL_FILTER)는 적용하지 않는다 —
     주간뷰 원본도 v83CalAllRows()를 그대로 세므로 동일하게 맞춘다. */
  function v82CalMonthSummaryText(){
    var TS = (typeof TCAL_STR !== "undefined" && (TCAL_STR[LANG] || TCAL_STR.ko)) || {};
    var now = new Date(); now.setHours(0, 0, 0, 0);
    var y = now.getFullYear(), mo = now.getMonth();
    var msStr = tcalYmd(new Date(y, mo, 1)), meStr = tcalYmd(new Date(y, mo + 1, 0));
    var rows = (typeof v83CalAllRows === "function" ? v83CalAllRows() : [])
      .filter(function(r){ return r.date >= msStr && r.date <= meStr; });
    var indN = rows.filter(function(r){ return r.isIndicator; }).length;
    var earnN = rows.filter(function(r){ return !r.isIndicator && r.kind === "earnings"; }).length;
    if (!indN && !earnN) return TS.monthNoData || "";
    if (LANG === "ja"){
      if (indN && earnN) return "今月、経済指標" + indN + "件・決算" + earnN + "件が予定されています";
      if (indN) return "今月、経済指標" + indN + "件が予定されています";
      return "今月、決算発表" + earnN + "件が予定されています";
    }
    if (LANG === "en"){
      if (indN && earnN) return "This month: " + indN + " indicator release" + (indN > 1 ? "s" : "") + " and " + earnN + " earnings report" + (earnN > 1 ? "s" : "") + " ahead.";
      if (indN) return "This month: " + indN + " indicator release" + (indN > 1 ? "s" : "") + " ahead.";
      return "This month: " + earnN + " earnings report" + (earnN > 1 ? "s" : "") + " ahead.";
    }
    if (indN && earnN) return "이번달 지표 " + indN + "건, 실적 " + earnN + "건이 예정되어 있어요";
    if (indN) return "이번달 지표 " + indN + "건이 예정되어 있어요";
    return "이번달 실적 " + earnN + "건이 예정되어 있어요";
  }
  /* 헤드라인 문구 디스패치. "✦ 이번주 AI 요약" 링크는 참고 이미지에도 월간뷰에서
     문구가 그대로다(월간용 문구로 바꾸지 않는다) — june 지시 원문 그대로 유지. */
  function v82CalSummaryText(){ return V82CAL_MODE === "month" ? v82CalMonthSummaryText() : v82CalWeekSummaryText(); }
  function v82CalRenderSummary(){
    var sum = $("v82calSummary"); if (!sum) return;
    sum.innerHTML = '<div class="v82cal-summary-txt">' + esc(v82CalSummaryText()) + '</div>'
      + '<button type="button" class="v82cal-ai">✦ ' + esc(T().calAiSummary) + ' <span class="chev">›</span></button>';
  }
  /* 날짜 숫자 한 칸. hasEvent=그 날 이벤트 있음(진하게), today=오늘(연회색 배지) —
     데스크톱 미니 달력의 "발표 있는 날 볼드" 관례를 그대로 재사용한다. */
  function v82CalMonthDayNumHtml(dnum, dateStr, todayStr, hasEvent){
    var cls = "v82cal-month-daynum" + (hasEvent ? " has" : "") + (dateStr === todayStr ? " today" : "");
    return '<span class="' + cls + '">' + dnum + '</span>';
  }
  /* 셀 하나 = 버튼(전체가 탭 영역, 칩 포함) — data-date는 v82CalPickDay()가 주간뷰
     day-head와 같은 방식으로 찾을 수 있게 동일 속성명을 쓴다(과제 지시: 날짜 셀 탭 →
     주간뷰 전환 + 그 주로 스크롤, 기존 로직 재사용). 칩은 최대 2개, 나머지는 "+N개"
     텍스트 — 아이콘 없이 accent 단색 바만(과제 지시, 셀 폭이 좁아 로고/국기 생략). */
  function v82CalMonthCellHtml(y, mo, dnum, todayStr, byDate){
    var d = new Date(y, mo, dnum);
    var dateStr = tcalYmd(d);
    var dayRows = byDate[dateStr] || [];
    var hasEvent = dayRows.length > 0;
    var chipsHtml = "";
    if (hasEvent){
      var shown = dayRows.slice(0, 2);
      chipsHtml = '<span class="v82cal-month-chips">' + shown.map(function(r){
        return '<span class="v82cal-month-chip"><span class="v82cal-month-chip-txt">' + esc(v82CalRowTitle(r)) + '</span></span>';
      }).join("");
      if (dayRows.length > 2){
        chipsHtml += '<span class="v82cal-month-more">' + esc(v82CalMoreLabel(dayRows.length - 2)) + '</span>';
      }
      chipsHtml += '</span>';
    }
    /* v82CalMonthCellTap()은 v82.js 클로저 안에서만 보이는 함수라 인라인 onclick
       문자열(window 전역 스코프에서 평가됨)로는 못 부른다 — v82CalRowHtml()의
       goIndicator()/evGo()는 index.html 전역이라 인라인이 되지만 이건 다르다.
       그래서 data-date만 심어 두고, v82CalRenderMonth()가 렌더 뒤 .onclick을
       직접 배선한다(v82CalRenderStrip()과 같은 패턴). */
    return '<button type="button" class="v82cal-month-cell" data-date="' + dateStr + '">'
      + v82CalMonthDayNumHtml(dnum, dateStr, todayStr, hasEvent) + chipsHtml + '</button>';
  }
  /* 월~금 5열, 토/일 컬럼 자체가 없다(참고 이미지와 동일). 월 이동 없음 — 항상
     "오늘이 속한 달"만 고정으로 그린다(설계 이유는 위 V82CAL_MODE 주석 참고).
     leadBlanks: 그 달 1일의 요일에 따라 첫 주 앞을 얼마나 비울지(월=0 ~ 금=4),
     1일이 토/일이면 그 주엔 이 달 평일이 전혀 없거나(토) 월요일부터 바로 시작하는
     주(일, 다음날인 월요일부터가 이미 이 달 이틀째)라 0으로 둔다. */
  function v82CalRenderMonth(){
    var body = $("v82calGroups"); if (!body) return;
    var now = new Date(); now.setHours(0, 0, 0, 0);
    var y = now.getFullYear(), mo = now.getMonth();
    var todayStr = tcalYmd(now);
    var firstOfMonth = new Date(y, mo, 1);
    var daysInMonth = new Date(y, mo + 1, 0).getDate();
    var dow = firstOfMonth.getDay();
    var leadBlanks = (dow === 1) ? 0 : (dow === 2) ? 1 : (dow === 3) ? 2 : (dow === 4) ? 3 : (dow === 5) ? 4 : 0;

    var rows = v82CalRows();
    var byDate = {};
    rows.forEach(function(r){ (byDate[r.date] || (byDate[r.date] = [])).push(r); });

    var cells = [];
    for (var i = 0; i < leadBlanks; i++) cells.push('<span class="v82cal-month-cell v82cal-month-blank" aria-hidden="true"></span>');
    for (var dnum = 1; dnum <= daysInMonth; dnum++){
      var wd = new Date(y, mo, dnum).getDay();
      if (wd === 0 || wd === 6) continue; /* 토/일 컬럼 없음 */
      cells.push(v82CalMonthCellHtml(y, mo, dnum, todayStr, byDate));
    }
    var weekRows = "";
    for (var k = 0; k < cells.length; k += 5){
      weekRows += '<div class="v82cal-month-week">' + cells.slice(k, k + 5).join("") + '</div>';
    }
    var monthLbl = (typeof calLocale === "function")
      ? firstOfMonth.toLocaleDateString(calLocale(), { year: "numeric", month: "long" })
      : (y + "." + (mo + 1));
    body.innerHTML = '<div class="v82cal-month-divider"><span>' + esc(monthLbl) + '</span></div>'
      + '<div class="v82cal-month-grid">' + weekRows + '</div>';
    var cellBtns = body.querySelectorAll(".v82cal-month-cell[data-date]");
    for (var ci = 0; ci < cellBtns.length; ci++){
      cellBtns[ci].onclick = function(){ v82CalMonthCellTap(this.dataset.date); };
    }
  }
  /* 날짜 셀(또는 칩) 탭 → 주간뷰로 전환 + 그 날짜가 속한 주로 스크롤. 주간뷰는
     이번 달 시작 주부터 미래 4주까지 그리므로 현재 날짜보다 앞선 월간 셀도 찾을 수 있다. */
  function v82CalMonthCellTap(dateStr){
    v82CalOpenWeek();
    v82CalPickDay(dateStr);
  }
  /* 필터(전체/경제지표/실적) 반영 후 다시 그리는 대상은 .v82cal-groups(과제
     설명의 ".v82cal-body") 컨테이너 하나뿐이다. renderFeedOnly()는 데스크톱
     전용 재렌더 함수라 호출하지 않는다(모바일 DOM 구조를 모른다). */
  function v82CalRenderGroups(){
    var body = $("v82calGroups"); if (!body) return;
    var todayD = new Date(); todayD.setHours(0, 0, 0, 0);
    var todayStr = tcalYmd(todayD);
    /* V83CAL은 데스크톱과 공유되는 전역이지만 mountV83() 안이 아니라 스크립트
       최상위에서 var로 선언돼 있어(index.html) 모바일 전용 세션에서도 이미
       초기화돼 있다 — 존재 가드는 사실상 불필요하지만 방어적으로 남겨둔다.
       anchor만 "오늘"로 맞춘다 — 데스크톱에서 다른 날짜를 찍어 둔 세션이 있어도
       모바일 주간뷰는 항상 이번 주부터 시작해야 한다(참고 이미지에 주 이동
       화살표가 없다 = 이번 주 고정 설계). */
    try { if (typeof V83CAL !== "undefined" && V83CAL) V83CAL.anchor = todayStr; } catch (e) {}
    var rows = v82CalRows();
    /* 공용 tcalWeekGroups()는 현재 주 기준 과거 2주만 보존한다. 모바일 월간 셀에서
       이번 달 초 날짜를 탭할 수 있어야 하므로, 이번 달 1일이 속한 일요일부터
       현재 주+미래 4주까지 모바일 전용 그룹을 만든다. */
    var monthStart = new Date(todayD.getFullYear(), todayD.getMonth(), 1);
    var startSun = tcalSunday(monthStart);
    var currentSun = tcalSunday(todayD);
    var lastSun = new Date(currentSun.getTime() + 4 * 7 * 86400000);
    var monthStartStr = tcalYmd(monthStart), lastStr = tcalYmd(new Date(lastSun.getTime() + 6 * 86400000));
    var groups = [];
    for (var w = 0, gs = startSun; gs <= lastSun; w++, gs = new Date(startSun.getTime() + w * 7 * 86400000)){
      var ge = new Date(gs.getTime() + 6 * 86400000), gsStr = tcalYmd(gs), geStr = tcalYmd(ge);
      var gRows = rows.filter(function(r){ return r.date >= monthStartStr && r.date >= gsStr && r.date <= geStr && r.date <= lastStr; })
        .sort(function(a, b){ return a.date < b.date ? -1 : (a.date > b.date ? 1 : 0); });
      groups.push({ start: gs, end: ge, rows: gRows });
    }
    var html = "";
    if (!groups.length){
      var TS = (typeof TCAL_STR !== "undefined" && (TCAL_STR[LANG] || TCAL_STR.ko)) || {};
      html = '<div class="v82cal-empty">' + esc(TS.weekNoData || "") + '</div>';
    } else {
      groups.forEach(function(g){
        var label = (typeof tcalWeekLabel === "function") ? tcalWeekLabel(g.start) : "";
        html += '<div class="v82cal-wk-divider" data-week-start="' + tcalYmd(g.start) + '"><span>' + esc(label) + '</span></div>';
        if (g.rows.length) html += v82CalWeekRowsHtml(g, todayStr);
      });
    }
    body.innerHTML = html;
  }
  /* 모드(week/month) 분기 — 필터 재적용·모드 전환 양쪽에서 공통으로 부른다.
     v82CalRenderGroups()(주간뷰)는 이름·내부 로직 전부 무수정. */
  function v82CalRenderBody(){
    if (V82CAL_MODE === "month") v82CalRenderMonth(); else v82CalRenderGroups();
  }
  function v82CalSetFilter(f){
    V82CAL_FILTER.filter = (f === "indicator" || f === "earnings") ? f : "all";
    var fb = $("v82calFilterBar");
    if (fb){
      var btns = fb.querySelectorAll("[data-f]");
      for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("on", btns[i].dataset.f === V82CAL_FILTER.filter);
    }
    v82CalRenderBody();
  }
  /* 헤더 우측 토글 버튼 라벨: 주간뷰일 땐 "월별보기", 월간뷰일 땐 "주별보기"
     (지금 모드에서 다음에 갈 곳을 알려주는 문구 — 참고 이미지와 동일). */
  function v82CalSyncHeader(){
    var btn = document.querySelector("#v82cal-h .v82cal-month-btn");
    if (!btn) return;
    var t = T();
    btn.textContent = V82CAL_MODE === "month" ? t.calWeekView : t.calMonthView;
  }
  /* 요일 스트립(월~토 6열 미니 탭)은 주간뷰 전용 UI라 월간뷰에선 숨긴다(참고
     이미지에도 없다) — DOM은 그대로 두고 CSS로만 감춘다(v82CalGoToday 등 기존
     로직이 스트립 버튼을 계속 찾아도 안전하게 동작하도록). */
  function v82CalSyncStripVisibility(){
    var scr = $("v82cal");
    if (scr) scr.classList.toggle("v82cal-month-mode", V82CAL_MODE === "month");
  }
  function v82CalSetMode(mode){
    V82CAL_MODE = (mode === "month") ? "month" : "week";
    v82CalSyncHeader();
    v82CalSyncStripVisibility();
    v82CalRenderSummary();
    v82CalRenderBody();
    var scr = $("v82cal"); if (scr) scr.scrollTop = 0;
  }
  /* v82CalOpenMonth(): 이전엔 "준비 중" 토스트만 띄우던 자리 — 이제 실제로
     월간뷰로 전환한다. */
  function v82CalOpenMonth(){ v82CalSetMode("month"); }
  function v82CalOpenWeek(){ v82CalSetMode("week"); }
  function v82CalToggleMode(){ v82CalSetMode(V82CAL_MODE === "month" ? "week" : "month"); }

  /* 화면 최초 생성(지연 생성 — openCalScreen()에서 없을 때만 호출). 헤더는
     addHead() 공용 템플릿(뒤로가기+제목만)으로는 부족해서(오늘/월별보기 버튼이
     더 필요) 같은 .v82-sh 스타일을 쓰는 전용 헤더를 직접 만든다. */
  function v82CalBuildScreen(){
    if ($("v82cal")) return;
    var t = T(), IS = (typeof IND_STR !== "undefined" && (IND_STR[LANG] || IND_STR.ko)) || {};
    var s = document.createElement("div"); s.id = "v82cal"; s.className = "v82-screen v82cal-screen";
    s.innerHTML =
      '<div class="v82cal-strip" id="v82calStrip"></div>'
      + '<div class="v82cal-summary" id="v82calSummary"></div>'
      + '<div class="v82cal-groups" id="v82calGroups"></div>'
      + '<div class="v82cal-filterbar" id="v82calFilterBar"><div class="tcal-seg-group">'
      + '<button type="button" class="tcal-seg-btn on" data-f="all">' + esc(IS.filterAll || "All") + '</button>'
      + '<button type="button" class="tcal-seg-btn" data-f="indicator">' + esc(IS.filterInd || "Indicators") + '</button>'
      + '<button type="button" class="tcal-seg-btn" data-f="earnings">' + esc(t.calEarnings) + '</button>'
      + '</div></div>';
    document.body.appendChild(s);
    var fbtns = s.querySelectorAll("#v82calFilterBar [data-f]");
    for (var i = 0; i < fbtns.length; i++){ fbtns[i].onclick = function(){ v82CalSetFilter(this.dataset.f); }; }

    var h = document.createElement("div"); h.className = "v82-sh v82cal-sh"; h.id = "v82cal-h";
    h.setAttribute("aria-label", t.cal);
    h.innerHTML = '<button class="bk" aria-label="back">←</button><span class="v82cal-hsp"></span>'
      + '<button type="button" class="v82cal-today-btn">' + esc(t.calToday) + '</button>'
      + '<span class="v82cal-hsep">|</span>'
      + '<button type="button" class="v82cal-month-btn">' + esc(t.calMonthView) + '</button>';
    h.querySelector(".bk").onclick = function(){ navGo("home"); };
    h.querySelector(".v82cal-today-btn").onclick = function(){ v82CalGoToday(); };
    h.querySelector(".v82cal-month-btn").onclick = function(){ v82CalToggleMode(); };
    document.body.appendChild(h);
  }
  /* openCal()/closeCal()(index.html)이 호출하는 진입점 — index.html 쪽은 이제
     이 둘을 얇게 위임만 한다(과제 지시대로 index.html 본문 변경을 최소화하려고
     실제 로직은 전부 여기 v82.js에 뒀다). 열 때마다 본문을 통째로 다시 그린다
     (캐시 안 함 — 날짜가 바뀌었을 수 있어서). 매번 "week"로 리셋해 재진입 시
     항상 주간뷰부터 시작한다(월간뷰에서 나갔다 다시 들어와도 마지막 모드를
     기억하지 않음 — 과제의 "캘린더 열기 → 주간뷰 기본 화면" 요구와 일치). */
  function openCalScreen(){
    if (!mq.matches) return;
    V82CAL_MODE = "week";
    v82CalBuildScreen();
    v82CalSyncHeader();
    v82CalSyncStripVisibility();
    v82CalRenderStrip();
    v82CalRenderSummary();
    v82CalRenderBody();
    showScreen("v82cal");
    /* 렌더 직후 현재 주를 먼저 보여준다. 월간 셀 탭은 이후 v82CalPickDay()가
       선택한 날짜/주로 다시 이동한다. */
    v82CalPickDay(tcalYmd(new Date()), "auto");
    setActive();
  }
  function closeCalScreen(){
    hideScreen("v82cal");
    setActive();
  }
  window.v82CalOpen = openCalScreen;
  window.v82CalClose = closeCalScreen;

  /* ---------- MOBILE INDICATOR DETAIL (2026-08-05) ----------
     캘린더 주간뷰 지표 행 탭에서 진입하는 새 지표 상세 화면(참고: Toss증권 앱 스크린샷).
     데스크톱 v83의 renderIndicatorDetailPage()/goIndicator()/closeIndicator()/
     INDICATOR_VIEW(전부 index.html)는 절대 건드리지 않는다 — 대신 그 옆의 순수
     데이터·문자열 함수만 그대로 재사용한다(사전 조사 결과):
       · INDICATORS/IND_CAT/IND_STR (index.html 전역 상수) — 그대로.
       · indHistAsc(ind)/indHistDate(dateStr)/indSvgChart(ind,IS) — DOM id를 전혀
         참조하지 않고 문자열만 반환하는 순수 함수라 포터블함을 확인, 그대로 호출.
       · v83CalAllRows() — 지표별 "다음 발표"(next, actual=null) 1건 + 과거 회차를
         이미 한 배열로 합쳐 주므로, 발표값 색 규칙(.tcal-hi=빨강/.tcal-lo=파랑, 예측
         대비 등락 — 데스크톱 tcalRowHtml()·모바일 v82CalRowHtml()과 동일 기준)까지
         그대로 물려받는다. 새로 만든 색 규칙이 아니라 기존 것 재사용.
       · v83IndicatorMatchedEvents()(데스크톱 "관련 글" = 같은 날짜에 흡수된 뉴스
         이벤트)는 용도가 달라(참고 이미지의 "함께 읽으면 좋은 글"은 흡수된 이벤트가
         아니라 주제 관련 기사 추천) 재사용하지 않았다 — 아래 v82IndRelatedArticles()가
         별도의 간단한 키워드 매칭이다. IND_EVENT_KEYWORDS(index.html, 이벤트 흡수용)는
         확장하지 않았다 — 거길 건드리면 데스크톱 캘린더의 이벤트 흡수 결과까지 바뀌어
         회귀 위험이 생긴다.
     화면은 #v82cal 위에 z-index만 높여 겹쳐서 연다(v82cal을 hideScreen하지 않음) —
     그래서 "캘린더 전체보기"는 이 화면만 닫으면 끝난다(아래 v82cal이 항상 그대로
     열려 있다). #v82detail(기사 상세, z13600)이 "함께 읽으면 좋은 글" 탭으로 이 위에
     또 열릴 수 있어 v82Pop()에 우선순위를 추가해 뒀다(위 window.v82Pop 참고). */
  var V82IND_ID = null;

  function v82IndStr(){ return (typeof IND_STR !== "undefined" && (IND_STR[LANG] || IND_STR.ko)) || {}; }
  function v82IndFind(id){
    if (typeof INDICATORS === "undefined") return null;
    for (var i = 0; i < INDICATORS.length; i++) if (INDICATORS[i].id === id) return INDICATORS[i];
    return null;
  }

  /* freq별 "지난달" 카드 라벨. rate8(FOMC·한국은행)은 "지난달"이 어색해 "직전 결정"으로
     조정했다(과제 지시 — 복잡하면 "지난달" 고정도 허용된다고 했지만 필드가 4종류뿐이라
     그대로 다 반영). */
  var V82IND_LASTLBL = {
    monthly: { ko: "지난달", en: "Last month", ja: "先月" },
    weekly: { ko: "지난주", en: "Last week", ja: "先週" },
    quarterly: { ko: "지난분기", en: "Last quarter", ja: "前四半期" },
    rate8: { ko: "직전 결정", en: "Previous decision", ja: "前回決定" }
  };
  function v82IndLastLabel(freq){
    var m = V82IND_LASTLBL[freq] || V82IND_LASTLBL.monthly;
    return m[LANG] || m.ko;
  }

  /* 발표일 옆 "(N월)" 표기 — 그 발표가 다루는 실제 데이터 기준월(참고 이미지: 8/5
     발표 옆에 "(7월)"). 월간·분기 지표는 대체로 발표 한 달 전이 기준월/기준분기라
     dateStr에서 1개월만 빼면 둘 다 맞는다(gdp 히스토리로 검산: 10/30 발표→9월→3분기 ✓,
     1/29 발표→12월→4분기 ✓). rate8(정책 결정일이라 "기준월" 개념이 없음)·weekly는 생략. */
  function v82IndPeriodLabel(freq, dateStr){
    if (freq !== "monthly" && freq !== "quarterly") return "";
    var d = new Date(dateStr + "T00:00:00");
    var pm = new Date(d.getFullYear(), d.getMonth() - 1, 1);
    if (freq === "quarterly"){
      var q = Math.floor(pm.getMonth() / 3) + 1;
      if (LANG === "ja") return "(" + q + "Q)";
      if (LANG === "en") return "(Q" + q + ")";
      return "(" + q + "분기)";
    }
    if (LANG === "ja") return "(" + (pm.getMonth() + 1) + "月)";
    if (LANG === "en") return "(" + pm.toLocaleDateString("en-US", { month: "short" }) + ")";
    return "(" + (pm.getMonth() + 1) + "월)";
  }

  /* ---- "✦ 예측 인사이트" 카드 문구 ----
     forecast(nextForecast)와 lastValue를 비교하고 goodDir(값이 높은 게 좋은 지표인지/
     낮은 게 좋은지/방향성 없음)로 분기하는 규칙 기반 템플릿이다. 실제 AI·전문가 호출이
     아니다 — 참고 이미지의 "전문가 예측이 나왔어요"는 우리가 진짜 전문가/AI가 아니라서
     그대로 베끼지 않았다(과제 지시). */
  var V82IND_INSIGHT_STR = {
    ko: {
      upUp: "예측치가 지난 값보다 높아요. 지표가 개선되는 방향이라 통상 경기 확장 신호로 해석돼요.",
      upDown: "예측치가 지난 값보다 낮아요. 지표가 둔화되는 방향이라 통상 경기 위축 신호로 해석될 수 있어요.",
      upFlat: "예측치가 지난 값과 비슷한 수준이에요. 뚜렷한 방향 전환 신호는 아직 없어요.",
      downUp: "예측치가 지난 값보다 높아요. 통상 부담 요인(지표 악화)으로 해석될 수 있어요.",
      downDown: "예측치가 지난 값보다 낮아요. 지표가 개선되는 방향이라 통상 긍정적으로 해석돼요.",
      downFlat: "예측치가 지난 값과 비슷한 수준이에요. 뚜렷한 방향 전환 신호는 아직 없어요.",
      neutralUp: "예측치가 지난 값보다 높아요. 인상 가능성을 반영한 예측이에요.",
      neutralDown: "예측치가 지난 값보다 낮아요. 인하 가능성을 반영한 예측이에요.",
      neutralFlat: "지난 결정과 같은 수준(동결)이 예상돼요."
    },
    en: {
      upUp: "The forecast is above the last reading, typically read as a sign of expansion.",
      upDown: "The forecast is below the last reading, typically read as a sign of slowing momentum.",
      upFlat: "The forecast is close to the last reading, with no clear shift in direction yet.",
      downUp: "The forecast is above the last reading, which can be read as a headwind.",
      downDown: "The forecast is below the last reading, typically read as improvement.",
      downFlat: "The forecast is close to the last reading, with no clear shift in direction yet.",
      neutralUp: "The forecast is above last time, pointing to a possible hike.",
      neutralDown: "The forecast is below last time, pointing to a possible cut.",
      neutralFlat: "Forecasts point to holding steady at the same level as last time."
    },
    ja: {
      upUp: "予測値は前回より高く、通常は景気拡大のサインと解釈されます。",
      upDown: "予測値は前回より低く、通常は景気減速のサインと解釈されることがあります。",
      upFlat: "予測値は前回とほぼ同水準で、明確な方向転換のサインはまだありません。",
      downUp: "予測値は前回より高く、負担要因(指標の悪化)と解釈されることがあります。",
      downDown: "予測値は前回より低く、通常は改善のサインと解釈されます。",
      downFlat: "予測値は前回とほぼ同水準で、明確な方向転換のサインはまだありません。",
      neutralUp: "予測値は前回より高く、引き上げの可能性を反映しています。",
      neutralDown: "予測値は前回より低く、引き下げの可能性を反映しています。",
      neutralFlat: "前回と同水準(据え置き)が予想されています。"
    }
  };
  function v82IndInsightText(ind){
    var f = ind.nextForecast, l = ind.lastValue;
    if (f === undefined || f === null || l === undefined || l === null) return "";
    var eps = 1e-9, diff = f - l;
    var dir = diff > eps ? "Up" : (diff < -eps ? "Down" : "Flat");
    var gd = ind.goodDir === "down" ? "down" : (ind.goodDir === "neutral" ? "neutral" : "up");
    var tbl = V82IND_INSIGHT_STR[LANG] || V82IND_INSIGHT_STR.ko;
    return tbl[gd + dir] || "";
  }

  /* ---- "함께 읽으면 좋은 글" ----
     ITEMS(기사)를 상대로 한 지표별 키워드 매칭 — 데스크톱의 "관련 글"
     (v83IndicatorMatchedEvents, EVENTS 흡수용)과는 별개다(위 섹션 설명 참고). 아주
     간단한 정규식 매칭이고, IND_EVENT_KEYWORDS(index.html)는 손대지 않았으므로 데스크톱
     이벤트 흡수 동작에는 영향이 없다. */
  var V82IND_ART_KW = {
    cpi: [/\bCPI\b/i, /소비자물가/, /消費者物価/],
    coreCpi: [/근원\s*CPI/i, /core\s*cpi/i, /コアCPI/i],
    unrate: [/실업률/, /unemployment/i, /失業率/],
    nfp: [/비농업|고용지표|\bNFP\b/i, /nonfarm/i, /雇用者数/],
    claims: [/실업수당\s*청구/, /jobless\s*claims/i, /失業保険/],
    fomc: [/FOMC/i, /기준금리/, /rate\s*decision/i, /政策金利/],
    gdp: [/\bGDP\b/i, /성장률/, /成長率/],
    pce: [/\bPCE\b/i, /개인소비지출/, /個人消費支出/],
    corePce: [/근원\s*PCE/i, /core\s*pce/i, /コアPCE/i],
    ismPmi: [/\bISM\b/i, /\bPMI\b/i, /구매관리자/, /購買担当者/],
    umich: [/소비자심리/, /미시간/, /consumer\s*sentiment/i, /消費者信頼感/],
    newHomeSales: [/신규주택/, /주택\s*매매/, /new\s*home\s*sales/i, /新築住宅/],
    krCpi: [/한국\s*소비자물가|국내\s*물가/, /korea.{0,6}cpi/i],
    krRate: [/한국은행|기준금리/, /bank\s*of\s*korea/i, /韓国銀行/],
    krTrade: [/무역수지|수출입/, /trade\s*balance/i, /貿易収支/]
  };
  function v82IndRelatedArticles(ind, max){
    max = max || 2;
    var kws = V82IND_ART_KW[ind.id];
    if (!kws || !kws.length || typeof ITEMS === "undefined") return [];
    var hits = [];
    for (var i = 0; i < ITEMS.length; i++){
      var it = ITEMS[i];
      try {
        var hay = [
          it.title && (it.title.ko || it.title.en || it.title.ja),
          it.gist && (it.gist.ko || it.gist.en || it.gist.ja),
          it.why && (it.why.ko || it.why.en || it.why.ja),
          (it.tags || []).join(" ")
        ].filter(Boolean).join(" ");
        if (kws.some(function(re){ return re.test(hay); })) hits.push(it);
      } catch (e) {}
    }
    hits.sort(function(a, b){ return a.date < b.date ? 1 : (a.date > b.date ? -1 : 0); });
    return hits.slice(0, max);
  }
  function v82IndArticleRowHtml(it){
    var title = esc((it.title && (it.title[LANG] || it.title.en)) || "");
    var sub = esc((it.cover && it.cover.label) || it.source || "");
    return '<button type="button" class="v82ind-art-row" data-aid="' + esc(it.id) + '">'
      + '<span class="v82ind-art-txt"><span class="v82ind-art-title">' + title + '</span>'
      + (sub ? '<span class="v82ind-art-sub">' + sub + '</span>' : "") + '</span>'
      + '<span class="v82ind-art-arrow">›</span></button>';
  }

  /* ---- "다가오는 경제지표" — 현재 지표 제외(가능하면, 과제 지시), nextDate 오름차순
     상위 N개. 캘린더 주간뷰와 같은 원형 아이콘(v82CalIconHtml 재사용, 국기)+제목+시각
     스타일. ---- */
  function v82IndUpcoming(excludeId, max){
    max = max || 3;
    if (typeof INDICATORS === "undefined") return [];
    var todayStr = tcalYmd(new Date());
    return INDICATORS.filter(function(x){ return x.id !== excludeId && x.nextDate >= todayStr; })
      .sort(function(a, b){
        if (a.nextDate !== b.nextDate) return a.nextDate < b.nextDate ? -1 : 1;
        return (a.nextTime || "") < (b.nextTime || "") ? -1 : 1;
      })
      .slice(0, max);
  }
  function v82IndUpcomingRowHtml(ind, todayStr){
    var iconHtml = v82CalIconHtml({ isIndicator: true, ind: ind });
    var name = esc(ind.name[LANG] || ind.name.en);
    var timeLbl = v82CalTimeLabel(ind.nextTime);
    var isToday = ind.nextDate === todayStr;
    var badge = isToday ? ('<span class="v82cal-today-chip">' + esc(T().calToday) + '</span>') : "";
    return '<button type="button" class="v82ind-up-row" data-ind="' + esc(ind.id) + '">' + iconHtml
      + '<span class="v82ind-up-txt"><span class="v82ind-up-title">' + name + '</span>'
      + (timeLbl ? '<span class="v82ind-up-time">' + esc(timeLbl) + '</span>' : "") + '</span>' + badge
      + '</button>';
  }

  /* ---- 히스토리 표 한 행. r은 v83CalAllRows()가 만드는 지표 행 그대로
     ({isIndicator:true, ind, date, actual, forecast, prev[, isNext]}) — 발표값 색
     (.tcal-hi/.tcal-lo)도 캘린더 주간뷰(v82CalRowHtml)와 완전히 같은 기준(예측 대비
     ±1e-9 밖이면 색, 같으면 무색)으로 계산해 재사용한다. ---- */
  function v82IndHistRowHtml(ind, r){
    var unit = ind.unit || "";
    var hd = (typeof indHistDate === "function") ? indHistDate(r.date) : r.date;
    var period = v82IndPeriodLabel(ind.freq, r.date);
    var noActual = (r.actual === null || r.actual === undefined);
    var actualTxt = noActual ? "—" : (r.actual + unit);
    var forecastTxt = (r.forecast === null || r.forecast === undefined) ? "—" : (r.forecast + unit);
    var colorCls = "";
    if (!noActual && r.forecast !== null && r.forecast !== undefined){
      if (r.actual > r.forecast + 1e-9) colorCls = "tcal-hi";
      else if (r.actual < r.forecast - 1e-9) colorCls = "tcal-lo";
    }
    return '<tr><td>' + esc(hd) + (period ? ' <span class="v82ind-hist-period">' + esc(period) + '</span>' : "") + '</td>'
      + '<td class="v82ind-hist-val ' + colorCls + '">' + esc(actualTxt) + '</td>'
      + '<td class="v82ind-hist-val v82ind-hist-muted">' + esc(forecastTxt) + '</td></tr>';
  }

  function v82IndBodyHtml(ind){
    var IS = v82IndStr();
    var name = ind.name[LANG] || ind.name.en;
    var catLbl = (IND_CAT[ind.cat] || {})[LANG] || (IND_CAT[ind.cat] || {}).en || "";
    var unit = ind.unit || "";
    var nd = new Date(ind.nextDate + "T00:00:00");
    var dateLbl = nd.toLocaleDateString(calLocale(), { month: "long", day: "numeric", weekday: "short" });
    var timeLbl = v82CalTimeLabel(ind.nextTime);
    var forecastLbl = (typeof TCAL_STR !== "undefined" && (TCAL_STR[LANG] || TCAL_STR.ko).colForecast) || "Forecast";

    var html = "";
    html += '<div class="v82ind-cat"><span class="chip">' + esc(catLbl) + '</span></div>';
    html += '<div class="v82ind-title">' + esc(name) + '</div>';
    var sub;
    if (LANG === "en") sub = dateLbl + (timeLbl ? " · Releases " + timeLbl : "");
    else if (LANG === "ja") sub = dateLbl + (timeLbl ? " · " + timeLbl + " 発表" : "");
    else sub = dateLbl + (timeLbl ? " · " + timeLbl + " 발표" : "");
    html += '<div class="v82ind-sub">' + esc(sub) + '</div>';

    html += '<div class="v82ind-cards">'
      + '<div class="v82ind-card"><div class="v82ind-card-l">' + esc(forecastLbl) + '</div><div class="v82ind-card-v">'
      + ((ind.nextForecast === undefined || ind.nextForecast === null) ? "—" : (ind.nextForecast + unit)) + '</div></div>'
      + '<div class="v82ind-card"><div class="v82ind-card-l">' + esc(v82IndLastLabel(ind.freq)) + '</div><div class="v82ind-card-v">'
      + ((ind.lastValue === undefined || ind.lastValue === null) ? "—" : (ind.lastValue + unit)) + '</div></div>'
      + '</div>';

    if (typeof indSvgChart === "function"){
      html += '<div class="v82ind-chart-card">' + indSvgChart(ind, IS) + '</div>';
    }

    var insight = v82IndInsightText(ind);
    if (insight){
      var insightTitle = LANG === "en" ? "Forecast insight" : (LANG === "ja" ? "予測インサイト" : "예측 인사이트");
      html += '<div class="v82ind-insight"><div class="v82ind-insight-h">✦ ' + esc(insightTitle) + '</div>'
        + '<div class="v82ind-insight-b">' + esc(insight) + '</div></div>';
    }

    /* v83CalAllRows()가 만든 지표 행(다음 발표 1개 + 과거 회차) 중 이 지표 것만 뽑아
       최신순으로 정렬 — 캘린더 주간뷰와 완전히 같은 데이터 소스(재사용, 과제 지시 1-4). */
    var histRows = (typeof v83CalAllRows === "function" ? v83CalAllRows() : [])
      .filter(function(r){ return r.isIndicator && r.ind && r.ind.id === ind.id; })
      .sort(function(a, b){ return a.date < b.date ? 1 : (a.date > b.date ? -1 : 0); });
    if (histRows.length){
      var headDate = LANG === "en" ? "Date" : (LANG === "ja" ? "発表日" : "발표 날짜");
      var headActual = LANG === "en" ? "Actual" : (LANG === "ja" ? "実績" : "발표");
      html += '<div class="v82ind-hist"><table class="v82ind-hist-table"><thead><tr><th>' + esc(headDate)
        + '</th><th>' + esc(headActual) + '</th><th>' + esc(forecastLbl) + '</th></tr></thead>';
      var head4 = histRows.slice(0, 4), rest = histRows.slice(4);
      html += '<tbody>' + head4.map(function(r){ return v82IndHistRowHtml(ind, r); }).join("") + '</tbody>';
      if (rest.length){
        html += '<tbody class="v82ind-hist-extra" hidden>' + rest.map(function(r){ return v82IndHistRowHtml(ind, r); }).join("") + '</tbody>';
      }
      html += '</table>';
      if (rest.length) html += '<button type="button" class="v82ind-more">' + esc(T().more) + '</button>';
      html += '</div>';
    }

    var desc = (ind.desc && (ind.desc[LANG] || ind.desc.ko)) || "";
    if (desc){
      html += '<div class="v82ind-desc"><div class="v82ind-sec-h">' + esc(name) + esc(IS.whatIs || "") + '</div>'
        + desc.split("\n\n").map(function(p){ return '<p class="v82ind-desc-p">' + esc(p) + '</p>'; }).join("")
        + '</div>';
    }

    var related = v82IndRelatedArticles(ind, 2);
    if (related.length){
      var relTitle = LANG === "en" ? "Worth reading" : (LANG === "ja" ? "一緒に読みたい記事" : "함께 읽으면 좋은 글");
      html += '<div class="v82ind-related"><div class="v82ind-sec-h">' + esc(relTitle) + '</div>'
        + related.map(v82IndArticleRowHtml).join("") + '</div>';
    }

    var todayStr = tcalYmd(new Date());
    var upcoming = v82IndUpcoming(ind.id, 3);
    if (upcoming.length){
      var upTitle = LANG === "en" ? "Upcoming indicators" : (LANG === "ja" ? "今後の経済指標" : "다가오는 경제지표");
      html += '<div class="v82ind-upcoming"><div class="v82ind-sec-h">' + esc(upTitle) + '</div>'
        + upcoming.map(function(x){ return v82IndUpcomingRowHtml(x, todayStr); }).join("") + '</div>';
    }

    var calLbl = LANG === "en" ? "Open full calendar" : (LANG === "ja" ? "カレンダーをすべて見る" : "캘린더 전체보기");
    html += '<button type="button" class="v82ind-cal-link">' + esc(calLbl) + ' ›</button>';

    var disclaimer = LANG === "en" ? "For reference only — not investment advice." : (LANG === "ja" ? "投資判断の参考情報です。実際の発表値と異なる場合があります。" : "투자 판단 참고용 정보이며 실제 발표치와 다를 수 있어요.");
    html += '<div class="v82ind-disclaimer">' + esc(disclaimer) + '</div>';

    return html;
  }

  function v82IndBuildScreen(){
    if ($("v82ind")) return;
    var s = document.createElement("div"); s.id = "v82ind"; s.className = "v82-screen v82ind-screen";
    s.innerHTML = '<div class="v82ind-body" id="v82indBody"></div>';
    document.body.appendChild(s);
    var h = document.createElement("div"); h.className = "v82-sh v82ind-sh"; h.id = "v82ind-h";
    h.innerHTML = '<button class="bk" aria-label="back">←</button><span class="ti"></span>';
    h.querySelector(".bk").onclick = function(){ v82IndClose(false); };
    document.body.appendChild(h);
  }

  function v82IndWireBody(){
    var body = $("v82indBody"); if (!body) return;
    var moreBtn = body.querySelector(".v82ind-more");
    if (moreBtn){
      moreBtn.onclick = function(){
        var extra = body.querySelector(".v82ind-hist-extra");
        if (extra) extra.hidden = false;
        moreBtn.remove();
      };
    }
    var upRows = body.querySelectorAll(".v82ind-up-row");
    for (var i = 0; i < upRows.length; i++){
      upRows[i].onclick = function(){ v82GoIndicator(this.dataset.ind); };
    }
    var artRows = body.querySelectorAll(".v82ind-art-row");
    for (var j = 0; j < artRows.length; j++){
      artRows[j].onclick = function(){ v82IndOpenArticle(this.dataset.aid); };
    }
    var calLink = body.querySelector(".v82ind-cal-link");
    if (calLink) calLink.onclick = function(){ v82IndClose(false); };
  }

  function v82IndRenderBody(){
    var body = $("v82indBody"); if (!body) return;
    var ind = v82IndFind(V82IND_ID);
    if (!ind){ body.innerHTML = ""; return; }
    body.innerHTML = v82IndBodyHtml(ind);
    v82IndWireBody();
  }

  /* 캘린더 지표 행(v82CalRowHtml, 위 onclick) 탭 + 상세 안 "다가오는 경제지표" 항목
     탭이 함께 쓰는 진입점. 이미 열려 있을 때(다른 지표로 갈아탈 때)는 pushView()를
     또 하지 않는다 — 데스크톱 goIndicator()의 "!wasOpen일 때만 push" 규칙과 동일한
     이유(관련 지표를 여러 번 옮겨 다녀도 뒤로가기 한 번이면 캘린더로 바로 돌아간다). */
  function v82GoIndicator(id){
    if (!mq.matches) return;
    if (!v82IndFind(id)) return;
    v82IndBuildScreen();
    V82IND_ID = id;
    v82IndRenderBody();
    var scr = $("v82ind");
    if (scr && scr.classList.contains("on")){
      scr.scrollTop = 0;
    } else {
      showScreen("v82ind");
    }
    setActive();
    if (typeof track === "function") track("indicator/" + id);
  }
  function v82IndClose(fromPop){
    if (!hideScreen("v82ind")) return false;
    if (!fromPop) silentBack();
    setActive();
    return true;
  }
  /* 관련 글 탭: v82notif/v82list의 기존 "행 탭 → 이 화면 닫고 기사 열기" 패턴
     (예: closeNotif(true); silentBack(); openCardById(r.id);)을 그대로 따른다.
     v82cal은 열어 둔 채로 둔다(다른 화면들과 동일하게 자기 자신만 정리) — 기사에서
     뒤로가면 v82detail이 먼저 닫히고(위 v82Pop 참고) 캘린더가 다시 보인다. */
  function v82IndOpenArticle(id){
    v82IndClose(true);
    silentBack();
    if (typeof openCardById === "function") openCardById(id);
  }
  window.v82GoIndicator = v82GoIndicator;
  window.v82IndClose = v82IndClose;

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
    /* Keyboard handling, third attempt - do NOT move the bar at all. Both the
       translateY lift (2026-07-29: gap above the keyboard) and the measured-delta
       version of it (2026-07-30 video: the whole bar vanished the moment the
       keyboard opened) broke on the real device, because iOS re-anchors and pans
       fixed-position chrome in ways that make any transform math lie.
       The pattern X itself uses instead: while our composer is focused and a
       keyboard is up, cancel the document pan and SHRINK THE DETAIL CONTAINER to
       the visual viewport height. bottom:0 then IS the keyboard top - nothing is
       transformed, so there is nothing to mis-measure. kb==0 (no keyboard, or a
       WebKit that already resizes the layout viewport) leaves everything alone. */
    var vv = window.visualViewport;
    var dt = $("v82detail");
    if (vv && dt) {
      var kb = Math.max(0, Math.round(window.innerHeight - vv.height));
      var ae = document.activeElement;
      if (kb > 60 && ae && bar.contains(ae)) {
        if (vv.offsetTop || window.scrollY) { try { window.scrollTo(0, 0); } catch (e) {} }
        dt.style.height = Math.round(vv.height) + "px";
      } else if (kb <= 60) {
        dt.style.height = "";
      }
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
    var dt = $("v82detail");
    if (dt) dt.style.height = "";
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
      /* build_data already marks long summaries with gclip/item.clip. Reuse
         that state instead of reading scrollHeight after DOM writes; the old
         measurement forced a synchronous reflow for every mobile card. */
      var gi = c.querySelector(".gist");
      if (gi && !c.classList.contains("v82expanded")) c.classList.toggle("v82clip", !!(it && it.clip) || c.classList.contains("gclip"));
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
    /* 2026-08-05: 지표 상세(#v82ind)는 캘린더(#v82cal) 위에 겹쳐 열리므로, 안쪽(위)
       레이어부터 닫는다 — 순서를 바꾸면 v82cal만 닫히고 v82ind가 화면을 계속 덮는다. */
    try { var vi=$("v82ind"); if(vi && vi.classList.contains("on") && typeof v82IndClose==="function"){ v82IndClose(false); } } catch(e){}
    try { var vc=$("v82cal"); if(vc && vc.classList.contains("on") && typeof closeCal==="function"){ closeCal(); silentBack(); } } catch(e){}
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
    try { var vcal=$("v82cal"); if (vcal && vcal.classList.contains("on")) cur = "cal"; } catch(e){}
    var bs = nav.querySelectorAll("button");
    for (var i = 0; i < bs.length; i++) bs[i].classList.toggle("on", bs[i].dataset.v === cur);
    refreshNav();
  }

  /* ---------- back handling ---------- */
  window.v82Pop = function(){
    if (SILENT){ SILENT = false; return true; }
    if (!mq.matches) return false;
    var cfs = $("chartFS"); if (cfs && !cfs.hidden) return false;
    /* 2026-08-05: 지표 상세(#v82ind, z45)는 캘린더(#v82cal, z40) 위에 겹쳐서 열리고,
       기사 상세(#v82detail, z13600)는 지표 상세의 "함께 읽으면 좋은 글"에서 그 위에
       또 열릴 수 있다 — 안쪽(가장 위) 레이어부터 닫아야 한다. 아래 vcal 체크가 먼저
       걸리면(원래 순서) 기사·지표 상세가 떠 있는 채로 캘린더만 조용히 닫혀 버튼 한
       번이 "허공에" 소비된다. closeDetail(true) 체크는 원래도 있었지만(현재 위치
       그대로 둠) vcal보다 뒤에 있어 이 두 레이어와 v82cal이 동시에 열린 상태에서는
       늦게 걸렸다 — 그 상태를 처음 만드는 게 이번 지표 상세 기능이라 여기서 먼저
       가로챈다. */
    var dtOv = $("v82detail");
    if (dtOv && dtOv.classList.contains("on")){ if (typeof closeDetail === "function" && closeDetail(true)) return true; }
    var vind = $("v82ind"); if (vind && vind.classList.contains("on")){ if (typeof v82IndClose === "function") v82IndClose(true); return true; }
    /* 새 주간뷰 캘린더(.v82-screen #v82cal)는 다른 셸 화면과 같은 방식으로 닫는다. */
    var vcal = $("v82cal"); if (vcal && vcal.classList.contains("on")){ hideScreen("v82cal"); setActive(); return true; }
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
      if (g && !c.classList.contains("v82expanded")) {
        var it = itemOf(c);
        c.classList.toggle("v82clip", !!(it && it.clip) || c.classList.contains("gclip"));
      }
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
      hideScreen("v82ind"); /* 2026-08-05: 지표 상세도 데스크톱 폭 전환 시 정리(캘린더 v82cal 자체는 기존에도 여기서 정리 대상이 아니었음 — 그 관례는 건드리지 않는다) */
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
