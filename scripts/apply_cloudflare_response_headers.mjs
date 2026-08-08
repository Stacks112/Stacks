import fs from "node:fs/promises";

const API = "https://api.cloudflare.com/client/v4";
const policy = JSON.parse(await fs.readFile("ops/cloudflare-response-headers.json", "utf8"));
const token = process.env.CLOUDFLARE_API_TOKEN;

if (!token) {
  console.warn("CLOUDFLARE_API_TOKEN is not configured; security headers were not changed.");
  process.exit(0);
}

async function cf(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.success === false) {
    throw new Error(`Cloudflare ${response.status}: ${JSON.stringify(body.errors || body)}`);
  }
  return body.result;
}

const zoneId = process.env.CLOUDFLARE_ZONE_ID ||
  (await cf(`/zones?name=${encodeURIComponent(policy.zone)}&status=active&per_page=1`))[0]?.id;
if (!zoneId) throw new Error(`Active Cloudflare zone not found: ${policy.zone}`);

const phase = "http_response_headers_transform";
const desired = {
  ref: policy.ref,
  description: policy.description,
  expression: policy.expression,
  action: "rewrite",
  action_parameters: {
    headers: Object.fromEntries(Object.entries(policy.headers).map(([name, value]) => [name, {
      operation: "set",
      value
    }]))
  }
};

const rulesets = await cf(`/zones/${zoneId}/rulesets?phase=${phase}`);
let ruleset = (rulesets || []).find(item => item.phase === phase && item.kind === "zone");
if (!ruleset) {
  ruleset = await cf(`/zones/${zoneId}/rulesets`, {
    method: "POST",
    body: JSON.stringify({
      name: "Stacks response security headers",
      description: "Managed by scripts/apply_cloudflare_response_headers.mjs",
      kind: "zone",
      phase,
      rules: [desired]
    })
  });
} else {
  const rules = (ruleset.rules || []).filter(rule => rule.ref !== policy.ref);
  rules.push(desired);
  ruleset = await cf(`/zones/${zoneId}/rulesets/${ruleset.id}`, {
    method: "PUT",
    body: JSON.stringify({ rules })
  });
}

console.log(`Cloudflare response headers active: ${ruleset.id} (${policy.ref})`);
