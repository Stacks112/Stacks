(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StacksFeedRanker = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var VERSION = "1.0.0";
  var DAY_MS = 86400000;
  var FLAG_KEY = "stk_feed_ranker_v1";
  var lastReasons = Object.create(null);

  var REASON_TEXT = {
    ko: {
      follow: "팔로우 기반",
      similar: "관심 주제와 비슷함",
      explore: "새로운 주제 추천",
      popular: "지금 주목받는 글",
      fresh: "새 글 추천"
    },
    en: {
      follow: "Based on your follows",
      similar: "Similar to your interests",
      explore: "A new topic to explore",
      popular: "Getting attention now",
      fresh: "A fresh read"
    },
    ja: {
      follow: "フォローに基づくおすすめ",
      similar: "関心のあるテーマに近い記事",
      explore: "新しいテーマのおすすめ",
      popular: "いま注目の記事",
      fresh: "新着のおすすめ"
    }
  };

  function finiteNumber(value) {
    var n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function toSet(value) {
    if (value instanceof Set) return value;
    if (Array.isArray(value)) return new Set(value);
    return new Set();
  }

  function uniqueStrings(values) {
    var seen = new Set();
    var out = [];
    (Array.isArray(values) ? values : []).forEach(function (value) {
      var key = String(value == null ? "" : value).trim().toUpperCase();
      if (!key || seen.has(key)) return;
      seen.add(key);
      out.push(key);
    });
    return out;
  }

  function tagsFor(item) {
    return uniqueStrings(item && item.tags);
  }

  function entitiesFor(context, item) {
    try {
      return uniqueStrings(context.getEntities ? context.getEntities(item) : []);
    } catch (e) {
      return [];
    }
  }

  function directReasonsFor(context, item) {
    try {
      var reasons = context.getDirectReasons ? context.getDirectReasons(item) : [];
      return Array.isArray(reasons) ? reasons : [];
    } catch (e) {
      return [];
    }
  }

  function addWeight(map, key, weight) {
    if (!key || !weight) return;
    map[key] = (map[key] || 0) + weight;
  }

  function maxWeight(map) {
    var max = 0;
    Object.keys(map).forEach(function (key) { max = Math.max(max, map[key]); });
    return max || 1;
  }

  function buildProfile(items, context, sets) {
    var profile = {
      tags: Object.create(null),
      entities: Object.create(null),
      sources: Object.create(null)
    };

    items.forEach(function (item) {
      if (!item || !item.id) return;
      var weight = 0;
      if (sets.likes.has(item.id)) weight += 4;
      if (sets.bookmarks.has(item.id)) weight += 3;
      if (sets.read.has(item.id)) weight += 1;
      if (!weight) return;

      tagsFor(item).forEach(function (tag) { addWeight(profile.tags, tag, weight); });
      entitiesFor(context, item).forEach(function (entity) {
        addWeight(profile.entities, entity, weight);
      });
      addWeight(profile.sources, String(item.source || "").trim().toUpperCase(), weight * 0.35);
    });

    profile.tagMax = maxWeight(profile.tags);
    profile.entityMax = maxWeight(profile.entities);
    profile.sourceMax = maxWeight(profile.sources);
    return profile;
  }

  function averageAffinity(values, weights, max) {
    if (!values.length) return 0;
    var sum = values.reduce(function (total, key) { return total + (weights[key] || 0); }, 0);
    return clamp(sum / (values.length * max), 0, 1);
  }

  function historyAffinity(item, tags, entities, profile) {
    var tagScore = averageAffinity(tags, profile.tags, profile.tagMax);
    var entityScore = averageAffinity(entities, profile.entities, profile.entityMax);
    var sourceKey = String((item && item.source) || "").trim().toUpperCase();
    var sourceScore = clamp((profile.sources[sourceKey] || 0) / profile.sourceMax, 0, 1);
    return clamp(tagScore * 0.55 + entityScore * 0.35 + sourceScore * 0.10, 0, 1);
  }

  function engagementScore(item, context) {
    var id = item && item.id;
    var views = Math.max(0, finiteNumber((context.views || {})[id]));
    var likes = Math.max(0, finiteNumber((context.likeCounts || {})[id]));
    var comments = Math.max(0, finiteNumber((context.commentCounts || {})[id]));

    /* Views are impressions, not approval. Smoothed action rates prevent a
       highly exposed card from winning only because it was already shown. */
    var likeRate = (likes + 0.5) / (views + 20);
    var commentRate = (comments + 0.25) / (views + 40);
    return clamp(
      likeRate * 5 + commentRate * 10 + Math.log1p(likes + comments * 2) * 0.08,
      0,
      2.2
    );
  }

  function dateValue(item) {
    var value = Date.parse(String((item && item.date) || "") + "T00:00:00Z");
    return Number.isFinite(value) ? value : 0;
  }

  function scoreItems(items, context) {
    var sets = {
      likes: toSet(context.likes),
      bookmarks: toSet(context.bookmarks),
      read: toSet(context.read),
      viewed: toSet(context.viewed),
      hidden: toSet(context.hidden)
    };
    var profile = buildProfile(items, context, sets);
    var now = finiteNumber(context.now) || Date.now();

    return items.filter(function (item) {
      return item && item.id && !sets.hidden.has(item.id);
    }).map(function (item, originalIndex) {
      var tags = tagsFor(item);
      var entities = entitiesFor(context, item);
      var directReasons = directReasonsFor(context, item);
      var direct = directReasons.length > 0;
      var affinity = historyAffinity(item, tags, entities, profile);
      var timestamp = dateValue(item);
      var ageDays = timestamp ? Math.max(0, (now - timestamp) / DAY_MS) : 30;
      var freshness = Math.exp(-ageDays / 12) * 2.4;
      var engagement = engagementScore(item, context);
      var seenPenalty = sets.read.has(item.id) ? 2.4 : (sets.viewed.has(item.id) ? 0.65 : 0);
      var directBoost = direct ? 6 + Math.min(2, Math.max(0, directReasons.length - 1)) : 0;
      var score = directBoost + affinity * 4 + freshness + engagement - seenPenalty;

      return {
        item: item,
        originalIndex: originalIndex,
        timestamp: timestamp,
        tags: tags,
        source: String(item.source || "").trim().toUpperCase(),
        direct: direct,
        affinity: affinity,
        engagement: engagement,
        discovery: !direct && affinity < 0.18,
        score: score
      };
    });
  }

  function jaccard(a, b) {
    if (!a.length || !b.length) return 0;
    var right = new Set(b);
    var intersection = a.reduce(function (n, key) { return n + (right.has(key) ? 1 : 0); }, 0);
    return intersection / (a.length + b.length - intersection);
  }

  function adjustedScore(record, selected, sourceCounts) {
    var sourceCount = sourceCounts[record.source] || 0;
    var score = record.score - sourceCount * 1.15;
    if (selected.length && selected[selected.length - 1].source === record.source) score -= 0.75;

    var recent = selected.slice(-3);
    var overlap = recent.reduce(function (max, prior) {
      return Math.max(max, jaccard(record.tags, prior.tags));
    }, 0);
    return score - overlap * 1.1;
  }

  function pickBest(pool, selected, sourceCounts) {
    var best = null;
    var bestAdjusted = -Infinity;
    pool.forEach(function (record) {
      var adjusted = adjustedScore(record, selected, sourceCounts);
      if (
        adjusted > bestAdjusted ||
        (adjusted === bestAdjusted && best && record.timestamp > best.timestamp) ||
        (adjusted === bestAdjusted && best && record.timestamp === best.timestamp && record.originalIndex < best.originalIndex)
      ) {
        best = record;
        bestAdjusted = adjusted;
      }
    });
    return best;
  }

  function reasonKey(record, forcedExplore) {
    if (forcedExplore && record.discovery) return "explore";
    if (record.direct) return "follow";
    if (record.affinity >= 0.18) return "similar";
    if (record.engagement >= 0.65) return "popular";
    return "fresh";
  }

  function diversify(records, context) {
    var remaining = records.slice();
    var selected = [];
    var sourceCounts = Object.create(null);
    var explorationEvery = Math.max(5, finiteNumber(context.explorationEvery) || 10);

    while (remaining.length) {
      var forcedExplore = selected.length > 0 && (selected.length + 1) % explorationEvery === 0;
      var pool = forcedExplore ? remaining.filter(function (record) { return record.discovery; }) : remaining;
      if (!pool.length) pool = remaining;
      var best = pickBest(pool, selected, sourceCounts);
      if (!best) break;
      selected.push(best);
      sourceCounts[best.source] = (sourceCounts[best.source] || 0) + 1;
      lastReasons[best.item.id] = reasonKey(best, forcedExplore);
      remaining.splice(remaining.indexOf(best), 1);
    }
    return selected;
  }

  function enabled(storage) {
    try {
      var target = storage || (typeof localStorage !== "undefined" ? localStorage : null);
      var value = target && target.getItem ? target.getItem(FLAG_KEY) : null;
      return value !== "0" && value !== "off" && value !== "false";
    } catch (e) {
      return true;
    }
  }

  function rank(items, context) {
    var list = Array.isArray(items) ? items : [];
    var safeContext = context || {};
    lastReasons = Object.create(null);
    if (list.length < 2) return list.slice();
    return diversify(scoreItems(list, safeContext), safeContext).map(function (record) {
      return record.item;
    });
  }

  function reason(id, lang) {
    var key = lastReasons[id];
    var dict = REASON_TEXT[lang] || REASON_TEXT.en;
    return key ? (dict[key] || REASON_TEXT.en[key] || "") : "";
  }

  return {
    VERSION: VERSION,
    FLAG_KEY: FLAG_KEY,
    enabled: enabled,
    rank: rank,
    reason: reason
  };
});
