CREATE TABLE IF NOT EXISTS article_metrics (
  article_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  author TEXT,
  published_at TEXT,
  tickers_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  view_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_views (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id TEXT NOT NULL,
  session_hash TEXT NOT NULL,
  ref_article_id TEXT,
  tickers_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_co_reads (
  source_article_id TEXT NOT NULL,
  target_article_id TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (source_article_id, target_article_id)
);

CREATE INDEX IF NOT EXISTS idx_article_views_session_created
  ON article_views (session_hash, created_at);

CREATE INDEX IF NOT EXISTS idx_article_views_article_created
  ON article_views (article_id, created_at);

CREATE INDEX IF NOT EXISTS idx_article_metrics_view_count
  ON article_metrics (view_count DESC);

CREATE INDEX IF NOT EXISTS idx_article_co_reads_source_score
  ON article_co_reads (source_article_id, score DESC);
