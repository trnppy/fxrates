import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

DATABASE = '/fxrates.db'
STATIC_DIR = 'static'
ALLOWED_CURRENCIES = {'inr', 'twd', 'ils', 'eur', 'rsd'}

# Budget reference rates: 1 LC = $x
BUDGET_RATES = {
    'eur': {2024: 1.1039, 2025: 1.03520, 2026: 1.17500},
    'inr': {2024: 0.0120, 2025: 0.0017, 2026: 0.0111},
    'twd': {2024: 0.0326, 2025: 0.0305, 2026: 0.0319},
    'ils': {2024: 0.2778, 2025: 0.2748, 2026: 0.3138},
    'rsd': {2024: 0.0095, 2025: 0.0089, 2026: 0.0101},
}

os.makedirs(STATIC_DIR, exist_ok=True)


def is_favorable(actual_rate, budget_rate):
    # Assumption: lower 1 LC = USD is favorable.
    # Flip to >= if Finance treats higher as favorable.
    return actual_rate <= budget_rate


def generate_plots(currency):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT date, rate FROM exchange_rates WHERE currency = ?"
    df = pd.read_sql_query(query, conn, params=(currency,))
    conn.close()

    if df.empty:
        print(f"No data found for currency: {currency}")
        return

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df['year'] = df['date'].dt.year

    budgets = BUDGET_RATES.get(currency, {})
    df['budget'] = df['year'].map(budgets)

    plt.figure(figsize=(15, 5))

    # Draw shaded variance and actual series separately for each year
    favorable_label_added = False
    unfavorable_label_added = False
    budget_label_added = set()

    years_in_data = sorted(df['year'].dropna().unique())

    for year in years_in_data:
        year_df = df[df['year'] == year].copy()
        if year_df.empty:
            continue

        budget_rate = budgets.get(year)

        # Draw budget line only for the span where data exists in that year
        if budget_rate is not None:
            budget_label = f'Budget {year} ({budget_rate:.5f})'
            plt.hlines(
                y=budget_rate,
                xmin=year_df['date'].min(),
                xmax=year_df['date'].max(),
                linestyles='--',
                linewidth=2,
                label=budget_label if budget_label not in budget_label_added else None
            )
            budget_label_added.add(budget_label)

            plt.text(
                year_df['date'].max(),
                budget_rate,
                f'  {year}: {budget_rate:.5f}',
                va='bottom'
            )

            # Shade favorable/unfavorable area against budget
            favorable_mask = year_df['rate'] <= budget_rate
            unfavorable_mask = year_df['rate'] > budget_rate

            if favorable_mask.any():
                plt.fill_between(
                    year_df['date'],
                    year_df['rate'],
                    budget_rate,
                    where=favorable_mask,
                    interpolate=True,
                    alpha=0.18,
                    color='green'
                )

            if unfavorable_mask.any():
                plt.fill_between(
                    year_df['date'],
                    year_df['rate'],
                    budget_rate,
                    where=unfavorable_mask,
                    interpolate=True,
                    alpha=0.18,
                    color='red'
                )

        # Color the actual line segment-by-segment within the year only
        for i in range(len(year_df)):
            row = year_df.iloc[i]
            actual = row['rate']
            budget = row['budget']

            if pd.notna(budget):
                favorable = is_favorable(actual, budget)
                point_color = 'green' if favorable else 'red'
                point_label = None

                if favorable and not favorable_label_added:
                    point_label = 'Actual (favorable)'
                    favorable_label_added = True
                elif (not favorable) and not unfavorable_label_added:
                    point_label = 'Actual (unfavorable)'
                    unfavorable_label_added = True
            else:
                point_color = 'blue'
                point_label = 'Actual'

            plt.scatter(
                row['date'],
                actual,
                color=point_color,
                s=22,
                zorder=3,
                label=point_label
            )

            if i > 0:
                prev = year_df.iloc[i - 1]
                seg_favorable = is_favorable(actual, budget) if pd.notna(budget) else True
                seg_color = 'green' if seg_favorable else 'red'

                plt.plot(
                    [prev['date'], row['date']],
                    [prev['rate'], row['rate']],
                    color=seg_color,
                    linewidth=1.8,
                    zorder=2
                )

    latest_row = df.iloc[-1]
    latest_year = int(latest_row['year'])
    latest_rate = float(latest_row['rate'])

    if latest_year in budgets:
        latest_budget = budgets[latest_year]
        variance_pct = ((latest_rate - latest_budget) / latest_budget) * 100
        status = "Favorable" if is_favorable(latest_rate, latest_budget) else "Unfavorable"
        title_suffix = f" | Latest vs {latest_year} Budget: {variance_pct:+.2f}% ({status})"
    else:
        title_suffix = " | No budget configured for latest year"

    plt.title(f'{currency.upper()} to USD - Fx Movement Over Time{title_suffix}')
    plt.xlabel('Date')
    plt.ylabel('Exchange Rate (1 LC = USD)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(STATIC_DIR, f'{currency}.png'))
    plt.close()


app = Flask(__name__, static_folder=STATIC_DIR)
app.wsgi_app = ProxyFix(app.wsgi_app)


@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self'"
    return response


@app.route('/fxplot')
def serve_all_fxplots():
    for currency in sorted(ALLOWED_CURRENCIES):
        generate_plots(currency)

    html = "<html><head><title>Currency Plots</title></head><body>"
    html += "<h1>Exchange Rate Plots vs Budget</h1>"
    html += "<p>Green = favorable vs budget, Red = unfavorable vs budget</p>"
    html += "<p>Shaded area shows variance from the applicable yearly budget rate.</p>"

    for currency in sorted(ALLOWED_CURRENCIES):
        budget_text = ", ".join(
            f"{year}: {rate:.5f}"
            for year, rate in sorted(BUDGET_RATES.get(currency, {}).items())
        ) or "not configured"

        html += f"<div><h2>{currency.upper()} (Budget rates: {budget_text})</h2>"
        html += f"<img src='/{STATIC_DIR}/{currency}.png' alt='{currency} plot' style='width:80%;'></div><hr>"

    html += "</body></html>"
    return html


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)

