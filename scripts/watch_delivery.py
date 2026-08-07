#!/usr/bin/env python3
"""Watch automatic publishing workflows and the GitHub Pages deployment.

This is intentionally read-only.  The workflow turns a non-zero exit into a
durable GitHub Issue, so a failed run cannot disappear in the Actions tab.
"""

import json
import os
import urllib.error
import urllib.request


API_ROOT = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()
TOKEN = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
BRANCH = os.environ.get("WATCH_BRANCH", "main").strip() or "main"
PAGE_ENVIRONMENT = os.environ.get("WATCH_PAGE_ENVIRONMENT", "github-pages").strip()

APPLY_WORKFLOW_NAMES = {"Apply pending cards"}
PAGES_WORKFLOW_NAMES = {"pages-build-deployment", "pages build and deployment"}
BAD_RUN_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "stale",
    "timed_out",
}
BAD_DEPLOYMENT_STATES = {"error", "failure", "inactive"}


def github_get(path):
    request = urllib.request.Request(
        API_ROOT + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError("GitHub API %s: HTTP %s %s" % (path, exc.code, detail)) from exc


def latest_named(runs, names):
    candidates = [run for run in runs if run.get("name") in names]
    candidates.sort(key=lambda run: run.get("created_at", ""), reverse=True)
    return candidates[0] if candidates else None


def run_label(run):
    return "%s %s (%s)" % (
        run.get("name") or "workflow",
        (run.get("head_sha") or "")[:9],
        run.get("html_url") or "no URL",
    )


def inspect_run(label, run, failures):
    if not run:
        print("DELIVERY_%s=not-found" % label.upper().replace(" ", "_"))
        return

    status = run.get("status") or "unknown"
    conclusion = run.get("conclusion") or "pending"
    print("DELIVERY_%s_STATUS=%s" % (label.upper().replace(" ", "_"), status))
    print("DELIVERY_%s_CONCLUSION=%s" % (label.upper().replace(" ", "_"), conclusion))
    print("DELIVERY_%s_RUN=%s" % (label.upper().replace(" ", "_"), run_label(run)))
    if status == "completed" and conclusion in BAD_RUN_CONCLUSIONS:
        failures.append("%s workflow failed: %s" % (label, run_label(run)))


def inspect_pages_deployment(failures):
    deployments = github_get(
        "/repos/%s/deployments?environment=%s&per_page=10" % (REPO, PAGE_ENVIRONMENT)
    )
    if not deployments:
        print("DELIVERY_PAGES_DEPLOYMENT=not-found")
        return

    deployment = deployments[0]
    deployment_id = deployment.get("id")
    statuses = github_get(
        "/repos/%s/deployments/%s/statuses?per_page=10" % (REPO, deployment_id)
    )
    status = statuses[0] if statuses else {}
    state = status.get("state") or "pending"
    sha = (deployment.get("sha") or "")[:9]
    url = status.get("target_url") or deployment.get("url") or "no URL"
    print("DELIVERY_PAGES_DEPLOYMENT_STATE=%s" % state)
    print("DELIVERY_PAGES_DEPLOYMENT=%s %s (%s)" % (sha, deployment_id, url))
    if state in BAD_DEPLOYMENT_STATES:
        failures.append("GitHub Pages deployment failed: %s %s (%s)" % (state, sha, url))


def main():
    if not REPO or "/" not in REPO or not TOKEN:
        print("DELIVERY_STATUS=error")
        print("DELIVERY_ERROR=GITHUB_REPOSITORY or GH_TOKEN is missing")
        return 2

    try:
        runs = github_get(
            "/repos/%s/actions/runs?branch=%s&per_page=100" % (REPO, BRANCH)
        ).get("workflow_runs", [])
        failures = []
        inspect_run("apply pending", latest_named(runs, APPLY_WORKFLOW_NAMES), failures)
        inspect_run("pages workflow", latest_named(runs, PAGES_WORKFLOW_NAMES), failures)
        inspect_pages_deployment(failures)
    except Exception as exc:
        print("DELIVERY_STATUS=error")
        print("DELIVERY_ERROR=%s: %s" % (type(exc).__name__, exc))
        return 2

    if failures:
        print("DELIVERY_STATUS=failure")
        print("DELIVERY_FAILURE_COUNT=%d" % len(failures))
        for failure in failures:
            print("DELIVERY_FAILURE=" + failure)
        return 1

    print("DELIVERY_STATUS=ok")
    print("DELIVERY_FAILURE_COUNT=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
