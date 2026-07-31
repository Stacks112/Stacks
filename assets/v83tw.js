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
  ko: { h:"二쇨컙 踰좎뒪???대찓??, d:"留ㅼ＜ ?쇱슂??'?대쾲 二?踰좎뒪?? 硫붿씪??諛쏆쓣 ?몄뼱?덉슂. 援щ룆???대찓?쇱쓣 ?낅젰?섍퀬 ??ν븯硫??섏떊 ?몄뼱媛 諛붾뚯뼱?? 泥섏쓬 ?낅젰?섎뒗 ?대찓?쇱씠硫??덈줈 援щ룆?쇱슂.",
        ph:"?대찓??二쇱냼", save:"???, saving:"???以묅?, saved:"??λ릱?댁슂! ?좏깮???몄뼱濡?諛쒖넚?쇱슂.",
        err:"臾몄젣媛 ?앷꼈?댁슂. ?좎떆 ???ㅼ떆 ?쒕룄??二쇱꽭??", bad:"?대찓??二쇱냼瑜??뺤씤??二쇱꽭??",
        lko:"?쒓뎅??, len:"English", lja:"?ζ쑍沃? },
  en: { h:"Weekly email", d:"The language of your Sunday weekly-best email. Enter the email you subscribed with and save to change it. A new email subscribes fresh.",
        ph:"Email address", save:"Save", saving:"Saving??, saved:"Saved! Your weekly email will arrive in this language.",
        err:"Something went wrong. Please try again.", bad:"Please enter a valid email address.",
        lko:"?쒓뎅??, len:"English", lja:"?ζ쑍沃? },
  ja: { h:"?깁뼋?쇻궧?덀깳?쇈꺂", d:"驪롩길뿥?쒌롣퍓?긱겗?쇻궧?덀뤵깳?쇈꺂??룛岳↑?沃욁겎?쇻귟낵沃?릎??깳?쇈꺂?㏂깋?с궧?믣뀯?쎼걮?╊퓷耶섅걲?뗣겏鸚됪쎍?뺛굦?얇걲?귝뼭?쀣걚?㏂깋?с궧?ゃ굢?계쫸蘊쇠き?ャ겒?듽겲?쇻?,
        ph:"?▲꺖?ャ궋?됥꺃??, save:"岳앭춼", saving:"岳앭춼訝??, saved:"岳앭춼?쀣겲?쀣걼竊곲겦?욁걮?잒?沃욁겎?듿콎?묆걮?얇걲??,
        err:"?ⓦ꺀?쇈걣?븀뵟?쀣겲?쀣걼?귙굚?녵?佯╉걡屋╉걮?뤵걽?뺛걚??, bad:"?▲꺖?ャ궋?됥꺃?밤굮閻븃첀?쀣겍?뤵걽?뺛걚??,
        lko:"?쒓뎅??, len:"English", lja:"?ζ쑍沃? }
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
          var PEND = { ko:"?뺤씤 硫붿씪??蹂대깉?댁슂. 硫붿씪?⑥뿉??踰꾪듉???뚮윭 援щ룆???꾨즺??二쇱꽭??",
                       en:"Check your inbox. Click the button in the confirmation email to finish.",
                       ja:"閻븃첀?▲꺖?ャ굮?곥굤?얇걮?잆귙깳?쇈꺂?끹겗?쒌궭?녈굮?쇈걮??낵沃?굮若뚥틙?쀣겍?뤵걽?뺛걚?? };
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
  ko: { title:"?뚮┝ ?ㅼ젙", newpost:"??湲 ?뚮┝", debate:"?ㅻ뒛???좊줎 ?뚮┝",
        follow:"?붾줈????湲 ?뚮┝", events:"?대깽???뚮┝", push:"釉뚮씪?곗? ?몄떆 ?뚮┝ 耳쒓린",
        pushOn:"釉뚮씪?곗? ?몄떆 ?뚮┝ 耳쒖쭚 ??, pushBlocked:"釉뚮씪?곗??먯꽌 ?뚮┝??李⑤떒???덉뼱?? 二쇱냼李쎌쓽 ?ъ씠???ㅼ젙?먯꽌 ?덉슜??二쇱꽭??" },
  en: { title:"Notification settings", newpost:"New posts", debate:"Today's debate",
        follow:"New posts from who you follow", events:"Event alerts", push:"Enable browser push",
        pushOn:"Browser push is on ??, pushBlocked:"Notifications are blocked by the browser. Allow them in the site settings." },
  ja: { title:"?싩윥鼇?츣", newpost:"?곁?鼇섆틟", debate:"餓딀뿥??쳳??,
        follow:"?뺛궔??꺖訝?겗?곁?", events:"?ㅳ깧?녈깉?싩윥", push:"?뽧꺀?╉궣?싩윥?믡궕?녈겓?쇻굥",
        pushOn:"?뽧꺀?╉궣?싩윥??궕????, pushBlocked:"?뽧꺀?╉궣?㏝싩윥?뚣깣??긿??걬?뚣겍?꾠겲?쇻귙궢?ㅳ깉鼇?츣?㎬㉠??걮?╉걦?졼걬?꾠? }
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
/* 2026-07-30 (june): ?뚮┝ ?ㅼ젙???곸쨷 湲곕줉쨌?뚮쭏 ?쇱웳泥섎읆 ?앹뾽???꾨땲???섏씠吏??
   蹂몃Ц HTML怨?諛곗꽑???섏씠吏 ?뚮뜑??index.html??renderV83AlertsPage)媛 ?????덇쾶
   鍮뚮뜑/??댁뼱 ?⑥닔濡?遺꾨━?덈떎. '?ㅻ뒛???좊줎' ?좉?? 湲곕뒫 ?먯?(6e73c06)??留욎떠 類먮떎. */
window.v83AlertsBodyHtml = function(){
  var t = npT(), p = npGet();
  var row = function(key, label, on){
    return '<button class="v83np-row" data-np="' + key + '"><span>' + label
      + '</span><span class="v83np-sw' + (on ? " on" : "") + '"></span></button>';
  };
  /* 2026-07-25 (june): ?곗뒪?ы넲???뚮┝ "紐⑸줉"???녾퀬 ?ㅼ젙留??덉뿀?? 紐⑸줉???꾩뿉 ?밸뒗?? */
  return (typeof window.v83NotifListHtml === "function" ? window.v83NotifListHtml() : "")
    + row("newpost", t.newpost, p.newpost)
    + row("follow", t.follow, p.follow)
    + row("eventsMaster", t.events, p.eventsMaster)
    + '<button class="v83np-push">' + t.push + '</button>'
    + '<div class="v83np-blocked" hidden></div>'
    + (window.stkNlHtml ? window.stkNlHtml() : '');
};
window.v83AlertsWire = function(root){
  var t = npT();
  if (typeof window.v83NotifBind === "function") window.v83NotifBind(root);
  root.querySelectorAll("[data-np]").forEach(function(b){
    b.addEventListener("click", function(){
      var sw = b.querySelector(".v83np-sw");
      var on = !sw.classList.contains("on");
      sw.classList.toggle("on", on);
      npSet(b.getAttribute("data-np"), on);
    });
  });
  if (window.stkNlWire) window.stkNlWire(root);
  var pushBtn = root.querySelector(".v83np-push");
  var blockedNote = root.querySelector(".v83np-blocked");
  if (!pushBtn) return;
  var pushIsOn = false; /* last known subscription state */
  /* reflect the live push state on the button: white border + "耳쒖쭚 ?? when on,
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
        /* only guess "on" if the SDK never answered ??never override a real opt-out */
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
    /* turn ON: delegate to the (hidden) top-bar push button ??it owns the
       OneSignal opt-in prompt + blocked-permission feedback */
    var nb = document.getElementById("notifBtn");
    if (nb && typeof nb.onclick === "function") nb.onclick();
    setTimeout(reflectPush, 1500);
  });
};
/* legacy shim: ???덉뒪?좊━ ?ㅻ깄??applyView??v.alerts)?대굹 ?몃? ?몄텧遺媛 ?꾩쭅
   紐⑤떖 ?⑥닔瑜?遺瑜몃떎 ???꾨? ?섏씠吏 酉곕줈 蹂대궦?? ?⑥븘 ?덈뜕 紐⑤떖???덉쑝硫?嫄룹뼱?몃떎. */
window.v83AlertsPanel = function(){
  var old = document.getElementById("v83npOv");
  if (old) old.remove();
  if (typeof setTab === "function") setTab("alerts");
};

/* ---- 理쒖떊/?붾줈??tabs: match the center column's width exactly (X-style) ---- */
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
  ko: { recent:"理쒓렐 寃??, clear:"紐⑤몢 吏?곌린", trend:"?ㅻ뒛???멸린",
        guide:"?щ엺, 湲곗뾽, ?ㅼ썙?쒕줈 寃?됲빐蹂댁꽭??, posts:"湲 {n}媛? },
  en: { recent:"Recent", clear:"Clear all", trend:"Popular today",
        guide:"Try searching for people, companies, or keywords", posts:"{n} posts" },
  ja: { recent:"?瓦묆겗濾쒐뇨", clear:"?쇻겧??텋??, trend:"餓딀뿥??볶麗?,
        guide:"雅븀돥?곦펯璵?곥궘?쇈꺈?쇈깋?㎪쩂榮㏂걮?╉겳?얇걮?뉎걝", posts:"{n}餓? }
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

/* ==== ?쎌쓬 ?섏씠釉뚮━?????쇱슫??1 媛쒗렪 (2026-07-23 june 寃곗젙) ==================
   - ???섎룞 ?쎌쓬 踰꾪듉 ?먯? (CSS濡??④?). ?몄쐞?곗쿂???ㅽ겕濡ㅻ줈 吏?섏튇 湲??怨?'蹂?湲'.
   - ?ㅽ겕濡ㅻ줈 移대뱶瑜??꾩쟾??吏?섏튂硫?stk_seen_pending??湲곕줉留??섍퀬,
     ?ㅼ쓬 諛⑸Ц ?쒖옉 ??READ濡??⑸쪟 ???섎떒 '?대? ?쎌? 湲' 洹몃９?쇰줈 媛뺣벑.
     (?대쾲 ?몄뀡 ?붾㈃? ?덈? 嫄대뱶由ъ? ?딆쓬: ?ㅽ겕濡?以?移대뱶媛 ?묓엳嫄곕굹 ?吏곸씠吏 ?딄쾶)
   - READ_BASE: ?몄뀡 ?쒖옉 ?쒖젏???쎌쓬 ?ㅻ깄??(肄붿뼱 媛뺣벑 ?뚰떚?섏씠 李몄“ ??
     ?대쾲 ?몄뀡???댁뼱蹂?湲? ?쒖옄由??좎?, ?ㅼ쓬 諛⑸Ц遺???섎떒?쇰줈) */
var SEEN_PEND = (function(){ try { return new Set(JSON.parse(localStorage.getItem("stk_seen_pending") || "[]")); } catch (e){ return new Set(); } })();
function seenSave(){ try { localStorage.setItem("stk_seen_pending", JSON.stringify(Array.from(SEEN_PEND))); } catch (e){} }
/* 吏??諛⑸Ц???ㅽ겕濡ㅻ줈 吏?섏튇 湲 ?⑸쪟 (READ_BASE ?ㅻ깄???꾩뿉!) */
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

/* ?ㅽ겕濡?異붿쟻: ?쇰컲 ?쇰뱶(理쒖떊/?붾줈???먯꽌留? 移대뱶 ?섎떒???붾㈃ ?꾨줈 40px ?댁긽
   吏?섍?硫?'蹂?湲' ?꾨낫濡?湲곕줉. rAF ???setTimeout (諛깃렇?쇱슫?????⑥젙 ?뚰뵾) */
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

/* ==== ?쇱슫??1: 遺곷쭏??鍮꾪뻾 ?좊땲硫붿씠??(?쎌쓬 ?좊땲硫붿씠?섏뿉???닿?) ============
   遺곷쭏??踰꾪듉 ?대┃ ??踰꾪듉 ?먮━?먯꽌 ?뵔 移⑹씠 ???깆옣 ??醫뚯륫 '遺곷쭏?? 硫붾돱濡?
   ?? ?좎븘媛 ?꾩씠肄??띿쑝濡????ㅼ뼱媛怨???硫붾돱媛 諛섏쭩 */
function bmFly(fromEl){
  try {
    if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var target = document.querySelector('#v83nav .v83-link[data-k="bm"]');
    if (!target || !fromEl) return;
    var r1 = fromEl.getBoundingClientRect(), r2 = target.getBoundingClientRect();
    var cx = r1.left + r1.width / 2, cy = Math.max(60, Math.min(r1.top + r1.height / 2, window.innerHeight - 60));
    /* ?源껋? 硫붾돱???꾩씠肄?泥?svg) 以묒떖 ??'遺곷쭏??紐⑥뼇源뚯? ?ㅼ뼱媛寃? */
    var ticon = target.querySelector("svg") || target;
    var rt = ticon.getBoundingClientRect();
    var tx = rt.left + rt.width / 2, ty = rt.top + rt.height / 2;
    /* 1) 踰꾪듉 ?먮━?먯꽌 ?뵔 移??깆옣 */
    var chip = document.createElement("div");
    chip.className = "rh-chip bm-chip";
    chip.textContent = "?뵔";
    chip.style.left = cx + "px";
    chip.style.top = cy + "px";
    document.body.appendChild(chip);
    setTimeout(function(){
      chip.style.transform = "translate(-50%,-50%) scale(1)";
      chip.style.opacity = "1";
    }, 30);
    /* 2) 遺곷쭏???꾩씠肄섍퉴吏 ?? (?앷퉴吏 ??蹂댁씠寃??좎븘媛??? */
    setTimeout(function(){
      chip.style.transition = "transform .6s cubic-bezier(.45,-0.05,.55,.5)";
      chip.style.transform = "translate(calc(-50% + " + (tx - cx) + "px), calc(-50% + " + (ty - cy) + "px)) scale(.55) rotate(-10deg)";
    }, 300);
    /* 3) ?꾩갑?섎㈃ ?꾩씠肄??띿쑝濡???(?ш린?쒕쭔 異뺤냼쨌?섏씠?? */
    setTimeout(function(){
      chip.style.transition = "transform .22s ease-in, opacity .22s ease-in";
      chip.style.transform = "translate(calc(-50% + " + (tx - cx) + "px), calc(-50% + " + (ty - cy) + "px)) scale(.1)";
      chip.style.opacity = "0";
    }, 910);
    setTimeout(function(){ chip.remove(); }, 1180);
    /* 4) 硫붾돱媛 諛쏆쑝硫댁꽌 諛섏쭩 */
    setTimeout(function(){
      target.classList.add("v83-read-pulse");
      setTimeout(function(){ target.classList.remove("v83-read-pulse"); }, 750);
    }, 930);
  } catch (e){}
}

/* 遺곷쭏???ㅻ쾭?쇱씠?? 異붽????뚮쭔 鍮꾪뻾 (?댁젣??議곗슜?? */
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

/* ==== ?쇱슫??: ?곷? ?쒓컙 ?쒓린 (ts ?덉쑝硫??뺥솗, ?놁쑝硫??대씪 first-seen 洹쇱궗) ==== */
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
  var W = ({ ko:{now:"諛⑷툑",min:"遺???,hr:"?쒓컙 ??}, en:{now:"just now",min:"m ago",hr:"h ago"}, ja:{now:"?잆겂?잋퍓",min:"?녶뎺",hr:"?귡뼋??} })[L] || { now:"諛⑷툑",min:"遺???,hr:"?쒓컙 ?? };
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

/* ==== ?쇱슫??: ?곸꽭酉??щ같移??덉륫異붿쟻 ?꾩씠肄샕룰툖?뺣????볤? ?? + ?쇰뱶 ?듭떖 ?대┃?믪긽??==== */
function v83CardFix(card){
  var id = (card.id || "").replace(/^sig-/, "");
  if (card.classList.contains("v83one")){
    if (card.__v83fix) return; card.__v83fix = true;
    /* ?쇱슫??3: 湲띿젙/遺??ask)???볤? ?곸뿭 留??꾨옒(??'?④퍡 ?쎄린' ?먮━)濡??대룞 +
       "?볤?濡??섍껄" ?쒓굅. '?④퍡 ?쎄린'???곗륫 ?⑤꼸濡?鍮좎죱??v83RelatedRail). */
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
    /* Item5: ?덉륫 異붿쟻(oc)???먮Ц蹂닿린 ???꾩씠肄섏쑝濡??묎린 */
    var oc = card.querySelector(".oc");
    var cta = card.querySelector(".cta-row");
    if (oc && cta && !cta.querySelector(".oc-toggle")){
      oc.classList.add("oc-collap");
      if (cta.nextSibling) cta.parentNode.insertBefore(oc, cta.nextSibling);
      else cta.parentNode.appendChild(oc);
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "oc-toggle";
      btn.innerHTML = "?렞";   /* ?꾩씠肄섎쭔: ?띿뒪???쇰꺼 ?쒓굅, ?대┃ ???묓엺 ?덉륫 ?댁슜???쇱퀜吏?*/
      btn.title = (oc.textContent || "").trim();
      btn.setAttribute("aria-label", (oc.textContent || "").trim() || "?덉륫 異붿쟻");
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
    /* Item4: ?쇰뱶 ?듭떖(gist) ?대┃ ???곸꽭 ?섏씠吏 (紐⑤컮???몄쐞?곗떇) */
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

/* ---- ?쇰뱶 移대뱶 3臾몃떒 ?꾨━酉? ?섏튂??移대뱶留??대옩??+ "??蹂닿린 ?? (?곸꽭濡? ---- */
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
    /* ?먯젙????踰덉쑝濡?援논엳吏 ?딅뒗?????붿빟 ?꾨Ц???섏쨷???꾩갑?섎㈃ ?묓옒 ?щ?媛
       諛붾먮떎. ?쇱튇 移대뱶???꾨옒 v83expanded 寃?щ줈 蹂댄샇?쒕떎. */
    var id = (c.id || "").replace(/^sig-/, "");
    if (!c.querySelector(".v83-more")){
      var fold = c.querySelector(".gist-fold") || g.parentElement;
      var b = document.createElement("button");
      b.className = "v83-more"; b.type = "button";
      b.textContent = (((typeof STRINGS !== "undefined" && STRINGS[LANG]) || {}).loadMore || "??蹂닿린") + " ??;
      b.addEventListener("click", function(e){
        /* 紐⑤컮?쇨낵 ?숈씪: ??蹂닿린 ???곸꽭濡??대룞?섏? ?딄퀬 洹??먮━?먯꽌 蹂몃Ц???쇱묠 */
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

/* ==== ?쇱슫??3: ?몄뼱?좏깮 醫뚯륫 ?대룞 + 利됱떆 諛섏쁺 + 寃???곷떒怨좎젙 + ?④퍡?쎄린 ?곗륫 ==== */
/* (1) ?곗륫 ?곷떒 ?몄뼱?좏깮??醫뚯륫 ?⑤꼸(#v83nav)濡??대룞 (CTA ?? */
function v83MoveLang(){
  try {
    var nav = document.getElementById("v83nav");
    var lm = document.getElementById("langMenu");
    if (!nav || !lm) return;
    if (nav.contains(lm)) return;
    lm.classList.add("v83-lang");
  } catch (e){}
}

/* ?쇱슫??6: 寃?됱갹???곗륫 ?⑤꼸 理쒖긽?????곷떒諛?留??곗륫?쇰줈 ?대룞 (X泥섎읆) */
function v83MoveSearch(){
  try {
    var ni = document.querySelector(".nav-inner");
    var sr = document.querySelector(".v83-search");
    if (!ni || !sr) return;
    if (sr.parentNode === ni) return;
    ni.appendChild(sr);
  } catch (e){}
}

/* (3) ?몄뼱 蹂寃???醫뚯륫 ?⑤꼸???덈줈怨좎묠 ?놁씠 利됱떆 諛붾뚮룄濡??쇰꺼 ?ㅼ떆 ?명똿 */
function v83Relabel(){
  try {
    var nav = document.getElementById("v83nav");
    if (!nav) return;
    nav.querySelectorAll(".v83-link").forEach(function(b){
      var k = b.getAttribute("data-k"); if (!k) return;
      var sp = b.querySelector("span");
      if (sp && typeof v83T === "function") sp.textContent = v83T(k);
    });
    var me = document.getElementById("v83me");
    if (me){ var ms = me.querySelector("span:not(.v83-ava)"); if (ms && typeof v83T === "function") ms.textContent = v83T("me"); }
    var si = document.querySelector(".v83-search input");
    if (si && typeof v83T === "function") si.placeholder = v83T("search");
    var fsw = document.getElementById("v83fsw");
    if (fsw){
      var fl = ({ ko:["理쒖떊","?붾줈??], en:["New","Following"], ja:["???,"?뺛궔??꺖訝?] })[(typeof LANG!=="undefined")?LANG:"ko"] || ["理쒖떊","?붾줈??];
      var ba = fsw.querySelector('button[data-f="all"]'); if (ba) ba.textContent = fl[0];
      var bm = fsw.querySelector('button[data-f="mine"]'); if (bm) bm.textContent = fl[1];
    }
    /* ?쇱슫??7: 醫뚯륫 ?⑤꼸???몄뼱 ??ぉ? 肄붾뱶(KO) ?????ㅼ엫(?쒓뎅???쇰줈 ??硫붾돱?듦쾶 */
    var LNAMES = { KO:"?쒓뎅??, EN:"English", JA:"?ζ쑍沃? };
    document.querySelectorAll("#v83nav .v83-lang span").forEach(function(sp){
      if (sp.classList.contains("lc-arrow")) return;
      var full = LNAMES[(sp.textContent || "").trim()];
      if (full) sp.textContent = full;
    });
  } catch (e){}
}

/* (2) '?④퍡 ?쎄린'瑜??곗륫 ?⑤꼸 ?곸꽭酉곗뿉 ???ㅺ??ㅻ뒗 ?대깽?몄? ??由ъ뒪???ъ씠, 3媛? hover */
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
    /* ?대? 媛숈? 湲濡?洹몃젮???덉쑝硫??ъ깮???앸왂 */
    if (existing && existing.getAttribute("data-for") === V83ITEM) return;
    if (existing) existing.remove();
    var S = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG] : null;
    var sec = document.createElement("section");
    sec.id = "v83relSec";
    sec.setAttribute("data-for", V83ITEM);
    var title = (S && S.related) ? S.related : "?④퍡 ?쎄린";
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

/* ??由ъ뒪?몄? ?숈씪??hover(移대뱶 ?대?吏 + ?쒖쨪?붿빟) ???앹꽦 */
function v83HotlRow(item){
  var b = document.createElement("button");
  b.className = "hotl-row";
  b.onclick = function(){ if (typeof v83OpenItem === "function") v83OpenItem(item.id); else if (typeof goToItem === "function") goToItem(item.id); };
  var LANG2 = (typeof LANG !== "undefined") ? LANG : "ko";
  var v = (typeof VIEW_COUNTS !== "undefined" && VIEW_COUNTS[item.id]) || 0;
  var c = (typeof COMMENT_COUNTS !== "undefined" && COMMENT_COUNTS[item.id]) || 0;
  var S2 = (typeof STRINGS !== "undefined" && STRINGS[LANG2]) ? STRINGS[LANG2] : {};
  var meta = ((typeof dispName === "function") ? dispName(item.source) : (item.source || ""))
    + " 쨌 " + ((typeof fmt === "function") ? fmt(item.date) : (item.date || ""))
    + (v ? " 쨌 " + (S2.views || "") + " " + v : "") + (c ? " 쨌 ?뮠 " + c : "");
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
    if (sum.length > 110) sum = sum.slice(0, 108) + "??;
    if (sum){ var sm = document.createElement("span"); sm.className = "hotl-sum"; sm.textContent = sum; cv.appendChild(sm); }
    b.appendChild(cv);
  } catch (e){}
  return b;
}

/* render()瑜?媛먯떥 ?몄뼱 ?쇰꺼/?④퍡?쎄린 ?⑤꼸??留??뚮뜑留덈떎 ?숆린??*/
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
/* 留덉슫?멸? 鍮꾨룞湲??곗씠??濡쒕뱶 ????render ?섑띁留뚯쑝濡?珥덇린 ?대룞????쓣 ???덉뼱,
   #v83nav媛 ?앷린??利됱떆 ?몄뼱?좏깮????린?꾨줉 吏㏐쾶 ?대쭅 */
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
