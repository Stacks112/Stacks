/*
 * D1 pending_cards -> GitHub Actions dispatcher.
 *
 * The publication session only writes a validated payload to D1. This small
 * Worker-side poller is the cloud-only handoff that removes the need for a
 * person to press "Run workflow" in GitHub.
 */

export const PUBLISH_DISPATCH_CRON = "*/5 * * * *";

const STATE_KEY = "apply-pending";
const REPOSITORY = "Stacks112/Stacks";
const WORKFLOW = "apply-pending.yml";
const REF = "main";
// Leave enough time for the Actions runner to finish before retrying a
// successful dispatch. Network/API failures release the claim immediately.
const COOLDOWN_SECONDS = 900;

let stateTableReady = false;

async function ensureStateTable(db) {
  if (stateTableReady) return;
  await db.exec(
    "CREATE TABLE IF NOT EXISTS publish_dispatch_state (" +
    "key TEXT PRIMARY KEY, " +
    "queue_id TEXT NOT NULL, " +
    "dispatched_at INTEGER NOT NULL DEFAULT 0)"
  );
  stateTableReady = true;
}

async function releaseClaim(db, queueId) {
  try {
    await db.prepare(
      "UPDATE publish_dispatch_state SET dispatched_at = 0 " +
      "WHERE key = ?1 AND queue_id = ?2"
    ).bind(STATE_KEY, queueId).run();
  } catch (e) {
    console.log(JSON.stringify({ event: "publish_dispatch_state_reset_failed" }));
  }
}

/**
 * Look for the oldest pending card, claim one dispatch window atomically, and
 * ask GitHub to run the existing idempotent apply-pending workflow.
 *
 * `nowMs` and `fetchImpl` are injectable so the state machine can be tested
 * without a live D1 or GitHub request.
 */
export async function dispatchPendingCards(
  env,
  nowMs = Date.now(),
  fetchImpl = globalThis.fetch
) {
  if (!env || !env.DB) return { status: "disabled", reason: "no_db" };

  const queue = await env.DB.prepare(
    "SELECT id, created_at FROM pending_cards " +
    "ORDER BY created_at ASC LIMIT 1"
  ).first();
  if (!queue || !queue.id) return { status: "empty" };

  const token = String(env.PUBLISH_GITHUB_TOKEN || "").trim();
  if (!token) {
    console.log(JSON.stringify({
      event: "publish_dispatch_disabled",
      reason: "PUBLISH_GITHUB_TOKEN_missing"
    }));
    return { status: "disabled", reason: "missing_token", id: queue.id };
  }

  await ensureStateTable(env.DB);
  const now = Math.floor(nowMs / 1000);
  const cutoff = now - COOLDOWN_SECONDS;

  /*
   * SQLite serialises this conditional upsert. Only one concurrent Worker
   * invocation can claim the same queue head inside the cooldown window.
   * A new queue head bypasses the cooldown so a later card is not delayed by
   * an older malformed or held row.
   */
  const claim = await env.DB.prepare(
    "INSERT INTO publish_dispatch_state (key, queue_id, dispatched_at) " +
    "VALUES (?1, ?2, ?3) " +
    "ON CONFLICT(key) DO UPDATE SET " +
    "queue_id = excluded.queue_id, dispatched_at = excluded.dispatched_at " +
    "WHERE publish_dispatch_state.queue_id <> excluded.queue_id " +
    "OR publish_dispatch_state.dispatched_at <= ?4 " +
    "RETURNING queue_id"
  ).bind(STATE_KEY, queue.id, now, cutoff).first();

  if (!claim) return { status: "cooldown", id: queue.id };

  const url = "https://api.github.com/repos/" + REPOSITORY
    + "/actions/workflows/" + WORKFLOW + "/dispatches";
  let response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "Stacks-publish-dispatcher",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: JSON.stringify({ ref: REF })
    });
  } catch (e) {
    await releaseClaim(env.DB, queue.id);
    console.log(JSON.stringify({
      event: "publish_dispatch_request_failed",
      id: queue.id
    }));
    return { status: "failed", reason: "request_error", id: queue.id };
  }

  if (!response || !response.ok) {
    await releaseClaim(env.DB, queue.id);
    console.log(JSON.stringify({
      event: "publish_dispatch_rejected",
      id: queue.id,
      status: response ? response.status : 0
    }));
    return {
      status: "failed",
      reason: "github_rejected",
      id: queue.id,
      httpStatus: response ? response.status : 0
    };
  }

  console.log(JSON.stringify({
    event: "publish_dispatch_sent",
    id: queue.id,
    workflow: WORKFLOW
  }));
  return { status: "dispatched", id: queue.id };
}
