(function(){
  "use strict";

  /* Stacks investor tickers are product identifiers, not exchange symbols. */
  var FALLBACK_TICKERS = {
    "berkshire":"BUFFETT", "pershing-square":"ACKMAN", "ark":"WOOD",
    "duquesne":"DRUCK", "appaloosa":"TEPPER", "situational-awareness":"ASCHEN",
    "third-point":"LOEB", "baupost":"KLARMAN", "tci":"HOHN",
    "coatue":"LAFFONT", "soros":"SOROS", "carl-icahn":"ICAHN",
    "tiger-global":"COLEMAN", "viking":"HALVORSEN", "oaktree":"MARKS",
    "scion":"BURRY"
  };
  var COMPARE_KEY = "stk_inv_compare";
  var selected = null;

  var COPY = {
    ko:{
      tickerHelp:"Stacks 투자자 티커", pickTitle:"투자자 비교", pickSub:"2~4명을 골라 포트폴리오를 나란히 비교하세요.",
      compare:"선택한 투자자 비교", selected:"{n}명 선택", min:"2명 이상 선택하세요.", max:"최대 4명까지 비교할 수 있어요.",
      title:"투자자 포트폴리오 비교", edit:"선택 바꾸기", periodWarn:"기준 분기가 다른 투자자가 포함돼 있습니다. 수익률과 보유 비중을 같은 시점의 성과처럼 직접 비교하지 마세요.",
      reported:"13F 기준", total:"공개 평가액", holdings:"보유 종목", top5:"상위 5종목", turnover:"회전율", changes:"분기 변화",
      since:"공시 후", threeM:"최근 3개월", oneY:"최근 1년", vsSpy:"S&P 500 대비", loading:"계산 중", building:"데이터 축적 중",
      overlap:"함께 보유한 종목", overlapSub:"선택한 투자자 중 2명 이상이 함께 보유한 미국 상장 롱 포지션입니다.", noOverlap:"겹치는 종목이 없습니다.", heldBy:"{n}명 보유",
      topHoldings:"상위 보유종목 비교", sectors:"섹터 비중 비교", sectorCoverage:"분류 커버리지", noSector:"분류된 섹터 데이터가 없습니다.",
      weight:"비중", newBuy:"신규", add:"추가", trim:"축소", exit:"청산",
      discTitle:"수익률을 읽는 법", disc:"이 값은 실제 펀드 수익률이 아니라 13F 공개일에 공시된 주식 수를 그대로 보유했다고 가정한 공개 포트폴리오 추정치입니다. 옵션·공매도·현금·채권·해외 상장 자산은 제외됩니다.",
      discWindow:"3개월·1년 수익률은 각 공시가 공개된 뒤 해당 기간이 실제로 지난 경우에만 표시합니다. 아직 지나지 않았다면 ‘데이터 축적 중’으로 표시해 미래 정보를 미리 쓰지 않습니다.",
      coverage:"시세 {p}%", mismatch:"분기 다름"
    },
    en:{
      tickerHelp:"Stacks investor ticker", pickTitle:"Compare investors", pickSub:"Choose 2–4 investors to compare their public portfolios side by side.",
      compare:"Compare selected", selected:"{n} selected", min:"Select at least two investors.", max:"You can compare up to four investors.",
      title:"Investor portfolio comparison", edit:"Change selection", periodWarn:"The selection includes different reporting periods. Do not read returns and weights as same-date results.",
      reported:"13F period", total:"Reported value", holdings:"Holdings", top5:"Top-5 weight", turnover:"Turnover", changes:"Quarterly changes",
      since:"Since filing", threeM:"Last 3 months", oneY:"Last year", vsSpy:"vs. S&P 500", loading:"Calculating", building:"Building history",
      overlap:"Shared holdings", overlapSub:"U.S.-listed long positions held by at least two selected investors.", noOverlap:"No shared holdings.", heldBy:"Held by {n}",
      topHoldings:"Top holdings comparison", sectors:"Sector allocation comparison", sectorCoverage:"Classification coverage", noSector:"No classified sector data.",
      weight:"Weight", newBuy:"New", add:"Added", trim:"Trimmed", exit:"Exited",
      discTitle:"How to read returns", disc:"These are not actual fund returns. They estimate the public portfolio as if the disclosed share counts were held from the 13F filing date. Options, shorts, cash, bonds and non-U.S.-listed assets are excluded.",
      discWindow:"Three-month and one-year returns appear only after that much time has actually passed since public disclosure. Until then, Stacks shows ‘Building history’ to avoid look-ahead bias.",
      coverage:"Prices {p}%", mismatch:"Different period"
    },
    ja:{
      tickerHelp:"Stacks投資家ティッカー", pickTitle:"投資家を比較", pickSub:"2〜4人を選び、公開ポートフォリオを横並びで比較します。",
      compare:"選択した投資家を比較", selected:"{n}人選択", min:"2人以上選択してください。", max:"比較できるのは最大4人です。",
      title:"投資家ポートフォリオ比較", edit:"選択を変更", periodWarn:"基準四半期が異なる投資家が含まれています。リターンや比率を同一時点の成績として直接比較しないでください。",
      reported:"13F基準", total:"公開評価額", holdings:"保有銘柄", top5:"上位5銘柄", turnover:"回転率", changes:"四半期変化",
      since:"開示後", threeM:"直近3か月", oneY:"直近1年", vsSpy:"S&P 500比", loading:"計算中", building:"データ蓄積中",
      overlap:"共通保有銘柄", overlapSub:"選択した投資家のうち2人以上が保有する米国上場ロングポジションです。", noOverlap:"共通銘柄はありません。", heldBy:"{n}人保有",
      topHoldings:"上位保有銘柄比較", sectors:"セクター比率比較", sectorCoverage:"分類カバレッジ", noSector:"分類済みセクターデータがありません。",
      weight:"比率", newBuy:"新規", add:"追加", trim:"縮小", exit:"清算",
      discTitle:"リターンの見方", disc:"これは実際のファンド収益率ではなく、13F公開日に開示株数をそのまま保有したと仮定する公開ポートフォリオ推定値です。オプション・空売り・現金・債券・米国外上場資産は除外されます。",
      discWindow:"3か月・1年リターンは、公開後にその期間が実際に経過した場合だけ表示します。未経過なら「データ蓄積中」とし、未来情報を先取りしません。",
      coverage:"価格 {p}%", mismatch:"四半期が異なります"
    }
  };

  function C(){ return COPY[(typeof LANG !== "undefined" && COPY[LANG]) ? LANG : "ko"]; }
  function ticker(inv){ return (inv && inv.ticker) || FALLBACK_TICKERS[(inv && inv.slug) || ""] || String((inv && inv.slug) || "INV").toUpperCase(); }
  function tickerLabel(inv){ return "INV:" + ticker(inv); }
  function holdings(inv){
    return ((inv && (inv.all_holdings || inv.holdings)) || []).filter(function(h){
      return h && h.change !== "exit" && h.put_call !== "PUT" && h.put_call !== "CALL";
    });
  }
  function pct(v, digits){ return typeof v === "number" && isFinite(v) ? (v * 100).toFixed(digits == null ? 1 : digits) + "%" : "—"; }
  function signedPct(v){ return typeof v === "number" && isFinite(v) ? (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%" : "—"; }
  function perfClass(v){ return typeof v !== "number" || !isFinite(v) ? "" : (v >= 0 ? " up" : " down"); }
  function topWeight(inv, n){ return holdings(inv).slice().sort(function(a,b){ return (b.weight||0)-(a.weight||0); }).slice(0,n).reduce(function(s,h){ return s+(h.weight||0); },0); }
  function selArray(){ return selected ? Array.from(selected) : []; }
  function saveSelection(){ try { store.set(COMPARE_KEY, selArray()); } catch(e) {} }
  function ensureSelection(investors){
    var valid = new Set((investors || []).map(function(inv){ return inv.slug; }));
    if (!selected){
      var saved = [];
      try { saved = store.get(COMPARE_KEY, []); } catch(e) {}
      selected = new Set((Array.isArray(saved) ? saved : []).filter(function(s){ return valid.has(s); }).slice(0,4));
      if (selected.size < 2){
        selected = new Set(["berkshire","pershing-square"].filter(function(s){ return valid.has(s); }));
      }
    } else {
      selected = new Set(selArray().filter(function(s){ return valid.has(s); }).slice(0,4));
    }
    saveSelection();
  }

  function injectTicker(root, inv){
    if (!root || root.querySelector(".inv-ticker")) return;
    var names = root.querySelector(".inv-card-names") || root.querySelector(".series-head-name");
    if (!names) return;
    var t = document.createElement("span");
    t.className = "inv-ticker";
    t.textContent = tickerLabel(inv);
    t.title = C().tickerHelp;
    names.appendChild(t);
  }

  function makePicker(investors){
    ensureSelection(investors);
    var c = C();
    var box = document.createElement("section"); box.className = "inv-compare-picker";
    box.innerHTML = '<div class="inv-compare-picker-head"><div><b>' + esc(c.pickTitle) + '</b><p>' + esc(c.pickSub) + '</p></div>'
      + '<span class="inv-compare-count"></span></div><div class="inv-select-chips"></div>'
      + '<div class="inv-compare-actions"><span class="inv-compare-msg" aria-live="polite"></span>'
      + '<button type="button" class="inv-compare-go"></button></div>';
    var chips = box.querySelector(".inv-select-chips");
    investors.forEach(function(inv){
      var b = document.createElement("button"); b.type = "button"; b.className = "inv-select-chip"; b.setAttribute("aria-pressed", selected.has(inv.slug) ? "true" : "false");
      b.innerHTML = '<span class="inv-select-code">' + esc(tickerLabel(inv)) + '</span><span>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</span>';
      b.addEventListener("click", function(){
        var msg = box.querySelector(".inv-compare-msg");
        if (selected.has(inv.slug)) selected.delete(inv.slug);
        else if (selected.size >= 4){ msg.textContent = c.max; return; }
        else selected.add(inv.slug);
        saveSelection(); refresh(); msg.textContent = "";
      });
      chips.appendChild(b);
    });
    function refresh(){
      var n = selected.size;
      box.querySelector(".inv-compare-count").textContent = c.selected.replace("{n}",n);
      var go = box.querySelector(".inv-compare-go"); go.textContent = c.compare; go.disabled = n < 2;
      chips.querySelectorAll(".inv-select-chip").forEach(function(b, i){
        var on = selected.has(investors[i].slug); b.classList.toggle("on",on); b.setAttribute("aria-pressed",on ? "true" : "false");
      });
    }
    box.querySelector(".inv-compare-go").addEventListener("click", function(){
      if (selected.size < 2){ box.querySelector(".inv-compare-msg").textContent = c.min; return; }
      if (typeof openInvestor === "function") openInvestor("compare");
    });
    refresh();
    return box;
  }

  function summaryCard(inv){
    var c = C(), a = inv.activity || {};
    var card = document.createElement("article"); card.className = "inv-compare-card"; card.setAttribute("data-slug", inv.slug);
    card.innerHTML = '<div class="inv-compare-card-head"><span class="inv-ticker">' + esc(tickerLabel(inv)) + '</span>'
      + '<b>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</b><small>' + esc(locVal(inv.name) || "") + '</small></div>'
      + '<dl class="inv-compare-metrics">'
      + metric(c.reported, esc(invFmtDate(inv.period))) + metric(c.total, esc(invMoneyFmt(inv.total_value)))
      + metric(c.holdings, String(inv.holdings_count == null ? "—" : inv.holdings_count)) + metric(c.top5, pct(topWeight(inv,5),1))
      + metric(c.turnover, pct(a.turnover_pct,1)) + metric(c.since, '<span data-perf="since">' + esc(c.loading) + '</span>')
      + metric(c.threeM, '<span data-perf="3m">' + esc(c.loading) + '</span>') + metric(c.oneY, '<span data-perf="1y">' + esc(c.loading) + '</span>')
      + metric(c.vsSpy, '<span data-perf="spy">' + esc(c.loading) + '</span>') + '</dl>'
      + '<div class="inv-quarter-changes"><span>' + esc(c.newBuy) + ' <b>' + num(a.new_count) + '</b></span><span>' + esc(c.add) + ' <b>' + num(a.added_count) + '</b></span>'
      + '<span>' + esc(c.trim) + ' <b>' + num(a.reduced_count) + '</b></span><span>' + esc(c.exit) + ' <b>' + num(a.exited_count) + '</b></span></div>';
    return card;
  }
  function metric(label, value){ return '<div><dt>' + esc(label) + '</dt><dd>' + value + '</dd></div>'; }
  function num(v){ return typeof v === "number" ? String(v) : "—"; }

  function valuePctAt(res, epoch){
    if (!res || !res.calendar || !res.values || res.calendar.length < 2 || epoch == null) return null;
    var i = 0; while (i < res.calendar.length - 1 && res.calendar[i] < epoch) i++;
    var first = res.values[i], last = res.values[res.values.length - 1];
    return first ? last / first - 1 : null;
  }
  function quotePctAt(q, epoch){
    if (!q || q.error || !q.t || !q.closes || q.t.length < 2 || epoch == null) return null;
    var i = 0; while (i < q.t.length - 1 && q.t[i] < epoch) i++;
    var first = q.closes[i], last = q.closes[q.closes.length - 1];
    return first ? last / first - 1 : null;
  }
  function setPerf(card, key, value, fallback){
    var el = card.querySelector('[data-perf="' + key + '"]'); if (!el) return;
    el.textContent = typeof value === "number" && isFinite(value) ? signedPct(value) : fallback;
    el.className = "inv-perf" + perfClass(value);
  }
  function fillPerformance(card, inv){
    var c = C(), filed = typeof invFiledEpoch === "function" ? invFiledEpoch(inv.filed) : null;
    return Promise.all([invComputeValueSeries(inv), quote1y("spy.us").catch(function(){ return null; })]).then(function(rows){
      if (!card.isConnected) return;
      var res = rows[0], spy = rows[1], lastEpoch = res && res.calendar && res.calendar.length ? res.calendar[res.calendar.length-1] : null;
      var since = valuePctAt(res, filed), age = filed != null && lastEpoch != null ? lastEpoch - filed : 0;
      var r3 = age >= 90*86400 ? valuePctAt(res, lastEpoch - 90*86400) : null;
      var r1 = age >= 365*86400 ? valuePctAt(res, lastEpoch - 365*86400) : null;
      var spySince = quotePctAt(spy, filed);
      setPerf(card,"since",since,"—"); setPerf(card,"3m",r3,c.building); setPerf(card,"1y",r1,c.building);
      setPerf(card,"spy",typeof since === "number" && typeof spySince === "number" ? since-spySince : null,"—");
      var cov = document.createElement("span"); cov.className = "inv-price-cov"; cov.textContent = c.coverage.replace("{p}",Math.round(((res&&res.coverage)||0)*100));
      card.querySelector(".inv-compare-card-head").appendChild(cov);
    }).catch(function(){
      ["since","3m","1y","spy"].forEach(function(k){ setPerf(card,k,null,k === "3m" || k === "1y" ? c.building : "—"); });
    });
  }

  function overlapSection(investors){
    var c=C(), map={};
    investors.forEach(function(inv){ holdings(inv).forEach(function(h){
      var key=h.ticker || h.cusip; if(!key) return;
      if(!map[key]) map[key]={issuer:h.issuer||key,by:{}};
      map[key].by[inv.slug]=h.weight||0;
    }); });
    var rows=Object.keys(map).map(function(k){ var x=map[k]; x.count=Object.keys(x.by).length; x.sum=Object.keys(x.by).reduce(function(s,z){return s+x.by[z];},0); return x; })
      .filter(function(x){return x.count>=2;}).sort(function(a,b){return b.count-a.count || b.sum-a.sum;}).slice(0,20);
    var sec=document.createElement("section"); sec.className="inv-compare-section";
    sec.innerHTML='<h3>'+esc(c.overlap)+'</h3><p>'+esc(c.overlapSub)+'</p>';
    if(!rows.length){sec.innerHTML+='<div class="empty">'+esc(c.noOverlap)+'</div>';return sec;}
    sec.appendChild(compareTable([c.overlap].concat(investors.map(function(i){return tickerLabel(i);})),rows.map(function(r){
      return [esc(r.issuer)+'<small>'+esc(c.heldBy.replace("{n}",r.count))+'</small>'].concat(investors.map(function(i){return pct(r.by[i.slug],2);}));
    })));
    return sec;
  }

  function topHoldingsSection(investors){
    var c=C(), sec=document.createElement("section"); sec.className="inv-compare-section"; sec.innerHTML='<h3>'+esc(c.topHoldings)+'</h3>';
    var cols=investors.map(function(inv){return holdings(inv).slice().sort(function(a,b){return(b.weight||0)-(a.weight||0);}).slice(0,10);});
    var rows=[]; for(var n=0;n<10;n++) rows.push([String(n+1)].concat(cols.map(function(hs){var h=hs[n];return h?esc(h.issuer||h.ticker||"")+'<small>'+pct(h.weight,2)+'</small>':"—";})));
    sec.appendChild(compareTable(["#"].concat(investors.map(function(i){return tickerLabel(i);})),rows)); return sec;
  }

  function sectorSection(investors){
    var c=C(), all={};
    investors.forEach(function(inv){ var sa=inv.sector_alloc||{}; (sa.sectors||[]).forEach(function(r){var name=locVal(r.sector)||"";if(name) all[name]=true;}); });
    var names=Object.keys(all).sort(function(a,b){
      function mx(name){return Math.max.apply(null,investors.map(function(inv){var r=((inv.sector_alloc||{}).sectors||[]).find(function(x){return(locVal(x.sector)||"")===name;});return r&&r.weight||0;}));}
      return mx(b)-mx(a);
    }).slice(0,14);
    var sec=document.createElement("section");sec.className="inv-compare-section";sec.innerHTML='<h3>'+esc(c.sectors)+'</h3>';
    if(!names.length){sec.innerHTML+='<div class="empty">'+esc(c.noSector)+'</div>';return sec;}
    var rows=names.map(function(name){return[esc(name)].concat(investors.map(function(inv){var r=((inv.sector_alloc||{}).sectors||[]).find(function(x){return(locVal(x.sector)||"")===name;});return pct(r&&r.weight,1);}));});
    rows.push(['<b>'+esc(c.sectorCoverage)+'</b>'].concat(investors.map(function(inv){return pct(inv.sector_alloc&&inv.sector_alloc.covered_pct,1);})));
    sec.appendChild(compareTable([c.sectors].concat(investors.map(function(i){return tickerLabel(i);})),rows));return sec;
  }
  function compareTable(headers,rows){
    var wrap=document.createElement("div");wrap.className="inv-compare-table-wrap";
    wrap.innerHTML='<table class="inv-compare-table"><thead><tr>'+headers.map(function(h){return'<th>'+esc(h)+'</th>';}).join("")+'</tr></thead><tbody>'
      +rows.map(function(r){return'<tr>'+r.map(function(v){return'<td>'+v+'</td>';}).join("")+'</tr>';}).join("")+'</tbody></table>';
    return wrap;
  }

  function renderCompare(list, S, investors){
    ensureSelection(investors);
    var c=C(), chosen=selArray().map(function(slug){return investors.find(function(x){return x.slug===slug;});}).filter(Boolean).slice(0,4);
    if(chosen.length<2){ if(typeof openInvestors==="function") openInvestors(); return; }
    var periods=new Set(chosen.map(function(i){return i.period||"";}));
    var head=document.createElement("div");head.className="series-header sb-header";
    head.innerHTML='<button class="series-close" onclick="openInvestors()">← '+esc(c.edit)+'</button><div class="series-head-name">⇄ '+esc(c.title)+'</div>'
      +'<p class="series-head-desc">'+chosen.map(function(i){return esc(tickerLabel(i));}).join(" · ")+'</p>';
    list.appendChild(head);
    if(periods.size>1){var warn=document.createElement("div");warn.className="inv-period-warning";warn.innerHTML='<b>'+esc(c.mismatch)+'</b><span>'+esc(c.periodWarn)+'</span>';list.appendChild(warn);}
    var grid=document.createElement("div");grid.className="inv-compare-summary-grid";
    var cards=chosen.map(function(inv){var card=summaryCard(inv);grid.appendChild(card);return{inv:inv,card:card};});list.appendChild(grid);
    invMapLimit(cards,2,function(x){return fillPerformance(x.card,x.inv);});
    list.appendChild(overlapSection(chosen)); list.appendChild(topHoldingsSection(chosen)); list.appendChild(sectorSection(chosen));
    var disc=document.createElement("section");disc.className="inv-compare-disclaimer";disc.innerHTML='<b>'+esc(c.discTitle)+'</b><p>'+esc(c.disc)+'</p><p>'+esc(c.discWindow)+'</p>';list.appendChild(disc);
  }

  /* Patch the existing 13F renderers without duplicating their SEC/photo/chart logic. */
  if(typeof window.investorCardEl==="function"){
    var originalCard=window.investorCardEl;
    window.investorCardEl=function(inv,S){var card=originalCard(inv,S);injectTicker(card,inv);return card;};
  }
  if(typeof window.renderInvestorDetail==="function"){
    var originalDetail=window.renderInvestorDetail;
    window.renderInvestorDetail=function(list,S,inv){originalDetail(list,S,inv);var head=list.querySelector(".series-header");injectTicker(head,inv);};
  }
  if(typeof window.renderInvestorsIndex==="function"){
    var originalIndex=window.renderInvestorsIndex;
    window.renderInvestorsIndex=function(list,S,investors){
      originalIndex(list,S,investors);
      var grid=list.querySelector(".inv-grid"); if(grid&&grid.parentNode) grid.parentNode.insertBefore(makePicker(investors),grid);
    };
  }
  window.renderInvestorCompare=renderCompare;
  window.invTickerLabel=tickerLabel;
})();
