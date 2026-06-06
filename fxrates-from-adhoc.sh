# query exchange rates { twd, inr, ils, eur } to usd
# jq to parse json
# round to 5 decimal places
# upsert into sqlite3 db
curl -s -k https://latest.currency-api.pages.dev/v1/currencies/usd.json | jq '{(.date): {eur: ((1 / .usd.eur * 100000) | round / 100000), inr: ((1 / .usd.inr * 100000) | round / 100000), twd: ((1 / .usd.twd * 100000) | round / 100000), ils: ((1 / .usd.ils * 100000) | round / 100000), rsd: ((1 / .usd.rsd * 100000) | round / 100000)}}' | jq -r 'to_entries[] | .key as $date | .value | to_entries[] | "INSERT OR REPLACE INTO exchange_rates (date, currency, rate) VALUES (\($date | @json), \(.key | @json), \(.value));"' | sqlite3 ~storage/fxrates/fxrates.db
