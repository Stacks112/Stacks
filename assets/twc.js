/* ==== BETA comment sheet — replaces the inline comment box ==== */
(function(){
"use strict";
if (typeof COMMENTS_API === "undefined" || !COMMENTS_API) return;

var TWS = {
  en: { title:"Comments", top:"Top", newest:"Latest",
    viewReplies:"View {n} replies", viewReply:"View 1 reply", hideReplies:"Hide replies",
    ph:"Post your reply", nameLabel:"Name", namePh:"Name shown with your comments",
    replyingTo:"Replying to {h}", cancel:"Cancel", reply:"Reply",
    empty:"No comments yet. Start the conversation.", loading:"Loading comments…",
    error:"Couldn't post. Please try again.", rate:"Too fast — try again in a minute.",
    sent:"Posted.", now:"now", min:"m", hr:"h", day:"d", viewAll:"View all {n} comments" },
  ko: { title:"댓글", top:"인기순", newest:"최신순",
    viewReplies:"답글 {n}개 보기", viewReply:"답글 1개 보기", hideReplies:"답글 접기",
    ph:"댓글을 남겨보세요", nameLabel:"이름", namePh:"댓글에 표시될 이름 (한 번만 설정)",
    replyingTo:"{h}님에게 답글 남기는 중", cancel:"취소", reply:"답글",
    empty:"아직 댓글이 없어요. 첫 대화를 시작해보세요.", loading:"댓글 불러오는 중…",
    error:"등록에 실패했어요. 다시 시도해주세요.", rate:"너무 빨라요. 잠시 후 다시 시도해주세요.",
    sent:"게시됐어요.", now:"방금", min:"분", hr:"시간", day:"일", viewAll:"댓글 {n}개 모두 보기" },
  ja: { title:"コメント", top:"人気順", newest:"新着順",
    viewReplies:"返信{n}件を表示", viewReply:"返信1件を表示", hideReplies:"返信を隠す",
    ph:"返信を投稿", nameLabel:"名前", namePh:"コメントに表示される名前",
    replyingTo:"{h}さんに返信中", cancel:"キャンセル", reply:"返信",
    empty:"まだコメントがありません。最初の会話を始めましょう。", loading:"コメントを読み込み中…",
    error:"投稿できませんでした。もう一度お試しください。", rate:"速すぎます。少し待ってから再試行してください。",
    sent:"投稿しました。", now:"たった今", min:"分", hr:"時間", day:"日", viewAll:"コメント{n}件をすべて表示" }
};
function TW(){ return TWS[(typeof LANG !== "undefined" && TWS[LANG]) ? LANG : "ko"]; }

var TWC = { id:null, sort:"top", rows:[], open:{}, replyTo:null, hist:false };

/* deterministic hash for avatar color + handle suffix */
function twHash(s){
  var h = 5381; s = String(s || "");
  for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h;
}
function twHandle(nick){
  var slug = String(nick || "").toLowerCase().replace(/\s+/g, "_")
    .replace(/[^a-z0-9_가-힣ぁ-ゖァ-ヺ一-龯]/g, "").slice(0, 12);
  if (!slug) slug = "user";
  return "@" + slug + "_" + String(twHash(nick) % 10000).padStart(4, "0");
}
function twAvatar(nick, cls){
  var h = twHash(nick) % 360;
  var ch = String(nick || "?").trim().charAt(0).toUpperCase() || "?";
  return '<div class="twi-av ' + (cls || "") + '" style="background:hsl(' + h + ',52%,44%)">' + esc(ch) + "</div>";
}
function twTime(iso){
  var W = TW();
  try {
    var t = new Date(iso).getTime();
    if (!isFinite(t)) return "";
    var d = Math.max(0, (Date.now() - t) / 1000);
    if (d < 60) return W.now;
    if (d < 3600) return Math.floor(d / 60) + W.min;
    if (d < 86400) return Math.floor(d / 3600) + W.hr;
    if (d < 7 * 86400) return Math.floor(d / 86400) + W.day;
    var dt = new Date(t);
    return String(dt.getMonth() + 1).padStart(2, "0") + "." + String(dt.getDate()).padStart(2, "0");
  } catch (e){ return ""; }
}
function twLinkify(escaped){
  /* URLs first (matched on the escaped text; & is already &amp; which is valid in href) */
  var out = escaped.replace(/(https?:\/\/[^\s<]+)/g, function(m){
    return '<a class="twi-link" href="' + m + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">' + m + "</a>";
  });
  return out.replace(/(^|[\s])(@[\w가-힣ぁ-ゖァ-ヺ一-龯._-]{1,24})/g,
    '$1<span class="twi-mention">$2</span>');
}

/* ---- internal post links -> quote card (like a quoted tweet) ---- */
function twQuoteId(text){
  try {
    var re = /(?:stacksdaily\.com|stacks112\.github\.io|wnrakrhdn128\.workers\.dev)\/(?:p\/([a-z0-9_-]+)\.html|s\/([a-z0-9_-]+)|#?sig-([a-z0-9_-]+))/gi;
    var m;
    while ((m = re.exec(text))){
      var id = m[1] || m[2] || m[3];
      if (id && typeof ITEMS !== "undefined" && ITEMS.some(function(x){ return x.id === id; })) return id;
    }
  } catch (e){}
  return null;
}
function twQuoteHtml(id){
  var it = (typeof ITEMS !== "undefined") ? ITEMS.find(function(x){ return x.id === id; }) : null;
  if (!it) return "";
  var src = (typeof dispName === "function") ? dispName(it.source) : it.source;
  return '<div class="twi-quote" onclick="twOpenQuote(\'' + id + '\', event)">'
    + '<div class="twi-quote-h">' + twAvatar(src, "twi-qav") + "<b>" + esc(src) + "</b>"
    + '<span class="twi-hd">· ' + esc((it.date || "").slice(5)) + "</span></div>"
    + '<div class="twi-quote-t">' + esc(it.title && (it.title[LANG] || it.title.en) || "") + "</div>"
    + "</div>";
}
window.twOpenQuote = function(id, ev){
  if (ev){ ev.stopPropagation(); ev.preventDefault(); }
  closeComments();
  if (document.documentElement.classList.contains("v83") && typeof v83OpenItem === "function") v83OpenItem(id);
  else if (typeof goToItem === "function") goToItem(id);
};

/* ---------- sheet skeleton (built once) ---------- */
var twcBuilt = false;
function twcBuild(){
  if (twcBuilt) return;
  twcBuilt = true;
  var ov = document.createElement("div");
  ov.id = "twcOv";
  ov.className = "twc-ov";
  ov.hidden = true;
  ov.innerHTML =
    '<div class="twc-sheet" role="dialog" aria-modal="true">'
    + '<div class="twc-head">'
    +   '<button class="twc-back" onclick="closeComments()" aria-label="close">&#x2715;</button>'
    +   '<div class="twc-title" id="twcTitle"></div>'
    +   '<button class="twc-sort" id="twcSort" onclick="twcToggleSort()"></button>'
    + '</div>'
    + '<div class="twc-orig" id="twcOrig"></div>'
    + '<div class="twc-scroll" id="twcList"></div>'
    + '<div class="twc-comp">'
    +   '<div class="twc-chip" id="twcChip" hidden></div>'
    +   '<div class="twc-namerow" id="twcNameRow" hidden>'
    +     '<input id="twcName" type="text" maxlength="40" autocomplete="nickname">'
    +   '</div>'
    +   '<div class="twc-row">'
    +     '<span id="twcMyAv" onclick="twcEditName()"></span>'
    +     '<textarea class="twc-input" id="twcText" rows="1"></textarea>'
    +     '<button class="twc-send" id="twcSend" onclick="twcSubmit()" disabled></button>'
    +   '</div>'
    +   '<input id="twcHp" type="text" name="website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0" aria-hidden="true">'
    +   '<div class="twc-err" id="twcErr" hidden></div>'
    + '</div></div>';
  document.body.appendChild(ov);
  ov.addEventListener("click", function(e){ if (e.target === ov) closeComments(); });
  document.addEventListener("keydown", function(e){
    if (e.key === "Escape" && !ov.hidden) closeComments();
  });
  var ta = document.getElementById("twcText");
  ta.addEventListener("input", function(){
    ta.style.height = "auto";
    ta.style.height = Math.min(120, ta.scrollHeight) + "px";
    document.getElementById("twcSend").disabled = !ta.value.trim();
  });
}

/* ---------- open / close (override the old inline box) ---------- */
window.toggleComments = function(id){
  twcBuild();
  var W = TW();
  TWC.id = id; TWC.rows = []; TWC.open = {}; TWC.replyTo = null; TWC.sort = "top";
  var ov = document.getElementById("twcOv");
  var wasOpen = !ov.hidden;
  ov.hidden = false;
  document.body.style.overflow = "hidden";
  /* 2026-07-25 (june, 모바일 전수조사): 댓글 시트만 뒤로가기로 안 닫혔다.
     엔트리를 하나 밀어두고 index.html의 popstate 맨 앞에서 받아 닫는다. */
  if (!wasOpen && !TWC.hist){
    try { history.pushState({ stk: (history.state && history.state.stk) || 0, twc: 1 }, ""); TWC.hist = true; } catch (e) {}
  }
  document.getElementById("twcTitle").innerHTML = esc(W.title) + ' <span id="twcCount"></span>';
  document.getElementById("twcSort").textContent = W.top + " ▾";
  document.getElementById("twcText").placeholder = W.ph;
  document.getElementById("twcSend").textContent = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG].cSubmit : "Post";
  document.getElementById("twcName").placeholder = W.namePh;
  twcClearReply();
  twcSetIdentity();
  /* original post context (like Twitter shows the tweet above replies) */
  var it = (typeof ITEMS !== "undefined") ? ITEMS.find(function(x){ return x.id === id; }) : null;
  var og = document.getElementById("twcOrig");
  if (it){
    var src = (typeof dispName === "function") ? dispName(it.source) : it.source;
    og.hidden = false;
    og.innerHTML = twAvatar(src)
      + '<div class="twc-orig-t"><b>' + esc(src) + '</b> <span class="twi-hd">· '
      + esc((it.date || "").slice(5)) + '</span><br>' + esc(it.title && (it.title[LANG] || it.title.en) || "") + "</div>";
  } else { og.hidden = true; og.innerHTML = ""; }
  if (typeof setRead === "function") setRead(id);
  twcLoad();
};
window.closeComments = function(fromPop){
  var ov = document.getElementById("twcOv");
  if (ov) ov.hidden = true;
  document.body.style.overflow = "";
  TWC.id = null; TWC.replyTo = null;
  /* ✕·배경·ESC로 닫았으면 밀어둔 엔트리도 걷어낸다. 그때 오는 popstate가
     밑에 있는 상세까지 닫아버리지 않게 한 번은 무시하라고 표시해 둔다. */
  if (TWC.hist && fromPop !== true){
    TWC.hist = false;
    window.__twcSilent = true;
    try { history.back(); } catch (e) { window.__twcSilent = false; }
  } else if (fromPop === true) TWC.hist = false;
};
window.twcToggleSort = function(){
  var W = TW();
  TWC.sort = TWC.sort === "top" ? "new" : "top";
  document.getElementById("twcSort").textContent = (TWC.sort === "top" ? W.top : W.newest) + " ▾";
  twcRender();
};

/* ---------- identity (device pseudo-profile, no login) ---------- */
function twcNick(){ return (typeof lsGet === "function" && lsGet("stk_nick")) || ""; }
function twcSetIdentity(){
  var n = twcNick();
  document.getElementById("twcMyAv").innerHTML = twAvatar(n || "?");
  document.getElementById("twcNameRow").hidden = !!n;
  if (!n) document.getElementById("twcName").value = "";
}
window.twcEditName = function(){
  var row = document.getElementById("twcNameRow");
  row.hidden = false;
  var inp = document.getElementById("twcName");
  inp.value = twcNick();
  inp.focus();
};

/* ---------- data ---------- */
function twcLoad(){
  var W = TW();
  var list = document.getElementById("twcList");
  list.innerHTML = '<div class="twc-status">' + W.loading + "</div>";
  fetch(COMMENTS_API + "/comments?pageId=" + encodeURIComponent(TWC.id))
    .then(function(r){ if (!r.ok) throw 0; return r.json(); })
    .then(function(j){
      TWC.rows = (j && Array.isArray(j.data)) ? j.data : [];
      twcRender();
      TWIN_CACHE[TWC.id] = TWC.rows;
      twinRender(TWC.id);
    })
    .catch(function(){
      list.innerHTML = '<div class="twc-status">' + W.empty + "</div>";
    });
}
function twcTree(){
  var roots = [], kids = {};
  TWC.rows.forEach(function(c){
    if (c.parentId){ (kids[c.parentId] = kids[c.parentId] || []).push(c); }
    else roots.push(c);
  });
  if (!roots.length) roots = TWC.rows.slice();
  for (var k in kids) kids[k].sort(function(a, b){ return (a.id || 0) - (b.id || 0); });
  if (TWC.sort === "top"){
    roots.sort(function(a, b){
      var d = (Number(b.likes) || 0) - (Number(a.likes) || 0);
      return d !== 0 ? d : (b.id || 0) - (a.id || 0);
    });
  } else {
    roots.sort(function(a, b){ return (b.id || 0) - (a.id || 0); });
  }
  return { roots: roots, kids: kids };
}
function twcItemHtml(c, isReply, kidCount, isOpen){
  var W = TW();
  var cid = (c.id == null) ? "" : String(c.id);
  var likes = Number(c.likes) || 0;
  var liked = cid && typeof CLIKED !== "undefined" && CLIKED.has(cid);
  var admin = !!c.admin;
  var acts = cid
    ? '<div class="twi-a">'
      + '<button onclick="twcReply(\'' + cid + '\')">'
      + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 21c4.97 0 9-3.58 9-8s-4.03-8-9-8-9 3.58-9 8c0 1.9.74 3.64 1.98 5.01L4 21l4.13-1.38A9.9 9.9 0 0 0 12 21z"/></svg>'
      + (kidCount ? "<span>" + kidCount + "</span>" : "") + "</button>"
      + '<button class="twi-like' + (liked ? " on" : "") + '" onclick="twcLike(\'' + cid + '\', this)">'
      + '<span class="twi-heart">' + (liked ? "♥" : "♡") + '</span><span>' + (likes || "") + "</span></button>"
      + "</div>"
    : "";
  var more = (!isReply && kidCount)
    ? '<button class="twi-more" onclick="twcToggleKids(\'' + cid + '\')">'
      + (isOpen ? W.hideReplies
         : (kidCount === 1 ? W.viewReply : W.viewReplies.replace("{n}", kidCount)))
      + "</button>"
    : "";
  var qid = twQuoteId(c.content);
  return '<div class="twi' + (isReply ? " twi-r" : "") + (isOpen ? " twi-open" : "")
    + (kidCount ? " twi-haskids" : "") + '" id="twi-' + cid + '">'
    + '<div class="twi-g">' + twAvatar(c.nickname)
    + ((isOpen && kidCount) ? '<div class="twi-line"></div>' : "") + "</div>"
    + '<div class="twi-m">'
    + '<div class="twi-h"><b>' + esc(c.nickname) + "</b>"
    + (admin ? '<span class="twi-badge" title="Stacks">✓</span>' : "")
    + '<span class="twi-hd">' + esc(twHandle(c.nickname)) + " · " + twTime(c.createdAt) + "</span></div>"
    + '<div class="twi-t">' + twLinkify(esc(c.content)) + "</div>"
    + (qid ? twQuoteHtml(qid) : "")
    + acts + more
    + (isOpen ? '<div class="twi-kids" id="twk-' + cid + '"></div>' : "")
    + "</div></div>";
}
function twcRender(){
  var W = TW();
  var list = document.getElementById("twcList");
  var n = TWC.rows.length;
  var cnt = document.getElementById("twcCount");
  if (cnt) cnt.textContent = n ? (typeof fmtCount === "function" ? fmtCount(n) : n) : "";
  if (!n){
    list.innerHTML = '<div class="twc-status">' + W.empty + "</div>";
    return;
  }
  var t = twcTree();
  list.innerHTML = t.roots.map(function(c){
    var kc = (c.id != null && t.kids[c.id]) ? t.kids[c.id].length : 0;
    var open = !!TWC.open[c.id];
    return twcItemHtml(c, false, kc, open);
  }).join("");
  /* fill expanded reply groups */
  t.roots.forEach(function(c){
    if (!TWC.open[c.id]) return;
    var box = document.getElementById("twk-" + c.id);
    if (box && t.kids[c.id]){
      box.innerHTML = t.kids[c.id].map(function(k){ return twcItemHtml(k, true, 0, false); }).join("");
    }
  });
}
window.twcToggleKids = function(cid){
  TWC.open[cid] = !TWC.open[cid];
  twcRender();
};

/* ---------- like ---------- */
window.twcLike = function(cid, btn){
  cid = String(cid);
  var on = !CLIKED.has(cid);
  if (on) CLIKED.add(cid); else CLIKED.delete(cid);
  store.set("stk_cliked", Array.from(CLIKED));
  var row = TWC.rows.find(function(c){ return String(c.id) === cid; });
  if (row) row.likes = Math.max(0, (Number(row.likes) || 0) + (on ? 1 : -1));
  if (btn){
    btn.classList.toggle("on", on);
    var v = row ? row.likes : 0;
    btn.innerHTML = '<span class="twi-heart">' + (on ? "♥" : "♡") + '</span><span>' + (v || "") + "</span>";
  }
  if (on && typeof track === "function") track("clike/" + cid);
  fetch(COMMENTS_API + "/clike", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ commentId: cid, action: on ? "like" : "unlike" })
  }).then(function(r){ return r.ok ? r.json() : null; })
    .then(function(j){
      if (j && typeof j.likes === "number" && row){ row.likes = j.likes; }
    }).catch(function(){});
};

/* ---------- reply targeting (replies attach to the ROOT; nested targets get an @mention) ---------- */
window.twcReply = function(cid){
  var W = TW();
  var c = TWC.rows.find(function(x){ return String(x.id) === String(cid); });
  if (!c) return;
  var rootId = c.parentId ? String(c.parentId) : String(c.id);
  var isNested = !!c.parentId;
  TWC.replyTo = { root: rootId, name: c.nickname, handle: twHandle(c.nickname) };
  if (c.parentId) TWC.open[rootId] = true;
  var chip = document.getElementById("twcChip");
  chip.hidden = false;
  chip.innerHTML = W.replyingTo.replace("{h}", "<b>" + esc(TWC.replyTo.handle) + "</b>")
    + ' <button onclick="twcClearReply()">' + W.cancel + "</button>";
  var ta = document.getElementById("twcText");
  if (isNested && ta.value.indexOf(TWC.replyTo.handle) !== 0){
    ta.value = TWC.replyTo.handle + " " + ta.value.replace(/^@\S+\s*/, "");
  }
  ta.focus();
  ta.dispatchEvent(new Event("input"));
};
window.twcClearReply = function(){
  TWC.replyTo = null;
  var chip = document.getElementById("twcChip");
  if (chip){ chip.hidden = true; chip.innerHTML = ""; }
};

/* ---------- submit ---------- */
window.twcSubmit = function(){
  var W = TW();
  var ta = document.getElementById("twcText");
  var err = document.getElementById("twcErr");
  var send = document.getElementById("twcSend");
  var content = ta.value.trim();
  if (!content) return;
  /* first-time: need a name */
  var nameRow = document.getElementById("twcNameRow");
  var nameInp = document.getElementById("twcName");
  var nick = twcNick();
  if (!nameRow.hidden && nameInp.value.trim()) nick = nameInp.value.trim();
  if (!nick){
    nameRow.hidden = false;
    nameInp.focus();
    return;
  }
  lsSet("stk_nick", nick);
  nameRow.hidden = true;
  twcSetIdentity();
  send.disabled = true;
  err.hidden = true;
  fetch(COMMENTS_API + "/comments", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pageId: TWC.id, content: content, nickname: nick,
      parentId: TWC.replyTo ? TWC.replyTo.root : undefined,
      website: document.getElementById("twcHp").value || "",
      /* hidden: operator badge — set localStorage stk_admin_key on your own
         device to post verified ✓ comments (needs worker v10) */
      adminKey: (typeof lsGet === "function" && lsGet("stk_admin_key")) || undefined
    })
  }).then(function(r){
    if (!r.ok) throw (r.status === 429 ? "rate" : "bad");
    ta.value = ""; ta.style.height = "auto";
    if (TWC.replyTo) TWC.open[TWC.replyTo.root] = true;
    twcClearReply();
    if (typeof track === "function") track("comment/" + TWC.id);
    if (typeof bumpCommentCount === "function") bumpCommentCount(TWC.id);
    twcLoad();
    send.disabled = true; /* textarea is empty again */
  }).catch(function(e){
    err.hidden = false;
    err.className = "twc-err";
    err.textContent = e === "rate" ? W.rate : W.error;
    send.disabled = !ta.value.trim();
  });
};

/* ---------- inline reply bar under each post (rendered by the card template) ---------- */
window.twInlineHtml = function(id){
  var W = TW();
  var nick = twcNick();
  var send = (typeof STRINGS !== "undefined" && STRINGS[LANG]) ? STRINGS[LANG].cSubmit : "Post";
  return '<div class="twin">'
    + twAvatar(nick || "?")
    + '<input class="twin-in" id="twin-' + id + '" maxlength="2000" placeholder="' + esc(W.ph)
    + '" onkeydown="twInlineKey(event, \'' + id + '\')">'
    + '<button class="twin-send" id="twinb-' + id + '" onclick="twInlineSend(\'' + id + '\')">' + send + "</button>"
    + "</div>"
    + '<div class="twin-list" id="twinl-' + id + '" data-twinl="' + id + '"></div>';
};

/* ---------- inline comment previews: lazy-loaded per visible card ---------- */
var TWIN_CACHE = {};
function twinItem(c, pageId){
  var qid = twQuoteId(c.content);
  return '<div class="twin-it" onclick="if(event.target.closest(\'a,.twi-quote\'))return;toggleComments(\'' + pageId + '\')">'
    + twAvatar(c.nickname)
    + '<div class="twin-it-m">'
    + '<div class="twi-h"><b>' + esc(c.nickname) + "</b>"
    + (c.admin ? '<span class="twi-badge" title="Stacks">✓</span>' : "")
    + '<span class="twi-hd">' + esc(twHandle(c.nickname)) + " · " + twTime(c.createdAt) + "</span></div>"
    + '<div class="twi-t">' + twLinkify(esc(c.content)) + "</div>"
    + (qid ? twQuoteHtml(qid) : "")
    + "</div></div>";
}
function twinRender(id){
  var el = document.getElementById("twinl-" + id);
  if (!el) return;
  var rows = TWIN_CACHE[id] || [];
  if (!rows.length){ el.innerHTML = ""; return; }
  var W = TW();
  var roots = rows.filter(function(c){ return !c.parentId; });
  if (!roots.length) roots = rows.slice();
  roots.sort(function(a, b){
    var d = (Number(b.likes) || 0) - (Number(a.likes) || 0);
    return d !== 0 ? d : (b.id || 0) - (a.id || 0);
  });
  var top = roots.slice(0, 2);
  var html = top.map(function(c){ return twinItem(c, id); }).join("");
  if (rows.length > top.length){
    html += '<button class="twin-more" onclick="toggleComments(\'' + id + '\')">'
      + W.viewAll.replace("{n}", rows.length) + "</button>";
  }
  el.innerHTML = html;
}
function twinLoad(id, force){
  if (!force && TWIN_CACHE[id] !== undefined){ twinRender(id); return; }
  fetch(COMMENTS_API + "/comments?pageId=" + encodeURIComponent(id))
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(j){
      TWIN_CACHE[id] = (j && Array.isArray(j.data)) ? j.data : [];
      twinRender(id);
    })
    .catch(function(){});
}
/* Load previews for every rendered card that has comments. No
   IntersectionObserver: it never fires for the zero-height placeholder in
   some layouts. /counts already tells us which pages have comments, so at
   most a handful of fetches happen, cached in TWIN_CACHE across re-renders. */
var TWIN_LOADING = {};
function twinScan(){
  document.querySelectorAll(".twin-list").forEach(function(el){
    var id = el.getAttribute("data-twinl");
    if (!id) return;
    if (TWIN_CACHE[id] !== undefined){
      /* re-render after the feed rebuilt this card */
      if (!el.firstChild && TWIN_CACHE[id].length) twinRender(id);
      return;
    }
    if (TWIN_LOADING[id]) return;
    var n = (typeof COMMENT_COUNTS !== "undefined" && COMMENT_COUNTS[id]) || 0;
    if (n > 0){
      TWIN_LOADING[id] = 1;
      twinLoad(id);
    }
    /* count 0 or counts not loaded yet: leave unmarked so a later scan retries */
  });
}
var twinScanQueued = false;
try {
  /* setTimeout (not rAF): rAF never fires in a background tab, which would
     permanently wedge the debounce flag and kill the scan loop */
  new MutationObserver(function(){
    if (twinScanQueued) return;
    twinScanQueued = true;
    setTimeout(function(){ twinScanQueued = false; twinScan(); }, 120);
  }).observe(document.body, { childList: true, subtree: true });
} catch (e){}
/* fallback ticker: catches /counts arriving without any DOM mutation */
setInterval(twinScan, 2500);
twinScan();
window.twInlineKey = function(ev, id){
  if (ev && ev.key === "Enter"){ ev.preventDefault(); twInlineSend(id); }
};
window.twInlineSend = function(id){
  var W = TW();
  var inp = document.getElementById("twin-" + id);
  var btn = document.getElementById("twinb-" + id);
  if (!inp) return;
  var text = inp.value.trim();
  if (!text){ toggleComments(id); return; }   /* empty tap = open the thread */
  var nick = twcNick();
  if (!nick){
    /* no name yet: hand off to the sheet (it owns the one-time name flow) */
    toggleComments(id);
    var ta = document.getElementById("twcText");
    if (ta){ ta.value = text; ta.dispatchEvent(new Event("input")); }
    twcEditName();
    inp.value = "";
    return;
  }
  if (btn) btn.disabled = true;
  fetch(COMMENTS_API + "/comments", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pageId: id, content: text, nickname: nick, website: "",
      adminKey: (typeof lsGet === "function" && lsGet("stk_admin_key")) || undefined
    })
  }).then(function(r){
    if (!r.ok) throw (r.status === 429 ? "rate" : "bad");
    inp.value = "";
    inp.placeholder = W.sent + " ✓";
    setTimeout(function(){ inp.placeholder = W.ph; }, 2500);
    if (typeof track === "function") track("comment/" + id);
    if (typeof bumpCommentCount === "function") bumpCommentCount(id);
    twinLoad(id, true);
    if (TWC.id === id) twcLoad();
  }).catch(function(e){
    inp.placeholder = (e === "rate") ? W.rate : W.error;
    setTimeout(function(){ inp.placeholder = W.ph; }, 3000);
  }).then(function(){ if (btn) btn.disabled = false; });
};

})();
