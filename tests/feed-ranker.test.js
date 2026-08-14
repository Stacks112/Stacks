"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const ranker = require("../assets/feed-ranker.js");

const NOW = Date.parse("2026-08-14T00:00:00Z");

function item(id, source, date, tags, entities) {
  return { id, source, date, tags: tags || [], entities: entities || [] };
}

function context(overrides) {
  return Object.assign({
    now: NOW,
    likes: new Set(),
    bookmarks: new Set(),
    read: new Set(),
    viewed: new Set(),
    views: {},
    likeCounts: {},
    commentCounts: {},
    getEntities: value => value.entities,
    getDirectReasons: value => value.entities.includes("NVDA") ? [{ kind: "co", key: "NVDA" }] : []
  }, overrides || {});
}

test("follow matches beat unrelated fresh cards", () => {
  const cards = [
    item("fresh", "B", "2026-08-14", ["OIL"], []),
    item("follow", "A", "2026-08-10", ["AI"], ["NVDA"])
  ];
  assert.equal(ranker.rank(cards, context())[0].id, "follow");
});

test("read cards are demoted when other signals are equal", () => {
  const cards = [
    item("read", "A", "2026-08-14", ["AI"], ["NVDA"]),
    item("unread", "B", "2026-08-14", ["AI"], ["NVDA"])
  ];
  assert.equal(ranker.rank(cards, context({ read: new Set(["read"]) }))[0].id, "unread");
});

test("source diversity breaks up repeated publishers", () => {
  const cards = [
    item("a1", "Same", "2026-08-14", ["AI"], ["NVDA"]),
    item("a2", "Same", "2026-08-14", ["AI"], ["NVDA"]),
    item("a3", "Same", "2026-08-14", ["AI"], ["NVDA"]),
    item("b1", "Different", "2026-08-13", ["SEMIS"], ["NVDA"])
  ];
  const ids = ranker.rank(cards, context()).map(value => value.id);
  assert.ok(ids.indexOf("b1") < ids.indexOf("a3"));
});

test("smoothed action rates beat exposure-only popularity", () => {
  const cards = [
    item("exposed", "A", "2026-08-14", ["A"], []),
    item("liked", "B", "2026-08-14", ["B"], [])
  ];
  const ranked = ranker.rank(cards, context({
    getDirectReasons: () => [],
    views: { exposed: 10000, liked: 100 },
    likeCounts: { exposed: 0, liked: 20 }
  }));
  assert.equal(ranked[0].id, "liked");
});

test("every tenth slot can explore outside direct follows", () => {
  const cards = [];
  for (let i = 0; i < 12; i += 1) {
    cards.push(item("follow-" + i, "Source-" + i, "2026-08-14", ["AI"], ["NVDA"]));
  }
  cards.push(item("explore", "New source", "2026-07-01", ["HEALTH"], []));
  const ranked = ranker.rank(cards, context());
  assert.equal(ranked[9].id, "explore");
  assert.equal(ranker.reason("explore", "ko"), "새로운 주제 추천");
});

test("feature flag defaults on and supports a local kill switch", () => {
  assert.equal(ranker.enabled({ getItem: () => null }), true);
  assert.equal(ranker.enabled({ getItem: () => "off" }), false);
});
