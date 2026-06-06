#!/usr/bin/env bash
set -euo pipefail

# required arguments: DB DATE
# example: ~/fxrates/fxrates.db 2026-05-04
[[ $# -ne 2 ]] && exit 1

DB=${1}
[[ ! -e "${DB}" ]] && exit 1

for d in ${2}; do
  url1="https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@${d}/v1/currencies/usd.json"
  url2="https://${d}.currency-api.pages.dev/v1/currencies/usd.json"

  json="$(curl -fsS "$url1" || curl -fsS "$url2")"

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

