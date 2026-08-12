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
  var MAX_COMPARE = 4;
  var selected = null;
  var SERIES_P = {};
  /* Observes .inv-compare-entry so the fixed bottom bar (renderCompareBar)
     can hide itself while the inline CTA is already on screen. Rebuilt on
     every renderCompareBar() call, so the previous instance is disconnected
     first. */
  var compareBarEntryObserver = null;

  var COPY = {
    ko:{
      tickerHelp:"Stacks 투자자 티커", pickTitle:"투자자 비교", pickSub:"2~4명을 골라 포트폴리오를 나란히 비교하세요.",
      compare:"선택한 투자자 비교", selected:"{n}명 선택", min:"2명 이상 선택하세요.", max:"최대 4명까지 비교할 수 있어요.", swapped:"최대 4명이라 오래된 선택을 교체했어요: {out} → {in}",
      search:"투자자, 운용사, 티커 검색", openPortfolio:"포트폴리오 보기", addCompare:"+ 비교 추가", inCompare:"✓ 비교 중", fullCompare:"최대 4명",
      entrySub:"보유종목·섹터·공개 포트폴리오 흐름을 같은 화면에서 비교합니다.", oneMore:"한 명 더 고르면 비교할 수 있어요.", ready:"보유종목과 수익률을 나란히 봅니다.",
      topHolding:"상위 보유", snapshot:"이번 스냅샷", read13f:"13F 읽는 법", read13fSub:"분기 말 미국 상장 롱 포지션을 최대 45일 뒤 공개합니다.",
      read13f1:"현금·공매도·채권 제외", read13f2:"실제 매수가격은 알 수 없음", read13f3:"같은 기준일끼리 비교", investorsLabel:"투자자", periodLabel:"기준", sourceLabel:"출처", railEmpty:"투자자 카드에서 비교에 추가하세요.", nextFiling:"다음 공시", nextFilingRow:"{date} (D-{n})", nextFilingToday:"{date} (D-DAY)", nextFilingWaiting:"공시 접수 중 · 반영 대기",
      title:"투자자 포트폴리오 비교", edit:"선택 바꾸기", periodWarn:"기준 분기가 다른 투자자가 포함돼 있습니다. 수익률과 보유 비중을 같은 시점의 성과처럼 직접 비교하지 마세요.",
      reported:"13F 기준", total:"공개 평가액", holdings:"보유 종목", top5:"상위 5종목", turnover:"회전율", changes:"분기 변화",
      since:"공시 후", threeM:"최근 3개월", oneY:"최근 1년", vsSpy:"S&P 500 대비", loading:"계산 중", building:"데이터 축적 중",
      overlap:"함께 보유한 종목", overlapSub:"선택한 투자자 중 2명 이상이 함께 보유한 미국 상장 롱 포지션입니다.", noOverlap:"겹치는 종목이 없습니다.", heldBy:"{n}명 보유",
      topHoldings:"상위 보유종목 비교", sectors:"섹터 비중 비교", sectorCoverage:"분류 커버리지", noSector:"분류된 섹터 데이터가 없습니다.",
      sectorUnclassified:"미분류", sectorUnclassifiedNote:"{ticker}: 공개 평가액의 {covered}만 분류된 결과입니다 · 나머지 {uncovered}는 미분류입니다.", sectorUnclassifiedUnknown:"{ticker}: 분류 커버리지 데이터가 없어 미분류 비율을 알 수 없습니다.",
      weight:"비중", newBuy:"신규", add:"추가", trim:"축소", exit:"청산",
      discTitle:"수익률을 읽는 법", disc:"이 값은 실제 펀드 수익률이 아니라 SEC에 공개된 분기별 13F 스냅샷을 공시일 기준으로 이어 붙인 포트폴리오 추정치입니다. 옵션·공매도·현금·채권·해외 상장 자산은 제외됩니다.",
      discWindow:"3개월·1년 수익률은 각 공시가 공개된 뒤 해당 기간이 실제로 지난 경우에만 표시합니다. 아직 지나지 않았다면 ‘데이터 축적 중’으로 표시해 미래 정보를 미리 쓰지 않습니다.",
      coverage:"시세 {p}%", priceUnavailable:"시세 조회 실패", pricePartial:"시세 부분 연결 {p}% · 일부 종목 제외", benchmarkUnavailable:"S&P 500 시세 조회 실패", mismatch:"분기 다름",
      holdGraphTitle:"그대로 들고 있었다면",
      holdGraphSub:"SEC에 공개된 분기별 13F 스냅샷을 공시일마다 이어 붙인 누적 추정 성과입니다. 선택 기간의 시작점을 0%로 맞춘 상대 성과입니다.",
      holdGraphDrag:"차트 위를 손가락으로 누른 채 좌우로 움직이면 선택 기간의 수익률을 확인할 수 있습니다.", holdGraphSelected:"선택 기간", holdGraphRange:"선택 {n}일", holdGraphClear:"선택 해제",
      holdGraphStart:"시작점=0%", holdGraphNow:"현재", holdGraphNoData:"비교 가능한 시세 데이터가 부족합니다.",
      holdGraphCoverage:"시세 {p}%", holdGraphNote:"SEC 공개 스냅샷 기준 분기별 재구성 · 실제 펀드 수익률 아님", holdGraphNoteMore:"제외 항목 전체 보기",
      holdGraphDays:"경과 {n}일", holdGraphNoPrice:"시세 조회 실패", benchmark:"S&P 500 비교", benchmarkNote:"기준지수",
      holdGraph1d:"1일", holdGraph5d:"5일", holdGraph1m:"1개월", holdGraph3m:"3개월", holdGraph6m:"6개월", holdGraphYtd:"연중", holdGraph1y:"1년",
      holdGraphHeroLabel:"{period} 수익률",
      ytdReturn:"연중 수익률", ytdReturnCoverage:"분류·시세 확보 {p}% — 수치를 내기에 부족합니다",
      ytdReturnNote:"연중 수익률은 마지막 공시 보유를 그대로 들고 있었다고 가정한 추정치이며 실제 펀드 수익률이 아닙니다. 산정 시작 {start} · 갱신 {asOf}.",
      ytdReturnUnavailable:"연중 수익률 데이터를 최신 상태로 불러오지 못해 이 열은 표시하지 않습니다."
    },
    en:{
      tickerHelp:"Stacks investor ticker", pickTitle:"Compare investors", pickSub:"Choose 2–4 investors to compare their public portfolios side by side.",
      compare:"Compare selected", selected:"{n} selected", min:"Select at least two investors.", max:"You can compare up to four investors.", swapped:"Four is the limit, so the oldest pick was replaced: {out} → {in}",
      search:"Search investor, firm or ticker", openPortfolio:"View portfolio", addCompare:"+ Add to compare", inCompare:"✓ Comparing", fullCompare:"Max 4",
      entrySub:"Compare holdings, sectors and public-portfolio paths in one place.", oneMore:"Choose one more investor to compare.", ready:"Compare holdings and returns side by side.",
      topHolding:"Top holding", snapshot:"This snapshot", read13f:"How to read 13F", read13fSub:"U.S.-listed long positions are disclosed up to 45 days after quarter-end.",
      read13f1:"Excludes cash, shorts and bonds", read13f2:"Actual purchase prices are unknown", read13f3:"Compare matching report dates", investorsLabel:"Investors", periodLabel:"As of", sourceLabel:"Source", railEmpty:"Add investors from a portfolio card.", nextFiling:"Next filing", nextFilingRow:"{date} (D-{n})", nextFilingToday:"{date} (D-DAY)", nextFilingWaiting:"Filing pending · not yet reflected",
      title:"Investor portfolio comparison", edit:"Change selection", periodWarn:"The selection includes different reporting periods. Do not read returns and weights as same-date results.",
      reported:"13F period", total:"Reported value", holdings:"Holdings", top5:"Top-5 weight", turnover:"Turnover", changes:"Quarterly changes",
      since:"Since filing", threeM:"Last 3 months", oneY:"Last year", vsSpy:"vs. S&P 500", loading:"Calculating", building:"Building history",
      overlap:"Shared holdings", overlapSub:"U.S.-listed long positions held by at least two selected investors.", noOverlap:"No shared holdings.", heldBy:"Held by {n}",
      topHoldings:"Top holdings comparison", sectors:"Sector allocation comparison", sectorCoverage:"Classification coverage", noSector:"No classified sector data.",
      sectorUnclassified:"Unclassified", sectorUnclassifiedNote:"{ticker}: This reflects only {covered} of disclosed value classified · the remaining {uncovered} is unclassified.", sectorUnclassifiedUnknown:"{ticker}: Classification coverage is unknown, so the unclassified share cannot be shown.",
      weight:"Weight", newBuy:"New", add:"Added", trim:"Trimmed", exit:"Exited",
      discTitle:"How to read returns", disc:"These are not actual fund returns. They estimate a public portfolio by chaining quarterly 13F snapshots from each SEC filing date. Options, shorts, cash, bonds and non-U.S.-listed assets are excluded.",
      discWindow:"Three-month and one-year returns appear only after that much time has actually passed since public disclosure. Until then, Stacks shows ‘Building history’ to avoid look-ahead bias.",
      coverage:"Prices {p}%", priceUnavailable:"Price data unavailable", pricePartial:"Partial price coverage: {p}% · some holdings excluded", benchmarkUnavailable:"S&P 500 price data unavailable", mismatch:"Different period",
      holdGraphTitle:"If you held it",
      holdGraphSub:"Estimated cumulative performance by chaining quarterly 13F snapshots from each SEC filing date. Each investor starts at 0% for the selected period.",
      holdGraphDrag:"Press and hold, then drag horizontally across the chart to see each investor's return for the selected period.", holdGraphSelected:"Selected period", holdGraphRange:"{n} selected days", holdGraphClear:"Clear selection",
      holdGraphStart:"Start=0%", holdGraphNow:"Now", holdGraphNoData:"There is not enough price data for a comparison chart.",
      holdGraphCoverage:"Prices {p}%", holdGraphNote:"Quarterly SEC snapshots chained · not actual fund returns", holdGraphNoteMore:"See full exclusions",
      holdGraphDays:"{n} elapsed days", holdGraphNoPrice:"Price data unavailable", benchmark:"Compare S&P 500", benchmarkNote:"Benchmark",
      holdGraph1d:"1D", holdGraph5d:"5D", holdGraph1m:"1M", holdGraph3m:"3M", holdGraph6m:"6M", holdGraphYtd:"YTD", holdGraph1y:"1Y",
      holdGraphHeroLabel:"{period} return",
      ytdReturn:"YTD return", ytdReturnCoverage:"Classification/price coverage {p}% — not enough to compute a number",
      ytdReturnNote:"This YTD return assumes the investor held their last disclosed 13F positions unchanged; it is not an actual fund return. Estimation window starts {start} · updated {asOf}.",
      ytdReturnUnavailable:"YTD return data could not be loaded up to date, so this column is not shown."
    },
    ja:{
      tickerHelp:"Stacks投資家ティッカー", pickTitle:"投資家を比較", pickSub:"2〜4人を選び、公開ポートフォリオを横並びで比較します。",
      compare:"選択した投資家を比較", selected:"{n}人選択", min:"2人以上選択してください。", max:"比較できるのは最大4人です。", swapped:"最大4人のため、最も古い選択を入れ替えました: {out} → {in}",
      search:"投資家・運用会社・ティッカーを検索", openPortfolio:"ポートフォリオを見る", addCompare:"+ 比較に追加", inCompare:"✓ 比較中", fullCompare:"最大4人",
      entrySub:"保有銘柄・セクター・公開ポートフォリオの推移を同じ画面で比較します。", oneMore:"もう1人選ぶと比較できます。", ready:"保有銘柄とリターンを横並びで比較します。",
      topHolding:"最大保有", snapshot:"今回のスナップショット", read13f:"13Fの見方", read13fSub:"四半期末の米国上場ロングポジションを最大45日後に開示します。",
      read13f1:"現金・空売り・債券は対象外", read13f2:"実際の買付価格は不明", read13f3:"同じ基準日同士で比較", investorsLabel:"投資家", periodLabel:"基準", sourceLabel:"出典", railEmpty:"投資家カードから比較に追加してください。", nextFiling:"次回開示", nextFilingRow:"{date}（D-{n}）", nextFilingToday:"{date}（D-DAY）", nextFilingWaiting:"開示受付中・反映待ち",
      title:"投資家ポートフォリオ比較", edit:"選択を変更", periodWarn:"基準四半期が異なる投資家が含まれています。リターンや比率を同一時点の成績として直接比較しないでください。",
      reported:"13F基準", total:"公開評価額", holdings:"保有銘柄", top5:"上位5銘柄", turnover:"回転率", changes:"四半期変化",
      since:"開示後", threeM:"直近3か月", oneY:"直近1年", vsSpy:"S&P 500比", loading:"計算中", building:"データ蓄積中",
      overlap:"共通保有銘柄", overlapSub:"選択した投資家のうち2人以上が保有する米国上場ロングポジションです。", noOverlap:"共通銘柄はありません。", heldBy:"{n}人保有",
      topHoldings:"上位保有銘柄比較", sectors:"セクター比率比較", sectorCoverage:"分類カバレッジ", noSector:"分類済みセクターデータがありません。",
      sectorUnclassified:"未分類", sectorUnclassifiedNote:"{ticker}：公開評価額のうち{covered}のみ分類された結果です・残り{uncovered}は未分類です。", sectorUnclassifiedUnknown:"{ticker}：分類カバレッジのデータがなく、未分類の割合は不明です。",
      weight:"比率", newBuy:"新規", add:"追加", trim:"縮小", exit:"清算",
      discTitle:"リターンの見方", disc:"これは実際のファンド収益率ではなく、SECに公開された四半期ごとの13Fスナップショットを開示日からつないだ公開ポートフォリオ推定値です。オプション・空売り・現金・債券・米国外上場資産は除外されます。",
      discWindow:"3か月・1年リターンは、公開後にその期間が実際に経過した場合だけ表示します。未経過なら「データ蓄積中」とし、未来情報を先取りしません。",
      coverage:"価格 {p}%", priceUnavailable:"価格データを取得できません", pricePartial:"価格データ一部取得 {p}%・一部銘柄を除外", benchmarkUnavailable:"S&P 500の価格データを取得できません", mismatch:"四半期が異なります",
      holdGraphTitle:"そのまま保有していたら",
      holdGraphSub:"SECに公開された四半期ごとの13Fスナップショットを開示日ごとにつないだ累積推定成績です。選択期間の開始点を0%に揃えた相対成績です。",
      holdGraphDrag:"グラフを長押しして左右にドラッグすると、選択した期間の投資家別リターンを確認できます。", holdGraphSelected:"選択期間", holdGraphRange:"選択 {n}日", holdGraphClear:"選択を解除",
      holdGraphStart:"開始点=0%", holdGraphNow:"現在", holdGraphNoData:"比較グラフに使える価格データがありません。",
      holdGraphCoverage:"価格 {p}%", holdGraphNote:"SEC公開スナップショットを四半期ごとに接続・実際のファンド収益率ではありません", holdGraphNoteMore:"除外項目をすべて見る",
      holdGraphDays:"経過 {n}日", holdGraphNoPrice:"価格データを取得できません", benchmark:"S&P 500と比較", benchmarkNote:"ベンチマーク",
      holdGraph1d:"1日", holdGraph5d:"5日", holdGraph1m:"1か月", holdGraph3m:"3か月", holdGraph6m:"6か月", holdGraphYtd:"年初来", holdGraph1y:"1年",
      holdGraphHeroLabel:"{period}のリターン",
      ytdReturn:"年初来リターン", ytdReturnCoverage:"分類・価格確保 {p}% — 数値を算出するには不十分です",
      ytdReturnNote:"年初来リターンは最後に開示された保有をそのまま継続保有したと仮定した推定値であり、実際のファンド収益率ではありません。起算日 {start}・更新 {asOf}。",
      ytdReturnUnavailable:"年初来リターンのデータを最新の状態で取得できなかったため、この列は表示していません。"
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
      selected = new Set((Array.isArray(saved) ? saved : []).filter(function(s){ return valid.has(s); }).slice(0,MAX_COMPARE));
      if (selected.size < 2){
        selected = new Set(["berkshire","pershing-square"].filter(function(s){ return valid.has(s); }));
      }
    } else {
      selected = new Set(selArray().filter(function(s){ return valid.has(s); }).slice(0,MAX_COMPARE));
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
    names.appendChild(document.createTextNode(" "));
    names.appendChild(t);
  }

  function chosenInvestors(investors){
    return selArray().map(function(slug){ return investors.find(function(inv){ return inv.slug === slug; }); }).filter(Boolean).slice(0,MAX_COMPARE);
  }
  function topHolding(inv){
    return holdings(inv).slice().sort(function(a,b){ return (b.weight || 0) - (a.weight || 0); })[0] || null;
  }
  function holdingTicker(holding){
    return String((holding && (holding.ticker || holding.issuer)) || "—").replace(/\.us$/i, "").toUpperCase();
  }
  function shortInitial(inv){
    var raw = locVal(inv && inv.manager) || locVal(inv && inv.name) || (inv && inv.slug) || "?";
    try { return typeof initial === "function" ? initial(raw) : raw.trim().slice(0,2).toUpperCase(); }
    catch(e){ return raw.trim().slice(0,2).toUpperCase(); }
  }
  function goCompare(message){
    if (selected.size < 2){ if (message) message.textContent = C().min; return; }
    if (typeof openInvestor === "function") openInvestor("compare");
  }
  function investorLabel(slug, investors){
    var inv = (investors || []).find(function(i){ return i.slug === slug; });
    return inv ? (locVal(inv.manager) || locVal(inv.name) || inv.slug) : slug;
  }
  function toggleSelection(slug, investors, message){
    var swappedOut = null;
    if (selected.has(slug)) selected.delete(slug);
    else {
      if (selected.size >= MAX_COMPARE){ swappedOut = selected.values().next().value; selected.delete(swappedOut); }
      selected.add(slug);
    }
    saveSelection();
    if (message) message.textContent = swappedOut ? C().swapped.replace("{out}", investorLabel(swappedOut, investors)).replace("{in}", investorLabel(slug, investors)) : "";
    syncSelection(investors);
    return true;
  }
  function selectionLabel(button, on){
    var c = C();
    button.textContent = on ? c.inCompare : c.addCompare;
    button.classList.toggle("on", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function renderCompareBar(investors){
    var old = document.querySelector(".inv-compare-bar"); if (old) old.remove();
    if (compareBarEntryObserver){ compareBarEntryObserver.disconnect(); compareBarEntryObserver = null; }
    if ((typeof INVESTOR_VIEW === "undefined" ? null : INVESTOR_VIEW) !== "index" || !selected.size) return;
    var c = C(), chosen = chosenInvestors(investors), list = document.getElementById("feedList");
    if (!list || !chosen.length) return;
    var bar = document.createElement("aside"); bar.className = "inv-compare-bar"; bar.setAttribute("aria-label", c.pickTitle);
    var avatars = document.createElement("div"); avatars.className = "inv-compare-bar-avatars";
    chosen.forEach(function(inv, i){
      var b = document.createElement("button"); b.type = "button"; b.title = (locVal(inv.manager) || locVal(inv.name) || inv.slug) + " ×";
      b.innerHTML = '<span>' + esc(shortInitial(inv)) + '</span><i style="background:' + graphColor(i) + '"></i>';
      b.addEventListener("click", function(){ toggleSelection(inv.slug, investors); }); avatars.appendChild(b);
    });
    var copy = document.createElement("div"); copy.className = "inv-compare-bar-copy";
    copy.innerHTML = '<b>' + esc(c.selected.replace("{n}", selected.size)) + '</b><span>' + esc(selected.size < 2 ? c.oneMore : c.ready) + '</span>';
    var go = document.createElement("button"); go.type = "button"; go.className = "inv-bar-go"; go.textContent = c.compare; go.disabled = selected.size < 2; go.addEventListener("click", function(){ goCompare(); });
    bar.appendChild(avatars); bar.appendChild(copy); bar.appendChild(go); list.appendChild(bar);
    /* Default is visible. Only an actual "the inline CTA is on screen"
       callback may hide it - if IntersectionObserver is missing, or the
       callback simply never fires (backgrounded tabs have a documented
       history of never running rAF/paint work here), the bar stays usable. */
    var entry = document.querySelector(".inv-compare-entry");
    if (entry && typeof IntersectionObserver === "function"){
      compareBarEntryObserver = new IntersectionObserver(function(entries){
        var hit = entries[entries.length - 1];
        bar.classList.toggle("inv-compare-bar-idle", !!(hit && hit.isIntersecting));
      });
      compareBarEntryObserver.observe(entry);
    }
  }
  /* Freshness row (2026-08-10). entity13fFreshness() (index.html) already turns a
     period into the SEC due date (quarter-end + 45d) - reused, not reimplemented.
     D-day is re-measured in UTC so the label does not drift near local midnight. */
  function invLatestPeriod(investors){
    var latest = "";
    (investors || []).forEach(function(inv){ var p = String(inv && inv.period || ""); if (p > latest) latest = p; });
    return latest;
  }
  function invNextFilingRowHtml(investors, c){
    try {
      var freshness = (typeof entity13fFreshness === "function") ? entity13fFreshness(invLatestPeriod(investors)) : null;
      if (!freshness || !freshness.due) return "";
      var due = freshness.due, dueUTC = Date.UTC(due.getFullYear(), due.getMonth(), due.getDate());
      var now = new Date(), todayUTC = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
      var diffDays = Math.round((dueUTC - todayUTC) / 86400000);
      var dueIso = due.getFullYear() + "-" + String(due.getMonth() + 1).padStart(2, "0") + "-" + String(due.getDate()).padStart(2, "0");
      var dueLabel = invFmtDate(dueIso), text;
      if (diffDays < 0) text = c.nextFilingWaiting;
      else if (diffDays === 0) text = c.nextFilingToday.replace("{date}", dueLabel);
      else text = c.nextFilingRow.replace("{date}", dueLabel).replace("{n}", diffDays);
      return '<div><dt>' + esc(c.nextFiling) + '</dt><dd>' + esc(text) + '</dd></div>';
    } catch (e) { return ""; }
  }
  function renderInvestorRail(investors){
    var rail = document.getElementById("v83rail"); if (!rail) return;
    var old = rail.querySelector(".inv-lab-rail"); if (old) old.remove();
    if (typeof invViewActive === "function" && !invViewActive()) return;
    var c = C(), chosen = chosenInvestors(investors), wrap = document.createElement("div"); wrap.className = "inv-lab-rail";
    var pick = document.createElement("section"); pick.className = "inv-rail-card inv-rail-selection";
    pick.innerHTML = '<h2>' + esc(c.pickTitle) + '<small>' + selected.size + '/' + MAX_COMPARE + '</small></h2><div class="inv-rail-rows"></div>';
    var rows = pick.querySelector(".inv-rail-rows");
    if (!chosen.length){ var empty = document.createElement("p"); empty.textContent = c.railEmpty; rows.appendChild(empty); }
    chosen.forEach(function(inv, i){
      var row = document.createElement("div"); row.className = "inv-rail-row";
      var open = document.createElement("button"); open.type = "button"; open.className = "inv-rail-open";
      open.innerHTML = '<i style="background:' + graphColor(i) + '"></i><span><b>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</b><small>' + esc(tickerLabel(inv)) + '</small></span>';
      open.addEventListener("click", function(){ if (typeof openInvestor === "function") openInvestor(inv.slug); });
      var remove = document.createElement("button"); remove.type = "button"; remove.className = "inv-rail-remove"; remove.textContent = "×"; remove.setAttribute("aria-label", (locVal(inv.manager) || inv.slug) + " ×");
      remove.addEventListener("click", function(){
        toggleSelection(inv.slug, investors);
        if ((typeof INVESTOR_VIEW === "undefined" ? null : INVESTOR_VIEW) === "compare"){
          if (selected.size < 2 && typeof openInvestors === "function") openInvestors();
          else if (typeof renderFeed === "function") renderFeed(false);
        }
      });
      row.appendChild(open); row.appendChild(remove); rows.appendChild(row);
    });
    /* On the hub this button would be a third simultaneous copy of the same
       CTA (inline .inv-compare-go + fixed .inv-bar-go already cover it); on
       the detail/compare screens it is the only compare CTA in the rail, so
       it stays there. The selection chips above stay unconditional either
       way so the rail is never left empty. */
    if ((typeof INVESTOR_VIEW === "undefined" ? null : INVESTOR_VIEW) !== "index"){
      var go = document.createElement("button"); go.type = "button"; go.className = "inv-rail-compare"; go.textContent = c.compare; go.disabled = selected.size < 2; go.addEventListener("click", function(){ goCompare(); }); pick.appendChild(go);
    }
    var guide = document.createElement("section"); guide.className = "inv-rail-card";
    guide.innerHTML = '<h2>' + esc(c.read13f) + '</h2><p>' + esc(c.read13fSub) + '</p><ul><li>' + esc(c.read13f1) + '</li><li>' + esc(c.read13f2) + '</li><li>' + esc(c.read13f3) + '</li></ul>';
    var snap = document.createElement("section"); snap.className = "inv-rail-card";
    var period = investors.length ? invFmtDate(invLatestPeriod(investors)) : "—";
    snap.innerHTML = '<h2>' + esc(c.snapshot) + '</h2><dl><div><dt>' + esc(c.investorsLabel) + '</dt><dd>' + investors.length + '</dd></div><div><dt>' + esc(c.periodLabel) + '</dt><dd>' + esc(period) + '</dd></div><div><dt>' + esc(c.sourceLabel) + '</dt><dd>SEC 13F</dd></div>' + invNextFilingRowHtml(investors, c) + '</dl>';
    wrap.appendChild(pick); wrap.appendChild(guide); wrap.appendChild(snap); rail.appendChild(wrap);
  }
  function syncSelection(investors){
    var c = C();
    document.querySelectorAll("[data-inv-select]").forEach(function(button){
      var slug = button.getAttribute("data-inv-select"), on = selected.has(slug); selectionLabel(button, on);
    });
    document.querySelectorAll(".inv-compare-count").forEach(function(el){ el.textContent = c.selected.replace("{n}", selected.size); });
    document.querySelectorAll("[data-inv-go]").forEach(function(button){ button.disabled = selected.size < 2; });
    renderInvestorRail(investors); renderCompareBar(investors);
  }

  function makePicker(investors, grid){
    ensureSelection(investors);
    var c = C(), box = document.createElement("section"); box.className = "inv-hub-tools";
    box.innerHTML = '<div class="inv-compare-entry"><span class="inv-compare-entry-icon">⇄</span><div><b>' + esc(c.pickTitle) + '</b><p>' + esc(c.entrySub) + '</p></div>'
      + '<button type="button" class="inv-compare-go" data-inv-go>' + esc(c.compare) + '</button><span class="inv-compare-count"></span><span class="inv-compare-msg" aria-live="polite"></span></div>'
      + '<label class="inv-hub-search"><span aria-hidden="true">⌕</span><input type="search" placeholder="' + esc(c.search) + '" aria-label="' + esc(c.search) + '"></label>';
    var msg = box.querySelector(".inv-compare-msg");
    box.querySelector(".inv-compare-go").addEventListener("click", function(){ goCompare(msg); });
    box.querySelector("input").addEventListener("input", function(ev){
      var q = String(ev.target.value || "").trim().toLocaleLowerCase();
      grid.querySelectorAll(".inv-hub-card").forEach(function(card){ card.hidden = !!q && String(card.getAttribute("data-search") || "").indexOf(q) < 0; });
    });
    return box;
  }
  /* 13F 허브 YTD 수익률(data/investor-returns.json, 일별 파이프라인 산출물).
     브라우저에서 종목별 시세를 재계산하지 않는다 — v90에서 investorCardFillSpark가
     허브 진입마다 /quote 194건을 쏘던 문제로 스파크라인을 걷어낸 전례가 있다. 값은
     파일에서 그대로 읽기만 한다.
     모듈 레벨 Promise/캐시라 허브 재진입은 재요청하지 않는다. rAF/IO로 지연 로드를
     게이팅하지 않는다 — 이 파일이 이미 세 번(v82 스파크라인, v85 비교 렌더, v88
     엔티티 로더) 배경 탭에서 안 깨어나는 함정을 밟았고 v90 IO(하단 바)가 네 번째다.
     여기서는 순수 fetch 체인만 쓴다. */
  var HUB_RETURNS_STALE_DAYS = 5; /* as_of가 이보다 오래되면(또는 로드 실패/malformed) 열 전체를 "—" 처리 */
  var HUB_RETURNS_P = null;
  var HUB_RETURNS_DATA = null; /* null = 아직 없음 / 실패 / stale. 해석된 JSON이면 {as_of, ytd_start, investors} */
  function loadHubReturns(){
    if (HUB_RETURNS_P) return HUB_RETURNS_P;
    var url = (typeof dataUrl === "function") ? dataUrl("investor-returns.json") : "data/investor-returns.json";
    HUB_RETURNS_P = (typeof getJSON === "function" ? getJSON(url) : Promise.resolve(null))
      .then(function(j){
        if (!j || typeof j !== "object" || !j.investors || typeof j.investors !== "object") return null;
        var asOf = Date.parse(j.as_of);
        if (!isFinite(asOf) || (Date.now() - asOf) > HUB_RETURNS_STALE_DAYS * 86400000) return null;
        return j;
      })
      .catch(function(){ return null; })
      .then(function(data){ HUB_RETURNS_DATA = data; return data; });
    return HUB_RETURNS_P;
  }
  function hubReturnEntry(inv){
    var d = HUB_RETURNS_DATA;
    return (d && inv && d.investors && d.investors[inv.slug]) || null;
  }
  function hubReturnPct(inv){
    var e = hubReturnEntry(inv);
    return (e && typeof e.ytd_pct === "number" && isFinite(e.ytd_pct)) ? e.ytd_pct : null;
  }
  function hubReturnsDate(iso){
    var d = new Date(iso);
    if (!isFinite(d.getTime())) return "";
    var m = d.getUTCMonth() + 1, day = d.getUTCDate(), y = d.getUTCFullYear();
    if (typeof LANG !== "undefined" && LANG === "en"){
      return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m - 1] + " " + day + ", " + y;
    }
    if (typeof LANG !== "undefined" && LANG === "ja") return y + "年" + m + "月" + day + "日";
    return y + "." + String(m).padStart(2,"0") + "." + String(day).padStart(2,"0");
  }
  /* 허브 랭킹 표 정렬 상태. 기본은 공개 평가액 내림차순(dir=-1 오름/-1 내림 대신
     "1=오름, -1=내림"으로 부호를 정해 hubCompareRows의 dir*(av-bv) 공식과 맞춘다). */
  var HUB_SORT = { key: "total_value", dir: -1 };
  function hubSortValue(inv, key){
    if (key === "ytd_return") return hubReturnPct(inv);
    if (key === "total_value") return (typeof inv.total_value === "number" && isFinite(inv.total_value)) ? inv.total_value : null;
    if (key === "holdings_count") return (typeof inv.holdings_count === "number" && isFinite(inv.holdings_count)) ? inv.holdings_count : null;
    if (key === "top5") { var w = topWeight(inv, 5); return isFinite(w) ? w : null; }
    if (key === "turnover") { var t = inv.activity && inv.activity.turnover_pct; return (typeof t === "number" && isFinite(t)) ? t : null; }
    return null;
  }
  /* 값이 없는 항목은 오름차순/내림차순 관계없이 항상 맨 뒤로 보낸다(요구사항: "정렬에서
     항상 뒤로"). -Infinity로 치환하는 트릭은 내림차순에서만 뒤로 가므로 쓰지 않고,
     null 여부를 직접 분기해 방향과 무관하게 뒤로 보낸다. */
  function hubCompareRows(a, b){
    var av = hubSortValue(a.inv, HUB_SORT.key), bv = hubSortValue(b.inv, HUB_SORT.key);
    var an = av == null, bn = bv == null;
    if (an && bn) return 0;
    if (an) return 1;
    if (bn) return -1;
    return HUB_SORT.dir * (av - bv);
  }
  function hubApplySort(table, rows){
    var tbody = table.querySelector("tbody");
    rows.slice().sort(hubCompareRows).forEach(function(r){ tbody.appendChild(r.tr); });
    table.querySelectorAll("thead button[data-sort]").forEach(function(btn){
      var key = btn.getAttribute("data-sort"), th = btn.parentNode, on = key === HUB_SORT.key;
      th.setAttribute("aria-sort", on ? (HUB_SORT.dir === 1 ? "ascending" : "descending") : "none");
      btn.classList.toggle("on", on);
    });
  }
  function upgradeHubCards(grid, investors){
    var c = C();
    var items = Array.prototype.slice.call(grid.children).map(function(card, i){
      var inv = investors[i];
      return (inv && card.classList.contains("inv-card")) ? { inv: inv, card: card } : null;
    }).filter(Boolean);
    if (!items.length) return;

    var table = document.createElement("table"); table.className = "inv-hub-table";
    var thead = document.createElement("thead"), headRow = document.createElement("tr");
    var COLS = [
      { label: c.investorsLabel, key: null, num: false },
      { label: c.ytdReturn, key: "ytd_return", num: true },
      { label: c.total, key: "total_value", num: true },
      { label: c.holdings, key: "holdings_count", num: true },
      { label: c.top5, key: "top5", num: true },
      { label: c.turnover, key: "turnover", num: true },
      { label: c.topHolding, key: null, num: true },
      { label: "", key: null, num: false }
    ];
    COLS.forEach(function(col){
      var th = document.createElement("th");
      if (col.num) th.className = "num";
      if (col.key){
        var btn = document.createElement("button"); btn.type = "button"; btn.setAttribute("data-sort", col.key);
        btn.textContent = col.label; th.appendChild(btn); th.setAttribute("aria-sort", "none");
      } else {
        th.textContent = col.label;
      }
      headRow.appendChild(th);
    });
    thead.appendChild(headRow); table.appendChild(thead);

    var tbody = document.createElement("tbody");
    var rows = items.map(function(item){
      var inv = item.inv, card = item.card;
      var tr = document.createElement("tr"); tr.className = "inv-hub-card"; tr.setAttribute("data-slug", inv.slug);
      tr.setAttribute("data-search", [tickerLabel(inv), locVal(inv.manager), locVal(inv.name), inv.slug].join(" ").toLocaleLowerCase());

      card.classList.add("inv-hub-person");
      var name = card.querySelector(".inv-card-name"), manager = card.querySelector(".inv-card-manager");
      if (name) name.textContent = locVal(inv.manager) || locVal(inv.name) || inv.slug;
      if (manager) manager.textContent = locVal(inv.name) || "";
      var nameTd = document.createElement("td"); nameTd.appendChild(card); tr.appendChild(nameTd);

      /* 값은 loadHubReturns() 응답이 오기 전까지 "—" 자리표시. 페인트를 막지
         않고 즉시 렌더한 뒤, 아래 loadHubReturns().then() 콜백이 채운다
         (백그라운드 탭에서도 동작해야 하므로 rAF/IO 게이팅 없음). */
      var ytdTd = document.createElement("td"); ytdTd.className = "num";
      var ytdSpan = document.createElement("span"); ytdSpan.className = "inv-perf"; ytdSpan.textContent = "—";
      ytdTd.appendChild(ytdSpan); tr.appendChild(ytdTd);

      var totalTd = document.createElement("td"); totalTd.className = "num"; totalTd.textContent = invMoneyFmt(inv.total_value); tr.appendChild(totalTd);
      var holdingsTd = document.createElement("td"); holdingsTd.className = "num"; holdingsTd.textContent = inv.holdings_count == null ? "—" : String(inv.holdings_count); tr.appendChild(holdingsTd);
      var top5Td = document.createElement("td"); top5Td.className = "num"; top5Td.textContent = pct(topWeight(inv, 5), 1); tr.appendChild(top5Td);
      var turnoverTd = document.createElement("td"); turnoverTd.className = "num"; turnoverTd.textContent = pct(inv.activity && inv.activity.turnover_pct, 1); tr.appendChild(turnoverTd);

      var top = topHolding(inv);
      var topTd = document.createElement("td"); topTd.className = "num";
      topTd.textContent = top ? (holdingTicker(top) + " " + pct(top.weight, 1)) : "—";
      tr.appendChild(topTd);

      var selectTd = document.createElement("td");
      var add = document.createElement("button"); add.type = "button"; add.className = "inv-hub-select"; add.setAttribute("data-inv-select", inv.slug);
      add.addEventListener("click", function(){ toggleSelection(inv.slug, investors, document.querySelector(".inv-compare-msg")); });
      selectTd.appendChild(add); tr.appendChild(selectTd);

      return { inv: inv, tr: tr, ytdTd: ytdTd, ytdSpan: ytdSpan };
    });
    rows.forEach(function(r){ tbody.appendChild(r.tr); });
    table.appendChild(tbody);

    Array.prototype.slice.call(grid.children).forEach(function(child){ grid.removeChild(child); });
    grid.appendChild(table);

    var note = document.createElement("p"); note.className = "inv-hub-ytd-note"; note.textContent = c.ytdReturnUnavailable;
    if (grid.parentNode) grid.parentNode.insertBefore(note, grid.nextSibling);

    hubApplySort(table, rows);
    headRow.querySelectorAll("button[data-sort]").forEach(function(btn){
      btn.addEventListener("click", function(){
        var key = btn.getAttribute("data-sort");
        if (HUB_SORT.key === key) HUB_SORT.dir = -HUB_SORT.dir; else { HUB_SORT.key = key; HUB_SORT.dir = -1; }
        hubApplySort(table, rows);
      });
    });

    loadHubReturns().then(function(data){
      rows.forEach(function(r){
        var v = hubReturnPct(r.inv);
        r.ytdSpan.textContent = v == null ? "—" : signedPct(v);
        r.ytdSpan.className = "inv-perf" + perfClass(v);
        var entry = hubReturnEntry(r.inv);
        if (v == null && entry && typeof entry.coverage_pct === "number" && isFinite(entry.coverage_pct)){
          r.ytdTd.title = c.ytdReturnCoverage.replace("{p}", (entry.coverage_pct * 100).toFixed(1));
        } else {
          r.ytdTd.removeAttribute("title");
        }
      });
      note.textContent = data ? c.ytdReturnNote.replace("{start}", hubReturnsDate(data.ytd_start)).replace("{asOf}", hubReturnsDate(data.as_of)) : c.ytdReturnUnavailable;
      if (HUB_SORT.key === "ytd_return") hubApplySort(table, rows);
    });
  }

  /* Rows shown in the summary table, top to bottom. "perf" marks the four
     rows whose value arrives async from fillPerformance() and which are
     eligible for the (higher-is-better) winner highlight; the rest render
     synchronously from the 13F snapshot and are never highlighted because
     the product takes no stance on whether e.g. high turnover is good. */
  var SUMMARY_METRIC_ROWS = [
    { key:"reported", copy:"reported" }, { key:"total", copy:"total" },
    { key:"holdings", copy:"holdings" }, { key:"top5", copy:"top5" }, { key:"turnover", copy:"turnover" },
    { key:"since", copy:"since", perf:"since" }, { key:"threeM", copy:"threeM", perf:"3m" },
    { key:"oneY", copy:"oneY", perf:"1y" }, { key:"vsSpy", copy:"vsSpy", perf:"spy" }
  ];
  var SUMMARY_CHANGE_ROWS = [
    { key:"newBuy", copy:"newBuy", field:"new_count" }, { key:"add", copy:"add", field:"added_count" },
    { key:"trim", copy:"trim", field:"reduced_count" }, { key:"exit", copy:"exit", field:"exited_count" }
  ];
  function summaryMetricHtml(c, key, inv){
    var a = inv.activity || {};
    if (key === "reported") return esc(invFmtDate(inv.period));
    if (key === "total") return esc(invMoneyFmt(inv.total_value));
    if (key === "holdings") return String(inv.holdings_count == null ? "—" : inv.holdings_count);
    if (key === "top5") return pct(topWeight(inv, 5), 1);
    if (key === "turnover") return pct(a.turnover_pct, 1);
    return "—";
  }
  function num(v){ return typeof v === "number" ? String(v) : "—"; }

  /* One <table>, metrics as rows / investors as columns, instead of one
     repeated-label card per investor. Cells are addressed by investor slug
     (model.cols / model.perf) rather than by a per-investor container
     element, since a column no longer has one. */
  function summaryTable(chosen){
    var c = C();
    var table = document.createElement("table"); table.className = "inv-compare-table inv-compare-summary-table";
    var thead = document.createElement("thead"), headTr = document.createElement("tr");
    headTr.appendChild(document.createElement("th"));
    var cols = {}, slugs = [];
    chosen.forEach(function(inv){
      slugs.push(inv.slug);
      var th = document.createElement("th"); th.className = "inv-compare-col"; th.scope = "col";
      th.setAttribute("data-slug", inv.slug); th.setAttribute("data-price-status", "loading");
      th.innerHTML = '<button type="button" class="inv-compare-card-head"><span class="inv-ticker">' + esc(tickerLabel(inv)) + '</span>'
        + '<b>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</b><small>' + esc(locVal(inv.name) || "") + '</small>'
        + '<span class="inv-price-cov inv-price-status" data-price-status="loading" role="status" aria-live="polite">' + esc(c.loading) + '</span></button>';
      th.querySelector(".inv-compare-card-head").addEventListener("click", function(){ if (typeof openInvestor === "function") openInvestor(inv.slug); });
      headTr.appendChild(th);
      cols[inv.slug] = { th: th, priceEl: th.querySelector(".inv-price-status") };
    });
    thead.appendChild(headTr); table.appendChild(thead);

    var tbody = document.createElement("tbody"), perf = {};
    chosen.forEach(function(inv){ perf[inv.slug] = {}; });
    SUMMARY_METRIC_ROWS.forEach(function(row){
      var tr = document.createElement("tr"); tr.setAttribute("data-row", row.key);
      var rowTh = document.createElement("th"); rowTh.scope = "row"; rowTh.textContent = c[row.copy]; tr.appendChild(rowTh);
      chosen.forEach(function(inv){
        var td = document.createElement("td"); td.className = "num"; td.setAttribute("data-slug", inv.slug);
        if (row.perf){
          td.innerHTML = '<span data-perf="' + row.perf + '">' + esc(c.loading) + '</span>';
          perf[inv.slug][row.perf] = { td: td, span: td.firstChild, value: null };
        } else {
          td.innerHTML = summaryMetricHtml(c, row.key, inv);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    SUMMARY_CHANGE_ROWS.forEach(function(row){
      var tr = document.createElement("tr"); tr.setAttribute("data-row", row.key);
      var rowTh = document.createElement("th"); rowTh.scope = "row"; rowTh.textContent = c[row.copy]; tr.appendChild(rowTh);
      chosen.forEach(function(inv){
        var a = inv.activity || {}, td = document.createElement("td");
        td.className = "num"; td.setAttribute("data-slug", inv.slug); td.textContent = num(a[row.field]);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    var wrap = document.createElement("div"); wrap.className = "inv-compare-table-wrap"; wrap.appendChild(table);
    return { wrap: wrap, table: table, cols: cols, perf: perf, slugs: slugs };
  }

  /* Recomputes the single-winner highlight for one perf row (since/3m/1y/spy)
     across every investor column. Only fires when >=2 columns have a finite
     value; a tie highlights nobody. Re-run after every fillPerformance()
     resolution so out-of-order arrivals still converge on the right winner. */
  function updateRowWinner(model, key){
    var best = null, winners = [], finite = 0;
    model.slugs.forEach(function(slug){
      var cell = model.perf[slug] && model.perf[slug][key]; if (!cell) return;
      cell.td.classList.remove("inv-win");
      if (typeof cell.value === "number" && isFinite(cell.value)){
        finite++;
        if (best === null || cell.value > best){ best = cell.value; winners = [slug]; }
        else if (cell.value === best){ winners.push(slug); }
      }
    });
    if (finite >= 2 && winners.length === 1){
      var win = model.perf[winners[0]][key];
      if (win) win.td.classList.add("inv-win");
    }
  }

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
  function setPerf(model, slug, key, value, fallback){
    var cell = model.perf[slug] && model.perf[slug][key]; if (!cell) return;
    var finite = typeof value === "number" && isFinite(value);
    cell.span.textContent = finite ? signedPct(value) : fallback;
    cell.span.className = "inv-perf" + perfClass(value);
    cell.value = finite ? value : null;
    updateRowWinner(model, key);
  }
  function priceState(res, c){
    var coverage = res && typeof res.coverage === "number" && isFinite(res.coverage) ? Math.max(0, Math.min(1, res.coverage)) : null;
    var hasSeries = !!(res && res.calendar && res.values && res.calendar.length > 1 && res.values.length > 1);
    if (!hasSeries || !(coverage > 0)) return { key:"unavailable", coverage:coverage, text:c.priceUnavailable };
    if (coverage < 0.999) return { key:"partial", coverage:coverage, text:c.pricePartial.replace("{p}", Math.round(coverage * 100)) };
    return { key:"ok", coverage:coverage, text:c.coverage.replace("{p}", Math.round(coverage * 100)) };
  }
  function quoteReady(q){ return !!(q && !q.error && q.t && q.closes && q.t.length > 1 && q.closes.length > 1); }
  function setPriceStatus(model, slug, res, c){
    var col = model.cols[slug]; if (!col) return;
    var state = priceState(res, c), el = col.priceEl;
    col.th.setAttribute("data-price-status", state.key);
    if (state.coverage == null) col.th.removeAttribute("data-price-coverage");
    else col.th.setAttribute("data-price-coverage", String(Math.round(state.coverage * 100)));
    if (!el){
      el = document.createElement("span"); el.className = "inv-price-cov inv-price-status"; el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite");
      col.th.querySelector(".inv-compare-card-head").appendChild(el);
      col.priceEl = el;
    }
    el.className = "inv-price-cov inv-price-status";
    el.textContent = state.text;
    el.setAttribute("data-price-status", state.key);
    if (state.coverage == null) el.removeAttribute("data-price-coverage");
    else el.setAttribute("data-price-coverage", String(Math.round(state.coverage * 100)));
  }
  function fillPerformance(model, inv){
    var c = C(), filed = typeof invFiledEpoch === "function" ? invFiledEpoch(inv.filed) : null, slug = inv.slug;
    return Promise.all([compareSeries(inv), quote1y("spy.us").catch(function(){ return null; })]).then(function(rows){
      if (!model.table.isConnected) return;
      var res = rows[0], spy = rows[1], lastEpoch = res && res.calendar && res.calendar.length ? res.calendar[res.calendar.length-1] : null;
      var state = priceState(res, c), hasSeries = state.key !== "unavailable";
      var since = valuePctAt(res, filed), age = filed != null && lastEpoch != null ? lastEpoch - filed : 0;
      var r3 = age >= 90*86400 ? valuePctAt(res, lastEpoch - 90*86400) : null;
      var r1 = age >= 365*86400 ? valuePctAt(res, lastEpoch - 365*86400) : null;
      var spySince = quotePctAt(spy, filed);
      setPerf(model,slug,"since",since,hasSeries ? "—" : c.priceUnavailable); setPerf(model,slug,"3m",r3,hasSeries ? c.building : c.priceUnavailable); setPerf(model,slug,"1y",r1,hasSeries ? c.building : c.priceUnavailable);
      setPerf(model,slug,"spy",typeof since === "number" && typeof spySince === "number" ? since-spySince : null,!quoteReady(spy) ? c.benchmarkUnavailable : (hasSeries ? "—" : c.priceUnavailable));
      setPriceStatus(model, slug, res, c);
    }).catch(function(){
      if (!model.table.isConnected) return;
      ["since","3m","1y","spy"].forEach(function(k){ setPerf(model,slug,k,null,c.priceUnavailable); });
      setPriceStatus(model, slug, null, c);
    });
  }

  var GRAPH_COLORS = ["#2F80ED", "#12B76A", "#F79009", "#9B51E0"];
  var GRAPH_PERIODS = [
    { key:"1m", days:30, copy:"holdGraph1m" },
    { key:"3m", days:91, copy:"holdGraph3m" },
    { key:"6m", days:182, copy:"holdGraph6m" },
    { key:"ytd", ytd:true, copy:"holdGraphYtd" },
    { key:"1y", days:365, copy:"holdGraph1y" }
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
  /* Daily bars carry a ~14:30 UTC timestamp (mid-session snapshot), while
     window-START targets (e.g. YTD's Date.UTC(y,0,1)) land on a midnight
     boundary. Nearest-neighbour search (graphPointAt) then picks the prior
     year's Dec 31 bar (~9.5h away) over the correct Jan 2 bar (~38.5h away),
     silently adding a trading day of return to every start-of-window figure.
     Use this ceiling search — first point with t >= target — for ANY window
     START resolution. Must stay in lockstep with invPaintValueChart's
     ceiling loop in index.html (`while (startIdx < calendar.length - 1 &&
     calendar[startIdx] < requestedStart) startIdx++;`) — that is this
     function's twin for the single-investor chart; keep both in sync.
     END resolution should keep using graphPointAt (nearest-neighbour). */
  function graphPointAtOrAfter(points, target){
    if (!points || !points.length) return null;
    var lo = 0, hi = points.length - 1;
    if (target <= points[0].t) return points[0];
    if (target > points[hi].t) return points[hi];
    while (lo < hi){
      var mid = (lo + hi) >> 1;
      if (points[mid].t < target) lo = mid + 1; else hi = mid;
    }
    return points[lo];
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
    var start = graphPointAtOrAfter(series.points, windowStart + lo * maxElapsed);
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
      var inv = row.inv, state = row.benchmark
        ? (row.series ? { key:"ok", coverage:1, text:c.benchmarkNote } : { key:"unavailable", coverage:null, text:c.benchmarkUnavailable })
        : priceState(row.res, c);
      var coverageAttr = state.coverage == null ? "" : ' data-price-coverage="' + Math.round(state.coverage * 100) + '"';
      return '<span class="inv-compare-legend-item' + (row.series ? "" : " muted") + '" data-price-status="' + state.key + '"' + coverageAttr + '>'
        + '<i style="background:' + (row.color || graphColor(i)) + '"></i><b>' + esc(row.label || tickerLabel(inv)) + '</b>'
        + '<span>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</span>'
        + '<small>' + esc(state.text) + '</small></span>';
    }).join("");
  }
  function graphStatus(rows){
    var hasSeries = rows.some(function(row){ return !!row.series; });
    var partial = rows.some(function(row){ return row.benchmark ? !row.series : !row.series || priceState(row.res, C()).key !== "ok"; });
    var benchmark = rows.find(function(row){ return row.benchmark; });
    return { key:!hasSeries ? "unavailable" : (partial ? "partial" : "ok"), benchmark:!benchmark ? "hidden" : (benchmark.series ? "ok" : "unavailable") };
  }
  function setGraphStatus(chart, rows){
    var state = graphStatus(rows);
    chart.setAttribute("data-price-status", state.key);
    chart.setAttribute("data-price-benchmark", state.benchmark);
    chart.setAttribute("aria-busy", "false");
  }
  /* Resting-state hero figures above the hold-graph: one signed return per
     selected investor (benchmark excluded), always matching whatever the
     chart currently shows (full window or an active drag selection). Colour
     and index come from the already-painted line when one exists so the
     number can never drift from what the SVG draws; investors with no line
     for this window fall back to holdGraphNoPrice rather than a blank or a
     fake 0.0%. */
  function findHeroSeries(series, inv){
    if (!series) return null;
    for (var i = 0; i < series.length; i++){ if (series[i].inv === inv) return series[i]; }
    return null;
  }
  function heroValueHtml(c, v){
    if (typeof v !== "number" || !isFinite(v)) return '<b class="inv-compare-hero-value">' + esc(c.holdGraphNoPrice) + '</b>';
    return '<b class="inv-compare-hero-value inv-perf' + perfClass(v / 100) + '">' + esc(signedPct(v / 100)) + '</b>';
  }
  function renderHero(heroLabelEl, heroListEl, rows, series, c, labelText, valueFor){
    if (!heroListEl) return;
    if (heroLabelEl) heroLabelEl.textContent = labelText;
    var investorRows = rows.filter(function(row){ return !row.benchmark; });
    heroListEl.innerHTML = investorRows.map(function(row, i){
      var s = findHeroSeries(series, row.inv);
      var color = (s && s.color) || row.color || graphColor(i);
      var label = (s && s.label) || row.label || tickerLabel(row.inv);
      var v = valueFor(s);
      return '<div class="inv-compare-hero-item"><span class="inv-compare-hero-name"><i style="background:' + color + '"></i>' + esc(label) + '</span>' + heroValueHtml(c, v) + '</div>';
    }).join("");
  }
  function heroWindowLabel(c, period){ return c.holdGraphHeroLabel.replace("{period}", graphPeriodLabel(c, period)); }
  function heroSelectionLabel(c){ return c.holdGraphHeroLabel.replace("{period}", c.holdGraphSelected); }
  function heroLastValue(s){ return s && s.points && s.points.length ? s.points[s.points.length - 1].v : null; }
  function emptyCompareChart(chart, rows, c, heroLabelEl, heroListEl, period){
    setGraphStatus(chart, rows);
    chart.innerHTML = '<div class="inv-compare-chart-empty" role="status" aria-live="polite" data-price-status="unavailable">' + esc(c.holdGraphNoData) + '</div>';
    renderHero(heroLabelEl, heroListEl, rows, null, c, heroWindowLabel(c, period), function(){ return null; });
  }
  function paintCompareGraph(chart, legend, rows, c, period, clearBtn, rangeReadout, heroLabelEl, heroListEl){
    if (clearBtn) clearBtn.hidden = true;
    if (rangeReadout) rangeReadout.hidden = true;
    graphLegend(legend, rows, c);
    setGraphStatus(chart, rows);
    var fullSeries = rows.map(function(row){ return row.series; }).filter(Boolean);
    if (!fullSeries.length){ emptyCompareChart(chart, rows, c, heroLabelEl, heroListEl, period); return; }
    var window = graphWindow(period, fullSeries), windowStart = window.start, windowEnd = window.end;
    var maxElapsed = windowEnd - windowStart;
    if (!(maxElapsed > 0)){ emptyCompareChart(chart, rows, c, heroLabelEl, heroListEl, period); return; }
    var series = fullSeries.map(function(s, i){
      var first = graphPointAtOrAfter(s.points, windowStart), last = graphPointAt(s.points, windowEnd);
      if (!first || !last || last.t <= first.t || !(first.v > 0)) return null;
      var points = s.points.filter(function(p){ return p.t >= first.t && p.t <= last.t; });
      if (!points.length || points[0].t !== first.t) points.unshift(first);
      if (points[points.length - 1].t !== last.t) points.push(last);
      return { inv:s.inv, label:s.label, benchmark:s.benchmark, points:points.map(function(p){ var index = (p.v / first.v) * 100; return { t:p.t, v:index - 100, index:index }; }), start:first.t, end:last.t, color:s.color || graphColor(i) };
    }).filter(Boolean);
    if (!series.length){ emptyCompareChart(chart, rows, c, heroLabelEl, heroListEl, period); return; }
    renderHero(heroLabelEl, heroListEl, rows, series, c, heroWindowLabel(c, period), heroLastValue);
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
      return '<polyline points="' + pts + '" fill="none" stroke="' + s.color + '" stroke-width="' + (s.benchmark ? '2' : '2.5') + '"' + (s.benchmark ? ' stroke-dasharray="7 6"' : '') + ' stroke-linejoin="round" stroke-linecap="round"/>';
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
        html += '<span><i style="background:' + s.color + '"></i>' + esc(s.label || tickerLabel(s.inv)) + ' <b>' + esc(graphPct(p.v)) + '</b></span>';
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
        if (!r){ html += '<span><i style="background:' + s.color + '"></i>' + esc(s.label || tickerLabel(s.inv)) + ' <b>—</b></span>'; return; }
        any = true;
        html += '<span><i style="background:' + s.color + '"></i>' + esc(s.label || tickerLabel(s.inv)) + ' <b>' + esc(rangePct(r.pct)) + '</b></span>';
      });
      if (!any) html += '<span>' + esc(c.holdGraphNoData) + '</span>';
      tip.innerHTML = html; tip.hidden = false; placeTip(((x1 + x2) / 2) / W);
      if (clearBtn) clearBtn.hidden = false;
      renderHero(heroLabelEl, heroListEl, rows, series, c, heroSelectionLabel(c), function(s){
        var r = s ? graphRangeForSeries(s, lo, hi, maxElapsed, windowStart) : null;
        return r ? r.pct : null;
      });
    }
    function clearSelection(){
      selection = null; selectionRect.setAttribute("visibility", "hidden"); if (clearBtn) clearBtn.hidden = true; if (rangeReadout) rangeReadout.hidden = true; hideHover();
      renderHero(heroLabelEl, heroListEl, rows, series, c, heroWindowLabel(c, period), heroLastValue);
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
    sec.innerHTML = '<div class="inv-performance-head inv-performance-head-row"><div><h3>' + esc(c.holdGraphTitle) + '</h3><p>' + esc(c.holdGraphSub) + '</p><small class="inv-compare-drag-hint">' + esc(c.holdGraphDrag) + '</small></div><label class="inv-benchmark-toggle"><input type="checkbox" checked><span>' + esc(c.benchmark) + '</span></label></div>'
      + '<div class="inv-compare-periods" role="tablist" aria-label="' + esc(c.holdGraphTitle) + '">' + periodButtons + '</div>'
      + '<div class="inv-compare-hero" aria-live="polite"><small class="inv-compare-hero-label"></small><div class="inv-compare-hero-list"></div></div>'
      + '<div class="inv-compare-chart" data-price-status="loading" data-price-benchmark="loading" aria-busy="true"><div class="ehq-loading">···</div></div><div class="inv-compare-selection-label" aria-live="polite" hidden></div><div class="inv-compare-legend"></div><button type="button" class="inv-compare-clear" hidden>' + esc(c.holdGraphClear) + '</button><p class="inv-compare-note">' + esc(c.holdGraphNote) + ' <button type="button" class="inv-compare-note-link">' + esc(c.holdGraphNoteMore) + ' →</button></p>';
    var chart = sec.querySelector(".inv-compare-chart"), legend = sec.querySelector(".inv-compare-legend"), clearBtn = sec.querySelector(".inv-compare-clear"), rangeReadout = sec.querySelector(".inv-compare-selection-label"), benchmarkToggle = sec.querySelector(".inv-benchmark-toggle input"), heroLabelEl = sec.querySelector(".inv-compare-hero-label"), heroListEl = sec.querySelector(".inv-compare-hero-list"), noteLinkBtn = sec.querySelector(".inv-compare-note-link"), rows = null, activePeriod = "ytd";
    /* A real <a href="#inv-compare-disc"> looked right but is unsafe here:
       this SPA's popstate handler treats any history entry with null state
       (which a plain fragment-link click pushes) as "nothing recognized,
       close the open overlay" and its own URL-sync (noteView/stkSyncUrl)
       then normalizes the address bar back to "/", silently dropping the
       whole compare view. A scroll-only button sidesteps the router
       entirely. */
    if (noteLinkBtn) noteLinkBtn.addEventListener("click", function(){
      try {
        var target = document.getElementById("inv-compare-disc");
        if (target && typeof target.scrollIntoView === "function") target.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (e) {}
    });
    function currentPeriod(){ return GRAPH_PERIODS.find(function(period){ return period.key === activePeriod; }) || GRAPH_PERIODS[3]; }
    function visibleRows(){ return (rows || []).filter(function(row){ return !row.benchmark || benchmarkToggle.checked; }); }
    sec.querySelectorAll(".inv-compare-period").forEach(function(button){
      button.addEventListener("click", function(){
        activePeriod = button.getAttribute("data-period") || "ytd";
        sec.querySelectorAll(".inv-compare-period").forEach(function(other){ var on = other === button; other.classList.toggle("on", on); other.setAttribute("aria-selected", on ? "true" : "false"); });
        if (rows) paintCompareGraph(chart, legend, visibleRows(), c, currentPeriod(), clearBtn, rangeReadout, heroLabelEl, heroListEl);
      });
    });
    benchmarkToggle.addEventListener("change", function(){ if (rows) paintCompareGraph(chart, legend, visibleRows(), c, currentPeriod(), clearBtn, rangeReadout, heroLabelEl, heroListEl); });
    var invDone = 0;
    function invProgress(){
      invDone++;
      var lo = chart.querySelector(".ehq-loading");
      if (lo) lo.textContent = c.loading + " (" + invDone + "/" + investors.length + ")";
    }
    Promise.all([
      invMapLimit(investors, 2, function(inv){ return compareSeries(inv).then(function(res){ invProgress(); return { inv: inv, res: res, series: normalizeGraphSeries(inv, res) }; }).catch(function(){ invProgress(); return { inv: inv, res: null, series: null }; }); }),
      quote1y("spy.us").then(function(q){
        var inv = { slug:"spy", ticker:"SP500", manager:{ ko:"S&P 500", en:"S&P 500", ja:"S&P 500" } };
        var res = q && q.t && q.closes ? { calendar:q.t, values:q.closes, coverage:1 } : null;
        var series = normalizeGraphSeries(inv, res); if (series){ series.benchmark = true; series.label = "S&P 500"; series.color = "#8E93A0"; }
        return { inv:inv, res:res, series:series, benchmark:true, label:"S&P 500", color:"#8E93A0" };
      }).catch(function(){
        var inv = { slug:"spy", ticker:"SP500", manager:{ ko:"S&P 500", en:"S&P 500", ja:"S&P 500" } };
        return { inv:inv, res:null, series:null, benchmark:true, label:"S&P 500", color:"#8E93A0" };
      })
    ]).then(function(result){ rows = result[0].concat(result[1] ? [result[1]] : []); if (sec.isConnected) paintCompareGraph(chart, legend, visibleRows(), c, currentPeriod(), clearBtn, rangeReadout, heroLabelEl, heroListEl); });
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
    /* The classified-slice breakdown above can look complete even when most
       of the book isn't in it. State the remainder next to the coverage row
       (guarding null/undefined covered_pct instead of printing a false
       "100% unclassified"), then flag investors under SECTOR_COVERAGE_WARN
       so the table reads as a partial view rather than the whole portfolio. */
    rows.push(['<b>'+esc(c.sectorUnclassified)+'</b>'].concat(investors.map(function(inv){
      var cov=inv.sector_alloc&&inv.sector_alloc.covered_pct;
      return typeof cov==="number"&&isFinite(cov)?pct(1-cov,1):"—";
    })));
    sec.appendChild(compareTable([c.sectors].concat(investors.map(function(i){return tickerLabel(i);})),rows));
    var SECTOR_COVERAGE_WARN=0.5;
    var coverageLines=investors.map(function(inv){
      var cov=inv.sector_alloc&&inv.sector_alloc.covered_pct, known=typeof cov==="number"&&isFinite(cov), low=known&&cov<SECTOR_COVERAGE_WARN;
      var text=known
        ? c.sectorUnclassifiedNote.replace("{ticker}",tickerLabel(inv)).replace("{covered}",pct(cov,1)).replace("{uncovered}",pct(1-cov,1))
        : c.sectorUnclassifiedUnknown.replace("{ticker}",tickerLabel(inv));
      return '<p class="inv-sector-coverage-line'+(low?" warn":"")+'">'+esc(text)+'</p>';
    });
    var note=document.createElement("div");note.className="inv-sector-coverage-note";note.innerHTML=coverageLines.join("");
    sec.appendChild(note);
    return sec;
  }
  function compareTable(headers,rows){
    var wrap=document.createElement("div");wrap.className="inv-compare-table-wrap"+(headers[0]==="#"?" inv-top-holdings-table":"");
    wrap.innerHTML='<table class="inv-compare-table"><thead><tr>'+headers.map(function(h){return'<th>'+esc(h)+'</th>';}).join("")+'</tr></thead><tbody>'
      +rows.map(function(r){return'<tr>'+r.map(function(v){return'<td>'+v+'</td>';}).join("")+'</tr>';}).join("")+'</tbody></table>';
    return wrap;
  }

  var CMP_PAINT_VIS_BOUND = false;
  var CMP_PAINT_PENDING = [];
  function cmpPaintFlushPending(){
    CMP_PAINT_PENDING.splice(0).forEach(function(job){ job(); });
  }
  /* A hidden tab never fires rAF, so the deferred build below would stall
     forever at the "계산 중" placeholder. Same failure and same fallback as
     observeInvestorCards() in index.html: resume on visibilitychange, plus a
     one-shot 3s safety net. This unsticks the render; it does not speed it up. */
  function afterCompareFirstPaint(fn){
    if (typeof requestAnimationFrame !== "function"){ setTimeout(fn, 0); return; }
    var done = false;
    function run(){
      if (done) return;
      done = true;
      var i = CMP_PAINT_PENDING.indexOf(run);
      if (i >= 0) CMP_PAINT_PENDING.splice(i, 1);
      fn();
    }
    CMP_PAINT_PENDING.push(run);
    requestAnimationFrame(function(){ requestAnimationFrame(run); });
    if (!CMP_PAINT_VIS_BOUND){
      CMP_PAINT_VIS_BOUND = true;
      document.addEventListener("visibilitychange", function(){
        if (document.visibilityState === "visible") cmpPaintFlushPending();
      });
    }
    setTimeout(run, 3000);
  }

  function selectedStrip(investors){
    var strip = document.createElement("div"); strip.className = "inv-selected-strip";
    investors.forEach(function(inv, i){
      var b = document.createElement("button"); b.type = "button";
      b.innerHTML = '<i style="background:' + graphColor(i) + '"></i><span>' + esc(tickerLabel(inv)) + '</span><b>' + esc(locVal(inv.manager) || locVal(inv.name) || inv.slug) + '</b>';
      b.addEventListener("click", function(){ if (typeof openInvestor === "function") openInvestor(inv.slug); }); strip.appendChild(b);
    });
    return strip;
  }

  function renderCompare(list, S, investors){
    ensureSelection(investors);
    var c=C(), chosen=chosenInvestors(investors);
    if(chosen.length<2){ if(typeof openInvestors==="function") openInvestors(); return; }
    renderInvestorRail(investors);
    var periods=new Set(chosen.map(function(i){return i.period||"";}));
    var head=document.createElement("div");head.className="series-header sb-header";
    head.innerHTML='<button class="series-close" onclick="openInvestors()">← '+esc(c.edit)+'</button><div class="series-head-name">⇄ '+esc(c.title)+'</div>'
      +'<p class="series-head-desc">'+chosen.map(function(i){return esc(tickerLabel(i));}).join(" · ")+'</p>';
    list.appendChild(head);
    list.appendChild(selectedStrip(chosen));
    var loading=document.createElement("div"); loading.className="ehq-loading"; loading.textContent=c.loading; list.appendChild(loading);
    /* Let the comparison header paint before building its tables and chart.
       On mobile, this synchronous DOM work was part of the navigation tap's
       INP even though the data work itself is asynchronous. */
    afterCompareFirstPaint(function(){
      if (!loading.isConnected) return;
      loading.remove();
      list.appendChild(compareGraphSection(chosen));
      if(periods.size>1){var warn=document.createElement("div");warn.className="inv-period-warning";warn.innerHTML='<b>'+esc(c.mismatch)+'</b><span>'+esc(c.periodWarn)+'</span>';list.appendChild(warn);}
      var grid=document.createElement("div");grid.className="inv-compare-summary-grid";
      var summaryModel=summaryTable(chosen);grid.appendChild(summaryModel.wrap);list.appendChild(grid);
      invMapLimit(chosen,2,function(inv){return fillPerformance(summaryModel,inv);});
      list.appendChild(overlapSection(chosen)); list.appendChild(topHoldingsSection(chosen)); list.appendChild(sectorSection(chosen));
      var disc=document.createElement("section");disc.className="inv-compare-disclaimer";disc.id="inv-compare-disc";disc.innerHTML='<b>'+esc(c.discTitle)+'</b><p>'+esc(c.disc)+'</p><p>'+esc(c.discWindow)+'</p>';list.appendChild(disc);
    });
  }

  /* Patch the existing 13F renderers without duplicating their SEC/photo/chart logic. */
  var detailReturn = "index";
  if (typeof window.openInvestor === "function"){
    var originalOpenInvestor = window.openInvestor;
    window.openInvestor = function(slug){
      if (slug !== "compare") detailReturn = ((typeof INVESTOR_VIEW !== "undefined" && INVESTOR_VIEW === "compare") ? "compare" : "index");
      return originalOpenInvestor(slug);
    };
  }
  if(typeof window.investorCardEl==="function"){
    var originalCard=window.investorCardEl;
    window.investorCardEl=function(inv,S){var card=originalCard(inv,S);injectTicker(card,inv);return card;};
  }
  if(typeof window.renderInvestorDetail==="function"){
    var originalDetail=window.renderInvestorDetail;
    window.renderInvestorDetail=function(list,S,inv){
      originalDetail(list,S,inv);
      var head=list.querySelector(".series-header"); injectTicker(head,inv);
      if (head){
        var back = head.querySelector(".series-close");
        if (back){ back.onclick = function(){ if (detailReturn === "compare" && selected.size >= 2) window.openInvestor("compare"); else openInvestors(); }; }
        var add = document.createElement("button"); add.type = "button"; add.className = "inv-profile-compare"; add.setAttribute("data-inv-select", inv.slug);
        add.addEventListener("click", function(){ toggleSelection(inv.slug, (PORTFOLIOS_DATA && PORTFOLIOS_DATA.investors) || [], null); });
        head.appendChild(add);
      }
      var all = (PORTFOLIOS_DATA && PORTFOLIOS_DATA.investors) || [];
      ensureSelection(all);
      syncSelection(all);
    };
  }
  if(typeof window.renderInvestorsIndex==="function"){
    var originalIndex=window.renderInvestorsIndex;
    window.renderInvestorsIndex=function(list,S,investors){
      originalIndex(list,S,investors);
      var grid=list.querySelector(".inv-grid");
      if(grid&&grid.parentNode){ upgradeHubCards(grid,investors); grid.parentNode.insertBefore(makePicker(investors,grid),grid); }
      syncSelection(investors);
    };
  }
  window.renderInvestorCompare=renderCompare;
  window.__stacksInvestorComparePaintDeferred = true;
  window.invTickerLabel=tickerLabel;
})();
