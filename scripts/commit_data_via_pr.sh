#!/usr/bin/env bash
# Commit staged data changes to main via PR so branch protection status checks can pass.
# Usage: bash scripts/commit_data_via_pr.sh "commit message" [path ...]
# Prints committed=true|false to GITHUB_OUTPUT when set.
set -euo pipefail

MSG="${1:?commit message required}"
shift
PATHS=("$@")
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(data/*.csv data/event_aliases.json data/quality_reports/)
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

if [[ "${GITHUB_REF_NAME:-}" != "main" ]]; then
  echo "::warning::Skipping data commit (ref=${GITHUB_REF_NAME:-unknown}; only main publishes data)."
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "committed=false" >>"$GITHUB_OUTPUT"
  fi
  exit 0
fi

git add "${PATHS[@]}" || true
if git diff --staged --quiet; then
  echo "No data changes to commit."
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "committed=false" >>"$GITHUB_OUTPUT"
  fi
  exit 0
fi

BRANCH="bot/data-export-${GITHUB_RUN_ID:-$RANDOM}"
git checkout -B "$BRANCH"
git commit -m "$MSG"
git push -u origin "HEAD:$BRANCH"

PR_URL="$(
  gh pr create \
    --base main \
    --head "$BRANCH" \
    --title "$MSG" \
    --body "Automated data export from \`${GITHUB_WORKFLOW:-workflow}\` (run ${GITHUB_RUN_ID:-local})."
)"
echo "Opened $PR_URL"

# Wait for required checks, then squash-merge.
gh pr checks --watch --fail-fast "$PR_URL"
gh pr merge --squash --delete-branch "$PR_URL"

git fetch origin main
git checkout main
git reset --hard origin/main

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "committed=true" >>"$GITHUB_OUTPUT"
fi
echo "Merged data PR into main."
