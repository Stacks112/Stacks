(function(){
  "use strict";
  if (window.__stacksInvestorComparePaintDeferred || typeof window.renderInvestorCompare !== "function" || window.__stacksInvestorComparePaintShim) return;
  window.__stacksInvestorComparePaintShim = true;
  var original = window.renderInvestorCompare;
  window.renderInvestorCompare = function(list, S, investors){
    function run(){
      if (!list || !list.isConnected || (typeof INVESTOR_VIEW !== "undefined" && INVESTOR_VIEW !== "compare")) return;
      original(list, S, investors);
    }
    if (typeof requestAnimationFrame === "function"){
      requestAnimationFrame(function(){ requestAnimationFrame(run); });
    } else setTimeout(run, 0);
  };
})();
