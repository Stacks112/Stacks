CREATE TABLE IF NOT EXISTS manual_post_overrides (
  slug TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  body_html TEXT NOT NULL,
  source_url TEXT,
  published_at TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_manual_post_overrides_status_updated
  ON manual_post_overrides (status, updated_at DESC);
