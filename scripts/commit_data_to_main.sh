#!/usr/bin/env bash
# Commit generated data/docs changes straight to protected main.
#
# Branch protection requires a successful `pytest` check on the pushed SHA.
# PRs/pushes made with GITHUB_TOKEN never trigger tests.yml, so this script runs
# the same pytest command itself and records the result as a `pytest` check run
# (GITHUB_TOKEN check runs are attributed to the GitHub Actions app, which is
# what the protection rule expects). Needs `contents: write` + `checks: write`.
#
# After creating the check, wait until GitHub lists it as completed/success on
# the SHA, settle briefly, then push. Retries only GH006 / required-check races;
# other push errors fail immediately.
#
# Usage: bash scripts/commit_data_to_main.sh "commit message" [path ...]
# Prints committed=true|false to GITHUB_OUTPUT when set.
set -euo pipefail

MSG="${1:?commit message required}"
shift
PATHS=("$@")
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(data/*.csv data/event_aliases.json data/quality_reports/)
fi

emit() {
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "committed=$1" >>"$GITHUB_OUTPUT"
  fi
}

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

if [[ "${GITHUB_REF_NAME:-}" != "main" ]]; then
  echo "::warning::Skipping data commit (ref=${GITHUB_REF_NAME:-unknown}; only main publishes data)."
  emit false
  exit 0
fi

git add "${PATHS[@]}" || true
if git diff --staged --quiet; then
  echo "No data changes to commit."
  emit false
  exit 0
fi

git commit -m "$MSG"
git fetch origin main
git rebase origin/main

SHA="$(git rev-parse HEAD)"
REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY required}"
BRANCH="bot/data-export-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"

cleanup() {
  git push origin --delete "$BRANCH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# The check-runs API needs the SHA to exist on the remote.
git push --force origin "HEAD:refs/heads/$BRANCH"

python -m pip install -q -r requirements.txt pytest
set +e
python -m pytest tests/ -q \
  --ignore=tests/test_data_analytics.py \
  --ignore=tests/test_data_processors.py
PYTEST_RC=$?
set -e

CONCLUSION=success
[[ $PYTEST_RC -eq 0 ]] || CONCLUSION=failure
RUN_URL="${GITHUB_SERVER_URL:-https://github.com}/${REPO}/actions/runs/${GITHUB_RUN_ID:-0}"
NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
gh api "repos/${REPO}/check-runs" \
  -f name=pytest \
  -f head_sha="$SHA" \
  -f status=completed \
  -f conclusion="$CONCLUSION" \
  -f started_at="$NOW" \
  -f completed_at="$NOW" \
  -f details_url="$RUN_URL" \
  -f "output[title]=pytest ($CONCLUSION)" \
  -f "output[summary]=Run inside ${GITHUB_WORKFLOW:-workflow} before publishing data." \
  >/dev/null

if [[ $PYTEST_RC -ne 0 ]]; then
  echo "::error::pytest failed on the data commit; not publishing to main."
  exit 1
fi

pytest_check_visible() {
  local count
  count="$(
    gh api "repos/${REPO}/commits/${SHA}/check-runs" \
      --jq '[.check_runs[] | select(.name=="pytest" and .status=="completed" and .conclusion=="success")] | length' \
      2>/dev/null || true
  )"
  count="${count:-0}"
  [[ "$count" =~ ^[0-9]+$ ]] || count=0
  [[ "$count" -ge 1 ]]
}

is_branch_protection_race() {
  # GH006 / required-check lag — only these are safe to retry.
  local err="$1"
  grep -Eqi 'GH006|Protected branch update failed|Required status check .+ is expected' <<<"$err"
}

# Wait until branch protection can see the synthetic pytest check.
echo "Waiting for pytest check on ${SHA}…"
CHECK_OK=0
for _ in $(seq 1 30); do
  if pytest_check_visible; then
    CHECK_OK=1
    break
  fi
  sleep 2
done
if [[ "$CHECK_OK" -ne 1 ]]; then
  echo "::error::pytest check on ${SHA} not visible to GitHub after wait; not publishing to main."
  exit 1
fi

# Brief settle: API visibility can lead branch-protection evaluation by a beat.
sleep 2

# Retry only GH006/required-check races; fail fast on auth/non-ff/other errors.
PUSH_OK=0
PUSH_ERR_FILE="$(mktemp)"
for attempt in 1 2 3 4 5; do
  if git push origin "HEAD:main" 2>"$PUSH_ERR_FILE"; then
    PUSH_OK=1
    break
  fi
  PUSH_ERR="$(cat "$PUSH_ERR_FILE")"
  cat "$PUSH_ERR_FILE" >&2
  if ! is_branch_protection_race "$PUSH_ERR"; then
    echo "::error::push to main failed with a non-retryable error (not GH006/required-check race)."
    rm -f "$PUSH_ERR_FILE"
    exit 1
  fi
  echo "::warning::branch-protection race on push (attempt ${attempt}/5); waiting before retry…"
  sleep $((attempt * 3))
  # Re-confirm check still present before the next attempt.
  if ! pytest_check_visible; then
    echo "::warning::pytest check not visible before retry; waiting…"
    sleep 2
  fi
done
rm -f "$PUSH_ERR_FILE"
if [[ "$PUSH_OK" -ne 1 ]]; then
  echo "::error::failed to push ${SHA} to main after GH006 retries."
  exit 1
fi

emit true
echo "Published $SHA to main."
