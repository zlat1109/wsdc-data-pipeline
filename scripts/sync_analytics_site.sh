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

PIPELINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POINT_SUMMARY_CUTOFF="${POINT_SUMMARY_CUTOFF:-2026-07-28}"
POINT_SUMMARY_REPORT="${POINT_SUMMARY_REPORT:-${PIPELINE_DATA_ABS}/quality_reports/point_summary_last.json}"
echo "Building points_summaries.json (cutoff=${POINT_SUMMARY_CUTOFF})"
if python3 "${PIPELINE_ROOT}/scripts/build_points_summary.py" \
  --data-dir "${PIPELINE_DATA_ABS}" \
  --site-repo "${WORKDIR}" \
  --cutoff "${POINT_SUMMARY_CUTOFF}" \
  --update-window-days 30 \
  --report "${POINT_SUMMARY_REPORT}"
then
  echo "Point Summary build OK"
else
  echo "::warning::Point Summary build failed — continuing without updating points_summaries.json"
fi

python3 "${WORKDIR}/scripts/validate_site_data.py" || {
  echo "::error::Site data validation failed after rebuild"
  exit 1
}

# Bust browser/CDN cache and refresh visible "as of" labels on the secondary dashboard.
AS_OF="$(date -u +%Y-%m-%d)"
CACHE_V="$(date -u +%Y%m%d)-sync"
DASHBOARD_HTML="${WORKDIR}/secondary_role_distribution_dashboard_en.html"
BUBBLE_HTML="${WORKDIR}/interactive_secondary_country_bubble.html"
if [[ -f "${DASHBOARD_HTML}" ]]; then
  sed -i \
    -e "s|(as of [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\})|(as of ${AS_OF})|g" \
    -e "s|interactive_secondary_country_bubble.html?v=[^\"]*|interactive_secondary_country_bubble.html?v=${CACHE_V}|g" \
    "${DASHBOARD_HTML}"
fi
if [[ -f "${BUBBLE_HTML}" ]]; then
  sed -i \
    -e "s|2026 (partial, as of [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\})|2026 (partial, as of ${AS_OF})|g" \
    -e "s|secondary_country_unified.json?v=[^\"]*|secondary_country_unified.json?v=${CACHE_V}|g" \
    "${BUBBLE_HTML}"
fi
echo "Stamped secondary dashboard as_of=${AS_OF} cache_v=${CACHE_V}"

cd "${WORKDIR}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add \
  static/data/homepage_kpis.json \
  static/data/secondary_country_unified.json \
  static/data/points_summaries.json \
  secondary_role_distribution_dashboard_en.html \
  interactive_secondary_country_bubble.html

if git diff --staged --quiet; then
  echo "No analytics site changes to push"
  exit 0
fi

git commit -m "$(cat <<EOF
chore(data): refresh homepage KPIs, secondary-role dashboard, Point Summary

Automated push from wsdc-data-pipeline after full-parse / export.
EOF
)"

git push origin HEAD
echo "✅ Synced analytics site JSON to ${ANALYTICS_REPO}"
