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
  var SERIES_P = {};

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
      discTitle:"수익률을 읽는 법", disc:"이 값은 실제 펀드 수익률이 아니라 SEC에 공개된 분기별 13F 스냅샷을 공시일 기준으로 이어 붙인 포트폴리오 추정치입니다. 옵션·공매도·현금·채권·해외 상장 자산은 제외됩니다.",
      discWindow:"3개월·1년 수익률은 각 공시가 공개된 뒤 해당 기간이 실제로 지난 경우에만 표시합니다. 아직 지나지 않았다면 ‘데이터 축적 중’으로 표시해 미래 정보를 미리 쓰지 않습니다.",
      coverage:"시세 {p}%", mismatch:"분기 다름",
      holdGraphTitle:"공개 포트폴리오의 흐름",
      holdGraphSub:"SEC에 공개된 분기별 13F 스냅샷을 공시일마다 이어 붙인 누적 추정 성과입니다. 선택 기간의 시작점을 0%로 맞춘 상대 성과입니다.",
      holdGraphDrag:"차트 위를 손가락으로 누른 채 좌우로 움직이면 선택 기간의 수익률을 확인할 수 있습니다.", holdGraphSelected:"선택 기간", holdGraphRange:"선택 {n}일", holdGraphClear:"선택 해제",
      holdGraphStart:"시작점=0%", holdGraphNow:"현재", holdGraphNoData:"비교할 시세 데이터가 없습니다.",
      holdGraphCoverage:"시세 {p}%", holdGraphNote:"옵션 제외 · SEC 공개 스냅샷 기준 분기별 재구성 · 실제 펀드 수익률 아님",
      holdGraphDays:"경과 {n}일", holdGraphNoPrice:"시세 없음",
      holdGraph1d:"1일", holdGraph5d:"5일", holdGraph1m:"1개월", holdGraph6m:"6개월", holdGraphYtd:"연중"
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
      discTitle:"How to read returns", disc:"These are not actual fund returns. They estimate a public portfolio by chaining quarterly 13F snapshots from each SEC filing date. Options, shorts, cash, bonds and non-U.S.-listed assets are excluded.",
      discWindow:"Three-month and one-year returns appear only after that much time has actually passed since public disclosure. Until then, Stacks shows ‘Building history’ to avoid look-ahead bias.",
      coverage:"Prices {p}%", mismatch:"Different period",
      holdGraphTitle:"Public portfolio path",
      holdGraphSub:"Estimated cumulative performance by chaining quarterly 13F snapshots from each SEC filing date. Each investor starts at 0% for the selected period.",
      holdGraphDrag:"Press and hold, then drag horizontally across the chart to see each investor's return for the selected period.", holdGraphSelected:"Selected period", holdGraphRange:"{n} selected days", holdGraphClear:"Clear selection",
      holdGraphStart:"Start=0%", holdGraphNow:"Now", holdGraphNoData:"There is not enough price data for a comparison chart.",
      holdGraphCoverage:"Prices {p}%", holdGraphNote:"Options excluded · quarterly SEC snapshots chained · not actual fund returns",
      holdGraphDays:"{n} elapsed days", holdGraphNoPrice:"No price data",
      holdGraph1d:"1D", holdGraph5d:"5D", holdGraph1m:"1M", holdGraph6m:"6M", holdGraphYtd:"YTD"
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
      discTitle:"リターンの見方", disc:"これは実際のファンド収益率ではなく、SECに公開された四半期ごとの13Fスナップショットを開示日からつないだ公開ポートフォリオ推定値です。オプション・空売り・現金・債券・米国外上場資産は除外されます。",
      discWindow:"3か月・1年リターンは、公開後にその期間が実際に経過した場合だけ表示します。未経過なら「データ蓄積中」とし、未来情報を先取りしません。",
      coverage:"価格 {p}%", mismatch:"四半期が異なります",
      holdGraphTitle:"公開ポートフォリオの推移",
      holdGraphSub:"SECに公開された四半期ごとの13Fスナップショットを開示日ごとにつないだ累積推定成績です。選択期間の開始点を0%に揃えた相対成績です。",
      holdGraphDrag:"グラフを長押しして左右にドラッグすると、選択した期間の投資家別リターンを確認できます。", holdGraphSelected:"選択期間", holdGraphRange:"選択 {n}日", holdGraphClear:"選択を解除",
      holdGraphStart:"開始点=0%", holdGraphNow:"現在", holdGraphNoData:"比較グラフに使える価格データがありません。",
      holdGraphCoverage:"価格 {p}%", holdGraphNote:"オプション除外・SEC公開スナップショットを四半期ごとに接続・実際のファンド収益率ではありません",
      holdGraphDays:"経過 {n}日", holdGraphNoPrice:"価格データなし",
      holdGraph1d:"1日", holdGraph5d:"5日", holdGraph1m:"1か月", holdGraph6m:"6か月", holdGraphYtd:"年初来"
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

  /* Keep one in-flight promise per investor so the summary cards and the
     comparison chart never request the same portfolio prices twice. */
  function compareSeries(inv){
    var key = (inv && inv.slug || "") + "|" + (inv && inv.filed || "");
    if (!SERIES_P[key]) SERIES_P[key] = invComputeValueSeries(inv);
    return SERIES_P[key];
  }

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
    return Promise.all([compareSeries(inv), quote1y("spy.us").catch(function(){ return null; })]).then(function(rows){
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

  var GRAPH_COLORS = ["#2F80ED", "#12B76A", "#F79009", "#9B51E0"];
  var GRAPH_PERIODS = [
    { key:"1d", days:1, copy:"holdGraph1d" },
    { key:"5d", days:5, copy:"holdGraph5d" },
    { key:"1m", days:30, copy:"holdGraph1m" },
    { key:"6m", days:182, copy:"holdGraph6m" },
    { key:"ytd", ytd:true, copy:"holdGraphYtd" }
  ];
  function graphColor(i){ return GRAPH_COLORS[i % GRAPH_COLORS.length]; }
  function graphPeriodLabel(c, period){ return c[period.copy] || period.key; }
  function normalizeGraphSeries(inv, res){
    /* Keep full quote1y history. filedIdx remains source for filing-based
       summary metrics; graph periods must include prices before disclosure. */
    if (!res || !res.calendar || !res.values || res.calendar.length < 2) return null;
    var start = 0, base = Number(res.values[start]);
    if (!(base > 0)) return null;
    var points = [];
    for (var i = start; i < res.calendar.length; i++){
      var t = Number(res.calendar[i]), v = Number(res.values[i]);
      if (isFinite(t) && isFinite(v) && v > 0) points.push({ t: t, v: (v / base) * 100 });
    }
    if (points.length < 2) return null;
    return { inv: inv, points: points, start: points[0].t, end: points[points.length - 1].t };
  }
  function graphPointAt(points, target){
    if (!points || !points.length) return null;
    var lo = 0, hi = points.length - 1;
    if (target <= points[0].t) return points[0];
    if (target >= points[hi].t) return points[hi];
    while (lo < hi){
      var mid = (lo + hi) >> 1;
      if (points[mid].t < target) lo = mid + 1; else hi = mid;
    }
    var a = points[lo - 1], b = points[lo];
    return Math.abs(a.t - target) <= Math.abs(b.t - target) ? a : b;
  }
  function graphPct(v){
    if (typeof v !== "number" || !isFinite(v)) return "—";
    return (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
  }
  function graphDays(c, elapsed){ return c.holdGraphDays.replace("{n}", Math.max(0, Math.round(elapsed / 86400))); }
  function graphDate(t){
    var d = new Date(Number(t) * 1000), m = d.getUTCMonth() + 1, day = d.getUTCDate(), y = d.getUTCFullYear();
    if (typeof LANG !== "undefined" && LANG === "en"){
      return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m - 1] + " " + day;
    }
    if (typeof LANG !== "undefined" && LANG === "ja") return m + "月" + day + "日";
    return y + "." + String(m).padStart(2,"0") + "." + String(day).padStart(2,"0");
  }
  function graphRangeForSeries(series, a, b, maxElapsed, windowStart){
    var lo = Math.min(a, b), hi = Math.max(a, b);
    var start = graphPointAt(series.points, windowStart + lo * maxElapsed);
    var end = graphPointAt(series.points, windowStart + hi * maxElapsed);
    if (!start || !end || end.t <= start.t || !(start.index > 0)) return null;
    return { start: start, end: end, pct: (end.index / start.index - 1) * 100, days: (end.t - start.t) / 86400 };
  }
  function graphRangeLabel(c, elapsed){ return c.holdGraphRange.replace("{n}", Math.max(1, Math.round(elapsed / 86400))); }
  function graphWindow(period, series){
    var end = Math.min.apply(null, series.map(function(s){ return s.end; }));
    var endDate = new Date(end * 1000), requestedStart;
    if (period.ytd) requestedStart = Date.UTC(endDate.getUTCFullYear(), 0, 1) / 1000;
    else requestedStart = end - period.days * 86400;
    /* Do not leave an empty left half when the selected period begins before
       13F prices become observable. Align all lines to latest common data
       start; the x-axis then describes the range actually drawn. */
    var commonStart = Math.max.apply(null, series.map(function(s){ return s.start; }));
    return { start:Math.max(requestedStart, commonStart), end:end };
  }
  function graphDateAt(start, end, frac){ return graphDate(start + (end - start) * Math.max(0, Math.min(1, frac))); }
  function graphAxisLabels(start, end, H, X){
    var labels = "", count = 4;
    for (var i = 0; i <= count; i++){
      var frac = i / count, anchor = i === 0 ? "start" : i === count ? "end" : "middle";
      labels += '<text x="' + X(frac).toFixed(1) + '" y="' + (H - 9) + '" text-anchor="' + anchor + '" class="inv-compare-axis">' + esc(graphDateAt(start, end, frac)) + '</text>';
    }
    return labels;
  }
  function graphLegend(legend, rows, c){
    legend.innerHTML = rows.map(function(row, i){
      var inv = row.inv, coverage = row.res && typeof row.res.coverage === "number" ? Math.round(row.res.coverage * 100) : null;
      return '<span class="inv-compare-legend-item' + (row.series ? "" : " muted") + '">'
        + '<i style="background:' + graphColor(i) + '"></i><b>' + esc(tickerLabel(inv)) + '</b>'
        + '<span>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</span>'
        + '<small>' + (coverage == null ? esc(c.holdGraphNoPrice) : esc(c.holdGraphCoverage.replace("{p}", coverage))) + '</small></span>';
    }).join("");
  }
  function paintCompareGraph(chart, legend, rows, c, period, clearBtn, rangeReadout){
    if (clearBtn) clearBtn.hidden = true;
    if (rangeReadout) rangeReadout.hidden = true;
    graphLegend(legend, rows, c);
    var fullSeries = rows.map(function(row){ return row.series; }).filter(Boolean);
    if (!fullSeries.length){ chart.innerHTML = '<div class="inv-compare-chart-empty">' + esc(c.holdGraphNoData) + '</div>'; return; }
    var window = graphWindow(period, fullSeries), windowStart = window.start, windowEnd = window.end;
    var maxElapsed = windowEnd - windowStart;
    if (!(maxElapsed > 0)){ chart.innerHTML = '<div class="inv-compare-chart-empty">' + esc(c.holdGraphNoData) + '</div>'; return; }
    var series = fullSeries.map(function(s, i){
      var first = graphPointAt(s.points, windowStart), last = graphPointAt(s.points, windowEnd);
      if (!first || !last || last.t <= first.t || !(first.v > 0)) return null;
      var points = s.points.filter(function(p){ return p.t >= first.t && p.t <= last.t; });
      if (!points.length || points[0].t !== first.t) points.unshift(first);
      if (points[points.length - 1].t !== last.t) points.push(last);
      return { inv:s.inv, points:points.map(function(p){ var index = (p.v / first.v) * 100; return { t:p.t, v:index - 100, index:index }; }), start:first.t, end:last.t, color:graphColor(i) };
    }).filter(Boolean);
    if (!series.length){ chart.innerHTML = '<div class="inv-compare-chart-empty">' + esc(c.holdGraphNoData) + '</div>'; return; }
    var all = [0]; series.forEach(function(s){ s.points.forEach(function(p){ all.push(p.v); }); });
    var mn = Math.min.apply(null, all), mx = Math.max.apply(null, all), span = mx - mn;
    if (span < 8){ var center = (mn + mx) / 2; mn = center - 5; mx = center + 5; }
    else { mn -= span * .08; mx += span * .08; }
    var W = 960, H = 310, pL = 88, pR = 22, pT = 18, pB = 34, pw = W - pL - pR, ph = H - pT - pB;
    function X(frac){ return pL + Math.max(0, Math.min(1, frac)) * pw; }
    function Y(v){ return pT + (1 - (v - mn) / (mx - mn)) * ph; }
    var grid = "", ylab = "";
    for (var g = 0; g <= 4; g++){
      var yv = mn + ((mx - mn) * g) / 4, yy = Y(yv);
      grid += '<line x1="' + pL + '" y1="' + yy.toFixed(1) + '" x2="' + (pL + pw) + '" y2="' + yy.toFixed(1) + '" class="inv-compare-grid"/>';
      ylab += '<text x="' + (pL - 8) + '" y="' + (yy + 4).toFixed(1) + '" text-anchor="end" class="inv-compare-axis">' + Math.round(yv) + '%</text>';
    }
    var baseY = Y(0);
    var lines = series.map(function(s){
      var pts = s.points.map(function(p){ return X((p.t - windowStart) / maxElapsed).toFixed(1) + "," + Y(p.v).toFixed(1); }).join(" ");
      return '<polyline points="' + pts + '" fill="none" stroke="' + s.color + '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>';
    }).join("");
    chart.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="100%" role="img" aria-label="' + esc(c.holdGraphSub) + '">'
      + grid + '<rect class="inv-compare-selection" y="' + pT + '" height="' + ph + '" visibility="hidden"/> '
      + '<line x1="' + pL + '" y1="' + baseY.toFixed(1) + '" x2="' + (pL + pw) + '" y2="' + baseY.toFixed(1) + '" class="inv-compare-baseline"/>'
      + lines + ylab
      + graphAxisLabels(windowStart, windowEnd, H, X)
      + '<line class="inv-compare-hover-line" y1="' + pT + '" y2="' + (pT + ph) + '" visibility="hidden"/>'
      + '<line class="inv-compare-hover-line inv-compare-hover-hline" x1="' + pL + '" x2="' + (pL + pw) + '" visibility="hidden"/>'
      + series.map(function(s){ return '<circle class="inv-compare-hover-dot" data-color="' + s.color + '" r="4" fill="' + s.color + '" visibility="hidden"/>'; }).join("")
      + '</svg><div class="inv-compare-chart-tip" hidden></div>';
    var svg = chart.querySelector("svg"), tip = chart.querySelector(".inv-compare-chart-tip"), hover = chart.querySelector(".inv-compare-hover-line"), hoverH = chart.querySelector(".inv-compare-hover-hline"), selectionRect = chart.querySelector(".inv-compare-selection"), dots = Array.prototype.slice.call(chart.querySelectorAll(".inv-compare-hover-dot"));
    var selection = null, dragging = false, dragStart = 0;
    function hideHover(){
      hover.setAttribute("visibility", "hidden"); hoverH.setAttribute("visibility", "hidden"); dots.forEach(function(d){ d.setAttribute("visibility", "hidden"); });
      if (!selection) tip.hidden = true;
    }
    function leave(){ if (!dragging && !selection) hideHover(); else if (!dragging) hideHover(); }
    function fracAt(ev){
      var rect = svg.getBoundingClientRect(), frac = (ev.clientX - rect.left) / rect.width;
      frac = Math.max(0, Math.min(1, (frac * W - pL) / pw));
      return frac;
    }
    function placeTip(frac){
      var host = chart.clientWidth || 0, tipWidth = tip.offsetWidth || 132;
      if (!host) return;
      var half = Math.min(tipWidth / 2 + 6, Math.max(10, host / 2 - 4));
      var center = host * Math.max(0, Math.min(1, frac));
      center = Math.max(half, Math.min(host - half, center));
      tip.style.left = center.toFixed(1) + "px";
    }
    function move(ev){
      var frac = fracAt(ev);
      var elapsed = frac * maxElapsed, x = X(frac);
      hideHover();
      hover.setAttribute("x1", x.toFixed(1)); hover.setAttribute("x2", x.toFixed(1)); hover.setAttribute("visibility", "visible");
      var html = '<b>' + esc(graphDays(c, elapsed)) + '</b>';
      var hoverY = null;
      series.forEach(function(s, i){
        var target = windowStart + elapsed;
        if (target < s.start - 86400 || target > s.end + 86400){ dots[i].setAttribute("visibility", "hidden"); return; }
        var p = graphPointAt(s.points, target);
        if (!p) return;
        dots[i].setAttribute("cx", X((p.t - windowStart) / maxElapsed).toFixed(1)); dots[i].setAttribute("cy", Y(p.v).toFixed(1)); dots[i].setAttribute("visibility", "visible");
        if (hoverY == null) hoverY = Y(p.v);
        html += '<span><i style="background:' + s.color + '"></i>' + esc(tickerLabel(s.inv)) + ' <b>' + esc(graphPct(p.v)) + '</b></span>';
      });
      if (hoverY != null){ hoverH.setAttribute("y1", hoverY.toFixed(1)); hoverH.setAttribute("y2", hoverY.toFixed(1)); hoverH.setAttribute("visibility", "visible"); }
      tip.innerHTML = html; tip.hidden = false; placeTip(x / W);
    }
    function rangePct(v){ return typeof v === "number" && isFinite(v) ? (v >= 0 ? "+" : "") + v.toFixed(1) + "%" : "—"; }
    function showSelection(a, b){
      var lo = Math.min(a, b), hi = Math.max(a, b), x1 = X(lo), x2 = X(hi);
      selectionRect.setAttribute("x", x1.toFixed(1)); selectionRect.setAttribute("width", Math.max(1, x2 - x1).toFixed(1)); selectionRect.setAttribute("visibility", "visible");
      hideHover();
      var startLabel = graphDateAt(windowStart, windowEnd, lo), endLabel = graphDateAt(windowStart, windowEnd, hi);
      var rangeText = startLabel + ' – ' + endLabel;
      if (rangeReadout){ rangeReadout.textContent = rangeText; rangeReadout.hidden = false; }
      var html = '<b>' + esc(rangeText) + '</b><small>' + esc(c.holdGraphSelected) + ' · ' + esc(graphRangeLabel(c, (hi - lo) * maxElapsed)) + '</small>';
      var any = false;
      series.forEach(function(s){
        var r = graphRangeForSeries(s, lo, hi, maxElapsed, windowStart);
        if (!r){ html += '<span><i style="background:' + s.color + '"></i>' + esc(tickerLabel(s.inv)) + ' <b>—</b></span>'; return; }
        any = true;
        html += '<span><i style="background:' + s.color + '"></i>' + esc(tickerLabel(s.inv)) + ' <b>' + esc(rangePct(r.pct)) + '</b></span>';
      });
      if (!any) html += '<span>' + esc(c.holdGraphNoData) + '</span>';
      tip.innerHTML = html; tip.hidden = false; placeTip(((x1 + x2) / 2) / W);
      if (clearBtn) clearBtn.hidden = false;
    }
    function clearSelection(){
      selection = null; selectionRect.setAttribute("visibility", "hidden"); if (clearBtn) clearBtn.hidden = true; if (rangeReadout) rangeReadout.hidden = true; hideHover();
    }
    function startDrag(ev){
      if (ev.button != null && ev.button !== 0) return;
      dragging = true; dragStart = fracAt(ev); selection = null; if (clearBtn) clearBtn.hidden = true;
      try { svg.setPointerCapture(ev.pointerId); } catch(e) {}
      showSelection(dragStart, dragStart); ev.preventDefault();
    }
    function dragMove(ev){ if (dragging) { showSelection(dragStart, fracAt(ev)); ev.preventDefault(); } else move(ev); }
    function endDrag(ev){
      if (!dragging) return;
      ev.preventDefault();
      var end = fracAt(ev), distance = Math.abs(end - dragStart); dragging = false;
      try { svg.releasePointerCapture(ev.pointerId); } catch(e) {}
      if (distance < 0.008){ clearSelection(); move(ev); return; }
      selection = { a: Math.min(dragStart, end), b: Math.max(dragStart, end) }; showSelection(selection.a, selection.b);
    }
    svg.addEventListener("pointerdown", startDrag);
    svg.addEventListener("pointermove", dragMove);
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointercancel", function(){ if (dragging){ dragging = false; clearSelection(); } });
    svg.addEventListener("pointerleave", leave);
    svg.addEventListener("dblclick", clearSelection);
    svg.addEventListener("contextmenu", function(ev){ ev.preventDefault(); });
    if (clearBtn) clearBtn.onclick = clearSelection;
  }
  function compareGraphSection(investors){
    var c = C(), sec = document.createElement("section"); sec.className = "inv-performance-section";
    var periodButtons = GRAPH_PERIODS.map(function(period){
      var active = period.key === "ytd";
      return '<button type="button" role="tab" aria-selected="' + (active ? "true" : "false") + '" class="inv-compare-period' + (active ? " on" : "") + '" data-period="' + period.key + '">' + esc(graphPeriodLabel(c, period)) + '</button>';
    }).join("");
    sec.innerHTML = '<div class="inv-performance-head"><h3>' + esc(c.holdGraphTitle) + '</h3><p>' + esc(c.holdGraphSub) + '</p><small class="inv-compare-drag-hint">' + esc(c.holdGraphDrag) + '</small></div>'
      + '<div class="inv-compare-periods" role="tablist" aria-label="' + esc(c.holdGraphTitle) + '">' + periodButtons + '</div>'
      + '<div class="inv-compare-chart"><div class="ehq-loading">···</div></div><div class="inv-compare-selection-label" aria-live="polite" hidden></div><div class="inv-compare-legend"></div><button type="button" class="inv-compare-clear" hidden>' + esc(c.holdGraphClear) + '</button><p class="inv-compare-note">' + esc(c.holdGraphNote) + '</p>';
    var chart = sec.querySelector(".inv-compare-chart"), legend = sec.querySelector(".inv-compare-legend"), clearBtn = sec.querySelector(".inv-compare-clear"), rangeReadout = sec.querySelector(".inv-compare-selection-label"), rows = null, activePeriod = "ytd";
    sec.querySelectorAll(".inv-compare-period").forEach(function(button){
      button.addEventListener("click", function(){
        activePeriod = button.getAttribute("data-period") || "ytd";
        sec.querySelectorAll(".inv-compare-period").forEach(function(other){ var on = other === button; other.classList.toggle("on", on); other.setAttribute("aria-selected", on ? "true" : "false"); });
        if (rows) paintCompareGraph(chart, legend, rows, c, GRAPH_PERIODS.find(function(period){ return period.key === activePeriod; }) || GRAPH_PERIODS[4], clearBtn, rangeReadout);
      });
    });
    invMapLimit(investors, 2, function(inv){ return compareSeries(inv).then(function(res){ return { inv: inv, res: res, series: normalizeGraphSeries(inv, res) }; }).catch(function(){ return { inv: inv, res: null, series: null }; }); })
      .then(function(result){ rows = result; if (sec.isConnected) paintCompareGraph(chart, legend, rows, c, GRAPH_PERIODS.find(function(period){ return period.key === activePeriod; }) || GRAPH_PERIODS[4], clearBtn, rangeReadout); });
    return sec;
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
    var wrap=document.createElement("div");wrap.className="inv-compare-table-wrap"+(headers[0]==="#"?" inv-top-holdings-table":"");
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
    list.appendChild(compareGraphSection(chosen));
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
