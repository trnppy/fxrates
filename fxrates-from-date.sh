#!/usr/bin/env bash
set -euo pipefail

# required arguments: DB START_DATE
# example: ~/fxrates/fxrates.db 2026-05-04
# optional: --dry-run
usage() { echo "Usage: $0 [--dry-run] <db> <start_date>"; exit 1; }

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi

[[ $# -ne 2 ]] && usage

DB="$1"
START_DATE="$2"
[[ ! -e "$DB" ]] && { echo "DB not found: $DB"; exit 1; }

TODAY="$(date -u +%F)"

# Collect all dates from start to yesterday (API lags by 1 day)
all_dates=()
d="$START_DATE"
while [[ "$d" < "$TODAY" ]]; do
  all_dates+=("$d")
  d="$(date -u -d "$d + 1 day" +%F 2>/dev/null || date -u -v+1d -jf %F "$d" +%F)"
done

# Find which dates are already in the DB
existing_dates="$(sqlite3 "$DB" "SELECT DISTINCT date FROM exchange_rates;" 2>/dev/null || true)"

for d in "${all_dates[@]}"; do
  if echo "$existing_dates" | grep -qx "$d"; then
    echo "Skipping $d (already present)"
    continue
  fi

  if $DRY_RUN; then
    echo "[dry-run] Would fetch $d and INSERT OR REPLACE into $DB"
    continue
  fi

  echo "Fetching $d..."
  url1="https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@${d}/v1/currencies/usd.json"
  url2="https://${d}.currency-api.pages.dev/v1/currencies/usd.json"

  json="$(curl -fsS "$url1" || curl -fsS "$url2")" || {
    echo "Failed to fetch $d, skipping"
    continue
  }

  printf '%s\n' "$json" |
    jq -r '
      .date as $date
      | .usd
      | {
          eur: ((1 / .eur * 100000) | round / 100000),
          inr: ((1 / .inr * 100000) | round / 100000),
          twd: ((1 / .twd * 100000) | round / 100000),
          ils: ((1 / .ils * 100000) | round / 100000),
          rsd: ((1 / .rsd * 100000) | round / 100000)
        }
      | to_entries[]
      | "INSERT OR REPLACE INTO exchange_rates (date, currency, rate) VALUES (\($date | @json), \(.key | @json), \(.value));"
    ' | sqlite3 "$DB"
done

