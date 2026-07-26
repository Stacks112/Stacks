/* v83 desktop: notification settings panel (reads/writes the same stk_notif
   store as the mobile drawer, so preferences stay in sync across layouts). */
(function(){
"use strict";
/* --- weekly-email (newsletter) receive-language setting ---
   Shared by the desktop notification-settings modal (v83AlertsPanel) and the
   mobile notifications screen (notifSettingsHtml). No accounts: the D1 list
   is keyed by email, so changing the language is just an upsert through the
   same worker /subscribe route the signup form uses. The last email/language
   saved on this device are remembered for prefill. */
var STK_NL_S = {
  ko: { h:"주간 베스트 이메일", d:"매주 일요일 '이번 주 베스트' 메일을 받을 언어예요. 구독한 이메일을 입력하고 저장하면 수신 언어가 바뀌어요. 처음 입력하는 이메일이면 새로 구독돼요.",
        ph:"이메일 주소", save:"저장", saving:"저장 중…", saved:"저장됐어요! 선택한 언어로 발송돼요.",
        err:"문제가 생겼어요. 잠시 후 다시 시도해 주세요.", bad:"이메일 주소를 확인해 주세요.",
        lko:"한국어", len:"English", lja:"日本語" },
  en: { h:"Weekly email", d:"The language of your Sunday weekly-best email. Enter the email you subscribed with and save to change it. A new email subscribes fresh.",
        ph:"Email address", save:"Save", saving:"Saving…", saved:"Saved! Your weekly email will arrive in this language.",
        err:"Something went wrong. Please try again.", bad:"Please enter a valid email address.",
        lko:"한국어", len:"English", lja:"日本語" },
  ja: { h:"週間ベストメール", d:"毎週日曜『今週のベスト』メールの受信言語です。購読中のメールアドレスを入力して保存すると変更されます。新しいアドレスなら新規購読になります。",
        ph:"メールアドレス", save:"保存", saving:"保存中…", saved:"保存しました！選択した言語でお届けします。",
        err:"エラーが発生しました。もう一度お試しください。", bad:"メールアドレスを確認してください。",
        lko:"한국어", len:"English", lja:"日本語" }
};
function stkNlT(){ return STK_NL_S[(typeof LANG !== "undefined" && STK_NL_S[LANG]) ? LANG : "ko"]; }
window.stkNlHtml = function(){
  var t = stkNlT(), em = "", lg = (typeof LANG !== "undefined") ? LANG : "ko";
  try { em = store.get("stk_nl_email", "") || ""; lg = store.get("stk_nl_lang", null) || lg; } catch (e){}
  var chip = function(code, label){ return '<button type="button" data-nll="'+code+'" class="'+(lg===code?"on":"")+'">'+label+'</button>'; };
  return '<div class="stk-nl-set">'
    + '<div class="stk-nl-h">'+t.h+'</div>'
    + '<div class="stk-nl-d">'+t.d+'</div>'
    + '<input type="email" data-nle placeholder="'+t.ph+'" value="'+em.replace(/"/g,"&quot;")+'">'
    + '<div class="stk-nl-langs">'+chip("ko",t.lko)+chip("en",t.len)+chip("ja",t.lja)+'</div>'
    + '<button type="button" class="stk-nl-save" data-nlsave>'+t.save+'</button>'
    + '<div class="stk-nl-msg" data-nlmsg hidden></div>'
    + '</div>';
};
window.stkNlWire = function(root){
  var box = root.querySelector(".stk-nl-set"); if (!box) return;
  var t = stkNlT();
  var input = box.querySelector("[data-nle]"), msg = box.querySelector("[data-nlmsg]");
  var lang = null;
  try { lang = store.get("stk_nl_lang", null); } catch (e){}
  if (!lang) lang = (typeof LANG !== "undefined") ? LANG : "ko";
  box.querySelectorAll("[data-nll]").forEach(function(b){
    b.addEventListener("click", function(){
      lang = b.getAttribute("data-nll");
      box.querySelectorAll("[data-nll]").forEach(function(x){ x.classList.toggle("on", x === b); });
    });
  });
  box.querySelector("[data-nlsave]").addEventListener("click", function(){
    var email = (input.value || "").trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ msg.hidden = false; msg.className = "stk-nl-msg err"; msg.textContent = t.bad; return; }
    msg.hidden = false; msg.className = "stk-nl-msg"; msg.textContent = t.saving;
    fetch(SUBSCRIBE_URL, { method:"POST", headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ email: email, lang: lang }) })
      .then(function(r){ return r.json().catch(function(){ return {}; }).then(function(j){ return (r.ok && j.ok) ? (j.status || "subscribed") : null; }); })
      .then(function(ok){
        if (ok){
          /* an address the list has never confirmed comes back "pending" */
          var PEND = { ko:"확인 메일을 보냈어요. 메일함에서 버튼을 눌러 구독을 완료해 주세요.",
                       en:"Check your inbox. Click the button in the confirmation email to finish.",
                       ja:"確認メールを送りました。メール内のボタンを押して購読を完了してください。" };
          var L = (typeof LANG !== "undefined" && PEND[LANG]) ? LANG : "ko";
          msg.className = "stk-nl-msg"; msg.textContent = (ok === "pending") ? PEND[L] : t.saved;
          try { store.set("stk_nl_email", email); store.set("stk_nl_lang", lang); } catch (e){}
          try { track("newsletter/lang-change"); } catch (e){}
        } else { msg.className = "stk-nl-msg err"; msg.textContent = t.err; }
      })
      .catch(function(){ msg.className = "stk-nl-msg err"; msg.textContent = t.err; });
  });
};

var NPS = {
  ko: { title:"알림 설정", newpost:"새 글 알림", debate:"오늘의 토론 알림",
        follow:"팔로우 새 글 알림", events:"이벤트 알림", push:"브라우저 푸시 알림 켜기",
        pushOn:"브라우저 푸시 알림 켜짐 ✓", pushBlocked:"브라우저에서 알림이 차단돼 있어요. 주소창의 사이트 설정에서 허용해 주세요." },
  en: { title:"Notification settings", newpost:"New posts", debate:"Today's debate",
        follow:"New posts from who you follow", events:"Event alerts", push:"Enable browser push",
        pushOn:"Browser push is on ✓", pushBlocked:"Notifications are blocked by the browser. Allow them in the site settings." },
  ja: { title:"通知設定", newpost:"新着記事", debate:"今日の論点",
        follow:"フォロー中の新着", events:"イベント通知", push:"ブラウザ通知をオンにする",
        pushOn:"ブラウザ通知はオン ✓", pushBlocked:"ブラウザで通知がブロックされています。サイト設定で許可してください。" }
};
function npT(){ return NPS[(typeof LANG !== "undefined" && NPS[LANG]) ? LANG : "ko"]; }
function npGet(){
  var d = { newpost:true, debate:true, follow:true, eventsMaster:true };
  try {
    var s = store.get("stk_notif", null);
    if (s && typeof s === "object"){
      d.newpost = s.newpost !== false; d.debate = s.debate !== false;
      d.follow = s.follow !== false; d.eventsMaster = s.eventsMaster !== false;
    }
  } catch (e){}
  return d;
}
function npSet(key, on){
  try {
    var p = store.get("stk_notif", {}) || {};
    p[key] = on;
    store.set("stk_notif", p);
  } catch (e){}
}
window.v83AlertsPanel = function(){
  var old = document.getElementById("v83npOv");
  if (old){ old.remove(); return; }
  var t = npT(), p = npGet();
  var ov = document.createElement("div");
  ov.id = "v83npOv"; ov.className = "v83np-ov";
  var row = function(key, label, on){
    return '<button class="v83np-row" data-np="' + key + '"><span>' + label
      + '</span><span class="v83np-sw' + (on ? " on" : "") + '"></span></button>';
  };
  ov.innerHTML = '<div class="v83np">'
    + '<h3>' + t.title + '<button aria-label="close">&#x2715;</button></h3>'
    /* 2026-07-25 (june): 데스크톱엔 알림 "목록"이 없고 설정만 있었다. 목록을 위에 얹는다. */
    + (typeof window.v83NotifListHtml === "function" ? window.v83NotifListHtml() : "")
    + row("newpost", t.newpost, p.newpost)
    + row("debate", t.debate, p.debate)
    + row("follow", t.follow, p.follow)
    + row("eventsMaster", t.events, p.eventsMaster)
    + '<button class="v83np-push">' + t.push + '</button>'
    + '<div class="v83np-blocked" hidden></div>'
    + (window.stkNlHtml ? window.stkNlHtml() : '')
    + '</div>';
  document.body.appendChild(ov);
  if (typeof window.v83NotifBind === "function") window.v83NotifBind(ov);
  ov.addEventListener("click", function(e){ if (e.target === ov) ov.remove(); });
  ov.querySelector("h3 button").addEventListener("click", function(){ ov.remove(); });
  ov.querySelectorAll("[data-np]").forEach(function(b){
    b.addEventListener("click", function(){
      var sw = b.querySelector(".v83np-sw");
      var on = !sw.classList.contains("on");
      sw.classList.toggle("on", on);
      npSet(b.getAttribute("data-np"), on);
    });
  });
  if (window.stkNlWire) window.stkNlWire(ov);
  var pushBtn = ov.querySelector(".v83np-push");
  var blockedNote = ov.querySelector(".v83np-blocked");
  var pushIsOn = false; /* last known subscription state */
  /* reflect the live push state on the button: white border + "켜짐 ✓" when on,
     a small note when the browser has blocked notifications. */
  function apply(opted){
    var perm = (typeof Notification !== "undefined") ? Notification.permission : "default";
    pushIsOn = (perm === "granted" && opted);
    if (pushIsOn){
      pushBtn.classList.add("on"); pushBtn.textContent = t.pushOn;
      if (blockedNote){ blockedNote.hidden = true; }
    } else if (perm === "denied"){
      pushBtn.classList.remove("on"); pushBtn.textContent = t.push;
      if (blockedNote){ blockedNote.hidden = false; blockedNote.textContent = t.pushBlocked; }
    } else {
      pushBtn.classList.remove("on"); pushBtn.textContent = t.push;
      if (blockedNote){ blockedNote.hidden = true; }
    }
  }
  function reflectPush(){
    try {
      var perm = (typeof Notification !== "undefined") ? Notification.permission : "default";
      if (window.OneSignalDeferred && perm === "granted"){
        var resolved = false;
        window.OneSignalDeferred.push(function(os2){
          var opted = false;
          try { opted = !!(os2.User && os2.User.PushSubscription && os2.User.PushSubscription.optedIn); } catch (e){}
          resolved = true; apply(opted);
        });
        /* only guess "on" if the SDK never answered — never override a real opt-out */
        setTimeout(function(){ if (!resolved) apply(true); }, 1500);
      } else {
        apply(false);
      }
    } catch (e){}
  }
  reflectPush();
  pushBtn.addEventListener("click", function(){
    if (pushIsOn){
      /* turn OFF: opt out of push (keeps browser permission, drops subscription) */
      pushBtn.classList.remove("on"); pushBtn.textContent = t.push;
      pushIsOn = false;
      if (window.OneSignalDeferred){
        window.OneSignalDeferred.push(function(os2){
          try {
            if (os2.User && os2.User.PushSubscription && os2.User.PushSubscription.optOut) os2.User.PushSubscription.optOut();
          } catch (e){}
        });
      }
      setTimeout(reflectPush, 1500);
      return;
    }
    /* turn ON: delegate to the (hidden) top-bar push button — it owns the
       OneSignal opt-in prompt + blocked-permission feedback */
    var nb = document.getElementById("notifBtn");
    if (nb && typeof nb.onclick === "function") nb.onclick();
    setTimeout(reflectPush, 1500);
  });
};

/* ---- 최신/팔로잉 tabs: match the center column's width exactly (X-style) ---- */
function alignFsw(){
  try {
    var f = document.getElementById("v83fsw");
    var c = document.getElementById("v83center");
    if (!f || !c || !f.parentElement || !document.documentElement.classList.contains("v83")) return;
    var cr = c.getBoundingClientRect(), nr = f.parentElement.getBoundingClientRect();
    if (!cr.width) return;
    f.style.left = (cr.left - nr.left) + "px";
    f.style.width = cr.width + "px";
    f.style.transform = "none";
  } catch (e){}
}
window.addEventListener("resize", alignFsw);
(function retryAlign(n){
  alignFsw();
  if (n > 0) setTimeout(function(){ retryAlign(n - 1); }, 400);
})(12);
try {
  new MutationObserver(alignFsw)
    .observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
} catch (e){}

/* ---- search dropdown: recent searches / guide + today's popular (3) ---- */
var SDS = {
  ko: { recent:"최근 검색", clear:"모두 지우기", trend:"오늘의 인기",
        guide:"사람, 기업, 키워드로 검색해보세요", posts:"글 {n}개" },
  en: { recent:"Recent", clear:"Clear all", trend:"Popular today",
        guide:"Try searching for people, companies, or keywords", posts:"{n} posts" },
  ja: { recent:"最近の検索", clear:"すべて消去", trend:"今日の人気",
        guide:"人物、企業、キーワードで検索してみましょう", posts:"{n}件" }
};
function sdT(){ return SDS[(typeof LANG !== "undefined" && SDS[LANG]) ? LANG : "ko"]; }
function sdRecent(){ try { var r = store.get("stk_recent_q", []); return Array.isArray(r) ? r : []; } catch(e){ return []; } }
function sdSaveRecent(q){
  q = String(q || "").trim(); if (!q) return;
  var r = sdRecent().filter(function(x){ return x !== q; });
  r.unshift(q);
  try { store.set("stk_recent_q", r.slice(0, 8)); } catch(e){}
}
function sdTrend3(){
  var out = [];
  try {
    var cnt = {};
    var items = (typeof ITEMS !== "undefined" ? ITEMS : []).slice(0, 20);
    items.forEach(function(it){
      (it.tags || []).forEach(function(t){ cnt[t] = (cnt[t] || 0) + 1; });
      var src = (typeof dispName === "function") ? dispName(it.source) : it.source;
      if (src) cnt[src] = (cnt[src] || 0) + 1;
    });
    out = Object.keys(cnt).map(function(k){ return { label: k, n: cnt[k] }; })
      .filter(function(o){ return o.n >= 2; })
      .sort(function(a, b){ return b.n - a.n; })
      .slice(0, 3);
  } catch(e){}
  return out;
}
function sdEsc(s){ return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }
function sdApply(q){
  var wrap = document.querySelector(".v83-search");
  var inp = wrap ? wrap.querySelector("input") : null;
  if (inp){
    inp.value = q;
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  }
  sdSaveRecent(q);
  sdHide();
}
function sdHide(){ var d = document.getElementById("v83sd"); if (d) d.remove(); }
function sdShow(){
  var wrap = document.querySelector(".v83-search");
  if (!wrap) return;
  sdHide();
  var t = sdT(), rec = sdRecent(), tr = sdTrend3();
  var h = "";
  if (rec.length){
    h += '<div class="v83sd-h">' + t.recent + '<button data-sdclear>' + t.clear + "</button></div>";
    rec.slice(0, 6).forEach(function(q, i){
      h += '<button class="v83sd-row" data-sdq="' + sdEsc(q) + '"><span class="ic">&#128336;</span>'
        + '<span class="lb">' + sdEsc(q) + '</span><span class="rm" data-sdrm="' + i + '">&#x2715;</span></button>';
    });
  } else {
    h += '<div class="v83sd-guide">' + t.guide + "</div>";
  }
  if (tr.length){
    h += '<div class="v83sd-div"></div><div class="v83sd-h">' + t.trend + "</div>";
    tr.forEach(function(o){
      h += '<button class="v83sd-row" data-sdq="' + sdEsc(o.label) + '"><span class="ic">&#128293;</span>'
        + '<span class="lb">' + sdEsc(o.label) + '</span>'
        + '<span class="sub">' + t.posts.replace("{n}", o.n) + "</span></button>";
    });
  }
  var d = document.createElement("div");
  d.id = "v83sd"; d.className = "v83sd";
  d.innerHTML = h;
  wrap.appendChild(d);
  d.querySelectorAll("[data-sdq]").forEach(function(b){
    b.addEventListener("click", function(e){
      var rm = e.target.closest("[data-sdrm]");
      if (rm){
        e.stopPropagation();
        var r = sdRecent(); r.splice(parseInt(rm.getAttribute("data-sdrm"), 10), 1);
        try { store.set("stk_recent_q", r); } catch(err){}
        sdShow();
        return;
      }
      sdApply(b.getAttribute("data-sdq"));
    });
  });
  var cl = d.querySelector("[data-sdclear]");
  if (cl) cl.addEventListener("click", function(){
    try { store.set("stk_recent_q", []); } catch(e){}
    sdShow();
  });
}
document.addEventListener("focusin", function(e){
  if (e.target && e.target.matches && e.target.matches(".v83-search input")) sdShow();
});
document.addEventListener("click", function(e){
  if (!e.target.closest || !e.target.closest(".v83-search")) sdHide();
});
document.addEventListener("keydown", function(e){
  if (e.key === "Enter" && e.target && e.target.matches && e.target.matches(".v83-search input")){
    sdSaveRecent(e.target.value);
    sdHide();
  }
  if (e.key === "Escape") sdHide();
});

/* ==== 읽음 하이브리드 → 라운드11 개편 (2026-07-23 june 결정) ==================
   - ✓ 수동 읽음 버튼 폐지 (CSS로 숨김). 트위터처럼 스크롤로 지나친 글이 곧 '본 글'.
   - 스크롤로 카드를 완전히 지나치면 stk_seen_pending에 기록만 하고,
     다음 방문 시작 시 READ로 합류 → 하단 '이미 읽은 글' 그룹으로 강등.
     (이번 세션 화면은 절대 건드리지 않음: 스크롤 중 카드가 접히거나 움직이지 않게)
   - READ_BASE: 세션 시작 시점의 읽음 스냅샷 (코어 강등 파티션이 참조 —
     이번 세션에 열어본 글은 제자리 유지, 다음 방문부터 하단으로) */
var SEEN_PEND = (function(){ try { return new Set(JSON.parse(localStorage.getItem("stk_seen_pending") || "[]")); } catch (e){ return new Set(); } })();
function seenSave(){ try { localStorage.setItem("stk_seen_pending", JSON.stringify(Array.from(SEEN_PEND))); } catch (e){} }
/* 지난 방문에 스크롤로 지나친 글 합류 (READ_BASE 스냅샷 전에!) */
try {
  if (SEEN_PEND.size && typeof READ !== "undefined"){
    var _sn = 0;
    SEEN_PEND.forEach(function(id){
      if (!READ.has(id)){ READ.add(id); _sn++; try { if (typeof logRead === "function") logRead(id); } catch (e){} }
    });
    if (_sn) store.set("stk_read", Array.from(READ));
    SEEN_PEND = new Set(); seenSave();
  }
} catch (e){}
window.READ_BASE = new Set(typeof READ !== "undefined" ? READ : []);
window.READ_SWEPT = new Set();

/* 스크롤 추적: 일반 피드(최신/팔로잉)에서만, 카드 하단이 화면 위로 40px 이상
   지나가면 '본 글' 후보로 기록. rAF 대신 setTimeout (백그라운드 탭 함정 회피) */
var seenTick = null;
window.addEventListener("scroll", function(){
  if (seenTick) return;
  seenTick = setTimeout(function(){
    seenTick = null;
    try {
      if (typeof V83ITEM !== "undefined" && V83ITEM) return;
      if (typeof QUERY !== "undefined" && QUERY) return;
      if (typeof ENTITY_VIEW !== "undefined" && ENTITY_VIEW) return;
      if (typeof SERIES_VIEW !== "undefined" && SERIES_VIEW) return;
      if (typeof THEME_VIEW !== "undefined" && THEME_VIEW) return;
      if (typeof SB_VIEW !== "undefined" && SB_VIEW) return;
      if (typeof READ_VIEW !== "undefined" && READ_VIEW) return;
      if (typeof BM_ONLY !== "undefined" && BM_ONLY) return;
      if (typeof UNREAD_ONLY !== "undefined" && UNREAD_ONLY) return;
      if (typeof EVENT_FILTER !== "undefined" && EVENT_FILTER) return;
      var dirty = false;
      document.querySelectorAll('#feedList > .card[id^="sig-"]').forEach(function(c){
        if (c.getBoundingClientRect().bottom < -40){
          var id = c.id.slice(4);
          if (typeof READ !== "undefined" && READ.has(id)) return;
          if (!SEEN_PEND.has(id)){ SEEN_PEND.add(id); dirty = true; }
        }
      });
      if (dirty) seenSave();
    } catch (e){}
  }, 350);
}, { passive: true });

/* ==== 라운드11: 북마크 비행 애니메이션 (읽음 애니메이션에서 이관) ============
   북마크 버튼 클릭 → 버튼 자리에서 🔖 칩이 톡 등장 → 좌측 '북마크' 메뉴로
   슝~ 날아가 아이콘 속으로 쏙 들어가고 → 메뉴가 반짝 */
function bmFly(fromEl){
  try {
    if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var target = document.querySelector('#v83nav .v83-link[data-k="bm"]');
    if (!target || !fromEl) return;
    var r1 = fromEl.getBoundingClientRect(), r2 = target.getBoundingClientRect();
    var cx = r1.left + r1.width / 2, cy = Math.max(60, Math.min(r1.top + r1.height / 2, window.innerHeight - 60));
    /* 타깃은 메뉴의 아이콘(첫 svg) 중심 — '북마크 모양까지 들어가게' */
    var ticon = target.querySelector("svg") || target;
    var rt = ticon.getBoundingClientRect();
    var tx = rt.left + rt.width / 2, ty = rt.top + rt.height / 2;
    /* 1) 버튼 자리에서 🔖 칩 등장 */
    var chip = document.createElement("div");
    chip.className = "rh-chip bm-chip";
    chip.textContent = "🔖";
    chip.style.left = cx + "px";
    chip.style.top = cy + "px";
    document.body.appendChild(chip);
    setTimeout(function(){
      chip.style.transform = "translate(-50%,-50%) scale(1)";
      chip.style.opacity = "1";
    }, 30);
    /* 2) 북마크 아이콘까지 슝~ (끝까지 잘 보이게 날아간 뒤) */
    setTimeout(function(){
      chip.style.transition = "transform .6s cubic-bezier(.45,-0.05,.55,.5)";
      chip.style.transform = "translate(calc(-50% + " + (tx - cx) + "px), calc(-50% + " + (ty - cy) + "px)) scale(.55) rotate(-10deg)";
    }, 300);
    /* 3) 도착하면 아이콘 속으로 쏙 (여기서만 축소·페이드) */
    setTimeout(function(){
      chip.style.transition = "transform .22s ease-in, opacity .22s ease-in";
      chip.style.transform = "translate(calc(-50% + " + (tx - cx) + "px), calc(-50% + " + (ty - cy) + "px)) scale(.1)";
      chip.style.opacity = "0";
    }, 910);
    setTimeout(function(){ chip.remove(); }, 1180);
    /* 4) 메뉴가 받으면서 반짝 */
    setTimeout(function(){
      target.classList.add("v83-read-pulse");
      setTimeout(function(){ target.classList.remove("v83-read-pulse"); }, 750);
    }, 930);
  } catch (e){}
}

/* 북마크 오버라이드: 추가할 때만 비행 (해제는 조용히) */
if (typeof toggleBookmark === "function"){
  var _origToggleBookmark = toggleBookmark;
  window.toggleBookmark = function(id){
    var adding = !(typeof BM !== "undefined" && BM.has(id));
    _origToggleBookmark(id);
    if (adding){
      var from = document.getElementById("bm-" + id) || document.getElementById("sig-" + id);
      if (from) bmFly(from);
    }
  };
}

/* ==== 라운드9: 상대 시간 표기 (ts 있으면 정확, 없으면 클라 first-seen 근사) ==== */
var FIRST_SEEN = (function(){ try { return JSON.parse(localStorage.getItem("stk_first_seen") || "{}"); } catch(e){ return {}; } })();
function fsSave(){ try { localStorage.setItem("stk_first_seen", JSON.stringify(FIRST_SEEN)); } catch(e){} }
function isTodayISO(d){
  try {
    var t = new Date(); var y = t.getFullYear(), m = ("0"+(t.getMonth()+1)).slice(-2), dd = ("0"+t.getDate()).slice(-2);
    var today = y + "-" + m + "-" + dd;
    // also accept "yesterday" so items near a UTC/local date boundary still qualify
    var ty = new Date(t.getTime() - 86400000); var yd = ty.getFullYear()+"-"+("0"+(ty.getMonth()+1)).slice(-2)+"-"+("0"+ty.getDate()).slice(-2);
    return d === today || d === yd;
  } catch(e){ return false; }
}
window.relDate = function(item){
  var L = (typeof LANG !== "undefined") ? LANG : "ko";
  var W = ({ ko:{now:"방금",min:"분 전",hr:"시간 전"}, en:{now:"just now",min:"m ago",hr:"h ago"}, ja:{now:"たった今",min:"分前",hr:"時間前"} })[L] || { now:"방금",min:"분 전",hr:"시간 전" };
  var pub = null;
  if (item.ts){ var t = Date.parse(item.ts); if (isFinite(t)) pub = t; }
  if (pub == null && isTodayISO(item.date)){
    /* client first-seen: stamp today's items the first time this device shows them */
    if (!FIRST_SEEN[item.id]){ try { FIRST_SEEN[item.id] = Date.now(); fsSave(); } catch(e){} }
    pub = FIRST_SEEN[item.id];
  }
  if (pub != null){
    var diff = Date.now() - pub; if (diff < 0) diff = 0;
    var h = Math.floor(diff / 3600000);
    if (h < 24){
      if (diff < 60000) return W.now;
      if (diff < 3600000) return Math.floor(diff / 60000) + W.min;
      return h + W.hr;
    }
  }
  return (typeof fmt === "function") ? fmt(item.date) : String(item.date || "");
};

/* ==== 라운드9: 상세뷰 재배치(예측추적 아이콘·긍정부정 댓글 위) + 피드 핵심 클릭→상세 ==== */
function v83CardFix(card){
  var id = (card.id || "").replace(/^sig-/, "");
  if (card.classList.contains("v83one")){
    if (card.__v83fix) return; card.__v83fix = true;
    /* 라운드13: 긍정/부정(ask)을 댓글 영역 맨 아래(옛 '함께 읽기' 자리)로 이동 +
       "댓글로 의견" 제거. '함께 읽기'는 우측 패널로 빠졌다(v83RelatedRail). */
    var ask = card.querySelector(".ask-block");
    if (ask){
      var ac = ask.querySelector(".ask-comment"); if (ac) ac.remove();
      var body = card.querySelector(".card-body") || card;
      var cbox = card.querySelector(".comment-box");
      if (cbox && cbox.parentNode){
        if (cbox.nextSibling) cbox.parentNode.insertBefore(ask, cbox.nextSibling);
        else cbox.parentNode.appendChild(ask);
      } else {
        body.appendChild(ask);
      }
    }
    /* Item5: 예측 추적(oc)을 원문보기 옆 아이콘으로 접기 */
    var oc = card.querySelector(".oc");
    var cta = card.querySelector(".cta-row");
    if (oc && cta && !cta.querySelector(".oc-toggle")){
      oc.classList.add("oc-collap");
      if (cta.nextSibling) cta.parentNode.insertBefore(oc, cta.nextSibling);
      else cta.parentNode.appendChild(oc);
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "oc-toggle";
      btn.innerHTML = "🎯";   /* 아이콘만: 텍스트 라벨 제거, 클릭 시 접힌 예측 내용이 펼쳐짐 */
      btn.title = (oc.textContent || "").trim();
      btn.setAttribute("aria-label", (oc.textContent || "").trim() || "예측 추적");
      btn.addEventListener("click", function(e){
        e.stopPropagation();
        var open = oc.classList.toggle("oc-open");
        btn.classList.toggle("on", open);
      });
      var ol = cta.querySelector(".original-link");
      if (ol && ol.nextSibling) cta.insertBefore(btn, ol.nextSibling);
      else cta.appendChild(btn);
    }
  } else {
    /* Item4: 피드 핵심(gist) 클릭 → 상세 페이지 (모바일 트위터식) */
    var g = card.querySelector(".gist");
    if (g && !g.__v83open){
      g.__v83open = true;
      g.addEventListener("click", function(e){
        if (e.target.closest("a,button,.ent-link,.gloss-link,.has-tip,summary")) return;
        if (typeof v83OpenItem === "function") v83OpenItem(id);
      });
    }
  }
}

/* ---- 피드 카드 3문단 프리뷰: 넘치는 카드만 클램프 + "더 보기 →" (상세로) ---- */
function v83ClipScan(){
  if (!document.documentElement.classList.contains("v83")) return;
  document.querySelectorAll("#feedList > .card").forEach(function(c){
    try { v83CardFix(c); } catch(e){}
    if (c.classList.contains("v83one") || c.classList.contains("collapsed")){
      c.classList.remove("v83clip");
      return;
    }
    var g = c.querySelector(".gist");
    if (!g || !g.clientHeight) return;   /* not laid out yet: retry next tick */
    /* 판정을 한 번으로 굳히지 않는다 — 요약 전문이 나중에 도착하면 접힘 여부가
       바뀐다. 펼친 카드는 아래 v83expanded 검사로 보호된다. */
    var id = (c.id || "").replace(/^sig-/, "");
    if (!c.querySelector(".v83-more")){
      var fold = c.querySelector(".gist-fold") || g.parentElement;
      var b = document.createElement("button");
      b.className = "v83-more"; b.type = "button";
      b.textContent = (((typeof STRINGS !== "undefined" && STRINGS[LANG]) || {}).loadMore || "더 보기") + " →";
      b.addEventListener("click", function(e){
        /* 모바일과 동일: 더 보기 → 상세로 이동하지 않고 그 자리에서 본문을 펼침 */
        e.stopPropagation();
        c.classList.add("v83expanded");
        c.classList.remove("v83clip");
      });
      fold.appendChild(b);
    }
    if (!c.classList.contains("v83expanded")) c.classList.toggle("v83clip", g.scrollHeight > 260);
  });
}
setInterval(v83ClipScan, 1000);
v83ClipScan();

/* ==== 라운드13: 언어선택 좌측 이동 + 즉시 반영 + 검색 상단고정 + 함께읽기 우측 ==== */
/* (1) 우측 상단 언어선택을 좌측 패널(#v83nav)로 이동 (CTA 위) */
function v83MoveLang(){
  try {
    var nav = document.getElementById("v83nav");
    var lm = document.getElementById("langMenu");
    if (!nav || !lm) return;
    if (nav.contains(lm)) return;
    lm.classList.add("v83-lang");
    var cta = document.getElementById("v83cta");
    if (cta && cta.parentNode === nav) nav.insertBefore(lm, cta);
    else nav.appendChild(lm);
  } catch (e){}
}

/* 라운드16: 검색창을 우측 패널 최상단 → 상단바 맨 우측으로 이동 (X처럼) */
function v83MoveSearch(){
  try {
    var ni = document.querySelector(".nav-inner");
    var sr = document.querySelector(".v83-search");
    if (!ni || !sr) return;
    if (sr.parentNode === ni) return;
    ni.appendChild(sr);
  } catch (e){}
}

/* (3) 언어 변경 시 좌측 패널이 새로고침 없이 즉시 바뀌도록 라벨 다시 세팅 */
function v83Relabel(){
  try {
    var nav = document.getElementById("v83nav");
    if (!nav) return;
    nav.querySelectorAll(".v83-link").forEach(function(b){
      var k = b.getAttribute("data-k"); if (!k) return;
      var sp = b.querySelector("span");
      if (sp && typeof v83T === "function") sp.textContent = v83T(k);
    });
    var cta = document.getElementById("v83cta");
    if (cta && typeof v83T === "function") cta.textContent = v83T("join");
    var me = document.getElementById("v83me");
    if (me){ var ms = me.querySelector("span:not(.v83-ava)"); if (ms && typeof v83T === "function") ms.textContent = v83T("me"); }
    var si = document.querySelector(".v83-search input");
    if (si && typeof v83T === "function") si.placeholder = v83T("search");
    var fsw = document.getElementById("v83fsw");
    if (fsw){
      var fl = ({ ko:["최신","팔로잉"], en:["New","Following"], ja:["最新","フォロー中"] })[(typeof LANG!=="undefined")?LANG:"ko"] || ["최신","팔로잉"];
      var ba = fsw.querySelector('button[data-f="all"]'); if (ba) ba.textContent = fl[0];
      var bm = fsw.querySelector('button[data-f="mine"]'); if (bm) bm.textContent = fl[1];
    }
    /* 라운드17: 좌측 패널의 언어 항목은 코드(KO) 대신 풀네임(한국어)으로 — 메뉴답게 */
    var LNAMES = { KO:"한국어", EN:"English", JA:"日本語" };
    document.querySelectorAll("#v83nav .v83-lang span").forEach(function(sp){
      if (sp.classList.contains("lc-arrow")) return;
      var full = LNAMES[(sp.textContent || "").trim()];
      if (full) sp.textContent = full;
    });
  } catch (e){}
}

/* (2) '함께 읽기'를 우측 패널 상세뷰에 — 다가오는 이벤트와 핫 리스트 사이, 3개, hover */
function v83RelatedRail(){
  try {
    var rail = document.getElementById("v83rail");
    var existing = document.getElementById("v83relSec");
    var active = (typeof V83ITEM !== "undefined" && V83ITEM) && rail
      && !(typeof QUERY !== "undefined" && QUERY)
      && !(typeof ENTITY_VIEW !== "undefined" && ENTITY_VIEW)
      && !(typeof SERIES_VIEW !== "undefined" && SERIES_VIEW);
    if (!active){ if (existing) existing.remove(); return; }
    var it = (typeof ITEMS !== "undefined") ? ITEMS.find(function(x){ return x.id === V83ITEM; }) : null;
    var rel = (it && it.related ? it.related : [])
      .map(function(rid){ return (typeof ITEMS !== "undefined") ? ITEMS.find(function(x){ return x.id === rid; }) : null; })
      .filter(Boolean).slice(0, 3);
    if (!rel.length){ if (existing) existing.remove(); return; }
    /* 이미 같은 글로 그려져 있으면 재생성 생략 */
    if (existing && existing.getAttribute("data-for") === V83ITEM) return;
    if (existing) existing.remove();
    var S = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG] : null;
    var sec = document.createElement("section");
    sec.id = "v83relSec";
    sec.setAttribute("data-for", V83ITEM);
    var title = (S && S.related) ? S.related : "함께 읽기";
    var h = document.createElement("h2"); h.className = "section-title"; h.textContent = title;
    sec.appendChild(h);
    var wrap = document.createElement("div"); wrap.className = "hot-rail";
    rel.forEach(function(item){ wrap.appendChild(v83HotlRow(item)); });
    sec.appendChild(wrap);
    var cal = document.getElementById("v83calSec");
    var hotSec = null;
    var hr = document.getElementById("hotRail"); if (hr) hotSec = hr.closest("section");
    if (hotSec && hotSec.parentNode === rail) rail.insertBefore(sec, hotSec);
    else if (cal && cal.nextSibling) rail.insertBefore(sec, cal.nextSibling);
    else rail.appendChild(sec);
  } catch (e){}
}

/* 핫 리스트와 동일한 hover(카드 이미지 + 한줄요약) 행 생성 */
function v83HotlRow(item){
  var b = document.createElement("button");
  b.className = "hotl-row";
  b.onclick = function(){ if (typeof v83OpenItem === "function") v83OpenItem(item.id); else if (typeof goToItem === "function") goToItem(item.id); };
  var LANG2 = (typeof LANG !== "undefined") ? LANG : "ko";
  var v = (typeof VIEW_COUNTS !== "undefined" && VIEW_COUNTS[item.id]) || 0;
  var c = (typeof COMMENT_COUNTS !== "undefined" && COMMENT_COUNTS[item.id]) || 0;
  var S2 = (typeof STRINGS !== "undefined" && STRINGS[LANG2]) ? STRINGS[LANG2] : {};
  var meta = ((typeof dispName === "function") ? dispName(item.source) : (item.source || ""))
    + " · " + ((typeof fmt === "function") ? fmt(item.date) : (item.date || ""))
    + (v ? " · " + (S2.views || "") + " " + v : "") + (c ? " · 💬 " + c : "");
  b.innerHTML = '<span class="hotl-t"></span><span class="hotl-m"></span>';
  b.querySelector(".hotl-t").textContent = (item.title[LANG2] || item.title.en || "");
  b.querySelector(".hotl-m").textContent = meta;
  try {
    var cv = document.createElement("span");
    cv.className = "hotl-cov";
    var ci = (typeof coverImg === "function") ? coverImg(item) : null;
    if (ci && ci.url){
      if (!(ci.mode === "photo" || ci.mode === "face")) cv.className += " hotl-cov-logo";
      cv.style.backgroundImage = "url('" + String(ci.url).replace(/'/g, "%27") + "')";
    } else {
      cv.className += " hotl-cov-plain";
    }
    var g = String((item.gist && (item.gist[LANG2] || item.gist.en)) || "").replace(/\s+/g, " ").trim();
    var sum = "";
    for (var i = 0; i < g.length; i++){
      sum += g[i]; var ch = g[i];
      if ((ch === "." || ch === "!" || ch === "?") && (i + 1 >= g.length || g[i + 1] === " ") && sum.length >= 40) break;
    }
    if (sum.length > 110) sum = sum.slice(0, 108) + "…";
    if (sum){ var sm = document.createElement("span"); sm.className = "hotl-sum"; sm.textContent = sum; cv.appendChild(sm); }
    b.appendChild(cv);
  } catch (e){}
  return b;
}

/* render()를 감싸 언어 라벨/함께읽기 패널을 매 렌더마다 동기화 */
if (typeof render === "function"){
  var _v83origRender = render;
  window.render = function(){
    var r = _v83origRender.apply(this, arguments);
    try { var one = document.querySelector("#feedList > .card.v83one"); if (one) v83CardFix(one); } catch (e){}
    try { v83MoveLang(); } catch (e){}
    try { v83MoveSearch(); } catch (e){}
    try { v83Relabel(); } catch (e){}
    try { v83RelatedRail(); } catch (e){}
    return r;
  };
}
/* 마운트가 비동기(데이터 로드 후)라 render 래퍼만으론 초기 이동이 늦을 수 있어,
   #v83nav가 생기는 즉시 언어선택을 옮기도록 짧게 폴링 */
var _v83initN = 0;
var _v83initTimer = setInterval(function(){
  _v83initN++;
  try { v83MoveLang(); v83MoveSearch(); v83Relabel(); } catch (e){}
  var nav = document.getElementById("v83nav"), lm = document.getElementById("langMenu");
  var ni = document.querySelector(".nav-inner"), sr = document.querySelector(".v83-search");
  var langOk = nav && lm && nav.contains(lm);
  var searchOk = ni && sr && sr.parentNode === ni;
  if (langOk && searchOk) { clearInterval(_v83initTimer); }
  else if (_v83initN > 40) { clearInterval(_v83initTimer); }
}, 150);
v83MoveLang(); v83MoveSearch(); v83Relabel(); v83RelatedRail();
})();
