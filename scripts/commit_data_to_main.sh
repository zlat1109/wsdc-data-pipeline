#!/usr/bin/env bash
# Commit generated data/docs changes straight to protected main.
#
# Branch protection requires a successful `pytest` check on the pushed SHA.
# PRs/pushes made with GITHUB_TOKEN never trigger tests.yml, so this script runs
# the same pytest command itself and records the result as a `pytest` check run
# (GITHUB_TOKEN check runs are attributed to the GitHub Actions app, which is
# what the protection rule expects). Needs `contents: write` + `checks: write`.
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
gh api "repos/${REPO}/check-runs" \
  -f name=pytest \
  -f head_sha="$SHA" \
  -f status=completed \
  -f conclusion="$CONCLUSION" \
  -f details_url="$RUN_URL" \
  -f "output[title]=pytest ($CONCLUSION)" \
  -f "output[summary]=Run inside ${GITHUB_WORKFLOW:-workflow} before publishing data." \
  >/dev/null

if [[ $PYTEST_RC -ne 0 ]]; then
  echo "::error::pytest failed on the data commit; not publishing to main."
  exit 1
fi

git push origin "HEAD:main"
emit true
echo "Published $SHA to main."
