#!/usr/bin/env bash
# Build homepage KPIs + secondary-role dashboard JSON and push to the analytics site.
#
# Used by .github/workflows/full-parse.yml after CSV export.
#
# Requires env:
#   WSDC_ANALYTICS_DEPLOY_TOKEN — PAT with contents:write on
#     wsdc-analytics/wsdc-analytics.github.io
#
# Optional env:
#   ANALYTICS_REPO   default wsdc-analytics/wsdc-analytics.github.io
#   PIPELINE_DATA    default data  (relative to cwd = pipeline repo root)
#   SITE_YEARS       space-separated years for secondary dashboard (default: 2023..current UTC year)

set -euo pipefail

ANALYTICS_REPO="${ANALYTICS_REPO:-wsdc-analytics/wsdc-analytics.github.io}"
PIPELINE_DATA="${PIPELINE_DATA:-data}"
WORKDIR="${RUNNER_TEMP:-/tmp}/wsdc-analytics-site-sync"
CURRENT_YEAR="$(date -u +%Y)"
SITE_YEARS="${SITE_YEARS:-$(seq 2023 "${CURRENT_YEAR}" | tr '\n' ' ')}"

if [[ -z "${WSDC_ANALYTICS_DEPLOY_TOKEN:-}" ]]; then
  echo "::warning::WSDC_ANALYTICS_DEPLOY_TOKEN not set — skipping analytics site sync"
  exit 0
fi

PIPELINE_DATA_ABS="$(cd "${PIPELINE_DATA}" && pwd)"
for required in \
  events_wsdc.csv \
  dancers_results_info.csv \
  dancer_role_info.csv \
  location_info.csv \
  event_editions.csv
do
  if [[ ! -f "${PIPELINE_DATA_ABS}/${required}" ]]; then
    echo "::error::Missing ${PIPELINE_DATA_ABS}/${required} — run export before site sync"
    exit 1
  fi
done

rm -rf "${WORKDIR}"
git clone --depth 1 \
  "https://x-access-token:${WSDC_ANALYTICS_DEPLOY_TOKEN}@github.com/${ANALYTICS_REPO}.git" \
  "${WORKDIR}"

echo "Building homepage_kpis.json from ${PIPELINE_DATA_ABS}"
python3 "${WORKDIR}/scripts/build_homepage_kpis.py" \
  --source-dir "${PIPELINE_DATA_ABS}" \
  --output "${WORKDIR}/static/data/homepage_kpis.json"

echo "Building secondary_country_unified.json (years: ${SITE_YEARS})"
# shellcheck disable=SC2086
python3 "${WORKDIR}/scripts/update_secondary_country_unified.py" \
  --source-dir "${PIPELINE_DATA_ABS}" \
  --output "${WORKDIR}/static/data/secondary_country_unified.json" \
  --years ${SITE_YEARS}

python3 "${WORKDIR}/scripts/validate_site_data.py" || {
  echo "::error::Site data validation failed after rebuild"
  exit 1
}

cd "${WORKDIR}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add \
  static/data/homepage_kpis.json \
  static/data/secondary_country_unified.json

if git diff --staged --quiet; then
  echo "No analytics site JSON changes to push"
  exit 0
fi

git commit -m "$(cat <<EOF
chore(data): refresh homepage KPIs and secondary-role dashboard

Automated push from wsdc-data-pipeline after full-parse / export.
EOF
)"

git push origin HEAD
echo "✅ Synced analytics site JSON to ${ANALYTICS_REPO}"
